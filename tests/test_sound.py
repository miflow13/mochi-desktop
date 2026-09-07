import tempfile
import unittest
from pathlib import Path

from mochi.sound import SoundEvent, SoundManager


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, float]] = []

    def play(self, path: Path, volume: float) -> None:
        self.calls.append((path, volume))


class SoundManagerTests(unittest.TestCase):
    def test_missing_placeholder_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = SoundManager(asset_root=Path(directory), backend=FakeBackend())
            self.assertFalse(manager.play(SoundEvent.PET))

    def test_volume_and_mute_apply_globally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pet.ogg").touch()
            backend = FakeBackend()
            manager = SoundManager(volume=0.4, asset_root=root, backend=backend)
            self.assertTrue(manager.play(SoundEvent.PET))
            self.assertEqual(backend.calls, [(root / "pet.ogg", 0.4)])

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

    def test_volume_is_clamped(self) -> None:
        manager = SoundManager(volume=9, backend=FakeBackend())
        self.assertEqual(manager.volume, 1.0)
        manager.set_volume(-1)
        self.assertEqual(manager.volume, 0.0)


if __name__ == "__main__":
    unittest.main()
