import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
