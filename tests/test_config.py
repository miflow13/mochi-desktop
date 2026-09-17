import tempfile
import unittest
from pathlib import Path

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
            self.assertEqual(ConfigStore.DEFAULT_SIZE, 96)
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


if __name__ == "__main__":
    unittest.main()
