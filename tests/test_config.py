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


if __name__ == "__main__":
    unittest.main()
