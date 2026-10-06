import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mochi.care import BondState
from mochi.config import ConfigStore, Position


class ConfigStoreTests(unittest.TestCase):
    def test_missing_config_has_no_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertIsNone(store.load_position())

    def test_position_round_trip_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "mochi" / "config.json")
            store.save_position(Position(42, 73))
            self.assertEqual(store.load_position(), Position(42, 73))
            store.reset_position()
            self.assertIsNone(store.load_position())

    def test_size_round_trip_and_clamping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertEqual(ConfigStore.DEFAULT_SIZE, 112)
            self.assertEqual(ConfigStore.SIZE_STEP, 16)
            self.assertEqual(store.load_size(), ConfigStore.DEFAULT_SIZE)
            store.save_size(192)
            self.assertEqual(store.load_size(), 192)
            store.save_size(999)
            self.assertEqual(store.load_size(), ConfigStore.MAX_SIZE)

    def test_reset_position_preserves_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            store.save_position(Position(42, 73))
            store.save_size(160)
            store.reset_position()
            self.assertIsNone(store.load_position())
            self.assertEqual(store.load_size(), 160)

    def test_audio_settings_round_trip_and_clamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertEqual(store.load_volume(), ConfigStore.DEFAULT_VOLUME)
            self.assertFalse(store.load_muted())
            store.save_volume(2.0)
            store.save_muted(True)
            self.assertEqual(store.load_volume(), 1.0)
            self.assertTrue(store.load_muted())

    def test_stay_put_defaults_off_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertFalse(store.load_stay_put())
            store.save_stay_put(True)
            self.assertTrue(store.load_stay_put())
            store.save_stay_put(False)
            self.assertFalse(store.load_stay_put())

    def test_edge_roam_defaults_off_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertFalse(store.load_edge_roam())
            store.save_edge_roam(True)
            self.assertTrue(store.load_edge_roam())
            store.save_edge_roam(False)
            self.assertFalse(store.load_edge_roam())

    def test_startup_marker_distinguishes_first_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertFalse(store.has_started_before())
            store.mark_started()
            self.assertTrue(store.has_started_before())

    def test_intro_marker_is_persisted_separately_from_startup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertFalse(store.has_seen_intro())
            store.mark_intro_seen()
            self.assertTrue(store.has_seen_intro())


    def test_update_preferences_default_and_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)

            self.assertTrue(store.load_update_checks_enabled())
            self.assertIsNone(store.load_last_update_check())
            self.assertIsNone(store.load_dismissed_update_commit())

            store.save_update_checks_enabled(False)
            store.save_last_update_check(1234.5)
            store.save_dismissed_update_commit("abc123")

            self.assertFalse(store.load_update_checks_enabled())
            self.assertEqual(store.load_last_update_check(), 1234.5)
            self.assertEqual(store.load_dismissed_update_commit(), "abc123")

            store.save_dismissed_update_commit(None)
            self.assertIsNone(store.load_dismissed_update_commit())

    def test_invalid_update_preferences_fall_back_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                '{"update_checks_enabled": "yes", "last_update_check": "oops", '
                '"dismissed_update_commit": 123}\n',
                encoding="utf-8",
            )
            store = ConfigStore(path)

            self.assertTrue(store.load_update_checks_enabled())
            self.assertIsNone(store.load_last_update_check())
            self.assertIsNone(store.load_dismissed_update_commit())

    def test_update_channel_defaults_to_releases_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")

            self.assertEqual(store.load_update_channel(), "release")

            store.save_update_channel("main")
            self.assertEqual(store.load_update_channel(), "main")

            store.save_update_channel("release")
            self.assertEqual(store.load_update_channel(), "release")

            with self.assertRaises(ValueError):
                store.save_update_channel("nightly")
            self.assertEqual(store.load_update_channel(), "release")

    def test_unknown_update_channel_falls_back_to_releases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for raw in ('"nightly"', "true", '""'):
                path.write_text(
                    f'{{"update_channel": {raw}}}\n', encoding="utf-8"
                )
                self.assertEqual(ConfigStore(path).load_update_channel(), "release")

    def test_bond_state_defaults_round_trips_and_migrates_old_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)

            self.assertEqual(store.load_bond_state(), BondState())

            store.save_bond_state(BondState(level=3, xp=210))
            self.assertEqual(
                store.load_bond_state(),
                BondState(level=3, xp=210),
            )

            path.write_text(
                '{"bond_level": 1, "bond_points": 2}\n',
                encoding="utf-8",
            )
            self.assertEqual(
                store.load_bond_state(),
                BondState(level=1, xp=240),
            )

            path.write_text('{"bond_phases": 4}\n', encoding="utf-8")
            self.assertEqual(
                store.load_bond_state(),
                BondState(level=2, xp=0),
            )

    def test_saves_quarantine_malformed_config_without_clobbering_backups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            malformed = '{"volume": 0.4, "bond_level": 8, "bond_xp": 300,'
            path.write_text(malformed, encoding="utf-8")
            store = ConfigStore(path)

            self.assertEqual(store.load_bond_state(), BondState())
            self.assertEqual(path.read_text(encoding="utf-8"), malformed)

            store.save_bond_state(BondState(level=2, xp=10))

            backups = list(path.parent.glob("config.json.corrupt-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), malformed)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"bond_level": 2, "bond_xp": 10},
            )

            non_object_json = "[]"
            path.write_text(non_object_json, encoding="utf-8")
            store.save_volume(0.5)

            backups = list(path.parent.glob("config.json.corrupt-*"))
            self.assertEqual(len(backups), 2)
            self.assertEqual(
                {backup.read_text(encoding="utf-8") for backup in backups},
                {malformed, non_object_json},
            )
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"volume": 0.5},
            )

    def test_reset_position_preserves_malformed_config_for_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            malformed = '{"bond_level": 8, "bond_xp": 300, '
            path.write_text(malformed, encoding="utf-8")

            ConfigStore(path).reset_position()

            self.assertFalse(path.exists())
            backups = list(path.parent.glob("config.json.corrupt-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), malformed)

    def test_permission_error_does_not_trigger_corrupt_config_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            contents = '{"bond_level": 8, "bond_xp": 300}\n'
            path.write_text(contents, encoding="utf-8")
            store = ConfigStore(path)

            with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    store.load_bond_state()
                with self.assertRaises(PermissionError):
                    store.save_bond_state(BondState(level=2, xp=10))

            self.assertEqual(path.read_text(encoding="utf-8"), contents)
            self.assertEqual(list(path.parent.glob("config.json.corrupt-*")), [])

    def test_pocket_hover_delay_defaults_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertEqual(store.load_pocket_hover_delay_ms(), 2000)
            for delay in (0, 1500, 2000, 3000):
                store.save_pocket_hover_delay_ms(delay)
                self.assertEqual(store.load_pocket_hover_delay_ms(), delay)

    def test_unsupported_pocket_hover_delay_reads_as_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for raw in (2500, -1, True, "2000", None):
                path.write_text(json.dumps({"pocket_hover_delay_ms": raw}))
                self.assertEqual(ConfigStore(path).load_pocket_hover_delay_ms(), 2000)

    def test_saving_an_unsupported_delay_stores_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            ConfigStore(path).save_pocket_hover_delay_ms(2500)
            self.assertEqual(json.loads(path.read_text())["pocket_hover_delay_ms"], 2000)


if __name__ == "__main__":
    unittest.main()
