import tempfile
import unittest
from pathlib import Path

from mochi.sound import SoundEvent, SoundManager


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, float]] = []

    def play(self, path: Path, volume: float) -> None:
        self.calls.append((path, volume))


class FakePitchBackend(FakeBackend):\n    def __init__(self) -> None:\n        super().__init__()\n        self.pitched_calls: list[tuple[Path, float, float, int]] = []\n\n    def play_pitched(\n        self, path: Path, volume: float, pitch_ratio: float, source_rate: int\n    ) -> None:\n        self.pitched_calls.append((path, volume, pitch_ratio, source_rate))\n\n\nclass SoundManagerTests(unittest.TestCase):
    def test_missing_placeholder_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = SoundManager(asset_root=Path(directory), backend=FakeBackend())
            self.assertFalse(manager.play(SoundEvent.PET))

    def test_volume_and_mute_apply_globally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pet.wav").touch()
            backend = FakeBackend()
            manager = SoundManager(volume=0.4, asset_root=root, backend=backend)
            self.assertTrue(manager.play(SoundEvent.PET))
            self.assertEqual(backend.calls, [(root / "pet.wav", 0.4)])

            manager.set_muted(True)
            self.assertFalse(manager.play(SoundEvent.PET))
            self.assertEqual(len(backend.calls), 1)

    def test_level_up_hook_uses_registered_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "level_up.ogg").touch()
            backend = FakeBackend()
            manager = SoundManager(asset_root=root, backend=backend)
            self.assertTrue(manager.play_level_up())
            self.assertEqual(backend.calls[0][0].name, "level_up.ogg")

    def test_lifecycle_sounds_use_subtle_event_gain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "spawn.ogg").touch()
            (root / "exit.ogg").touch()
            backend = FakeBackend()
            manager = SoundManager(volume=0.6, asset_root=root, backend=backend)

            self.assertTrue(manager.play(SoundEvent.SPAWN))
            self.assertTrue(manager.play(SoundEvent.EXIT))
            self.assertEqual(backend.calls[0][0].name, "spawn.ogg")
            self.assertAlmostEqual(backend.calls[0][1], 0.21)
            self.assertEqual(backend.calls[1][0].name, "exit.ogg")
            self.assertAlmostEqual(backend.calls[1][1], 0.168)

    def test_context_menu_sound_is_intentionally_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "menu_open.ogg").touch()
            backend = FakeBackend()
            manager = SoundManager(volume=0.6, asset_root=root, backend=backend)

            self.assertTrue(manager.play(SoundEvent.MENU_OPEN))
            self.assertEqual(backend.calls[0][0].name, "menu_open.ogg")
            self.assertAlmostEqual(backend.calls[0][1], 0.132)

    def test_volume_is_clamped(self) -> None:
        manager = SoundManager(volume=9, backend=FakeBackend())
        self.assertEqual(manager.volume, 1.0)
        manager.set_volume(-1)
        self.assertEqual(manager.volume, 0.0)


if __name__ == "__main__":
    unittest.main()
