import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.developer_shortcut import GnomeShellDeveloperShortcutBackend


class DeveloperShortcutBackendTests(unittest.TestCase):
    def test_subscribes_without_requiring_current_shell_name_owner(self) -> None:
        connection = SimpleNamespace(
            signal_subscribe=Mock(return_value=7),
            signal_unsubscribe=Mock(),
        )
        fake_gio = SimpleNamespace(
            BusType=SimpleNamespace(SESSION=1),
            DBusSignalFlags=SimpleNamespace(NONE=0),
            bus_get_sync=Mock(return_value=connection),
        )

        backend = GnomeShellDeveloperShortcutBackend()
        callback = Mock()

        with patch.object(backend, "_load_gio", return_value=fake_gio):
            self.assertTrue(backend.start(callback))

        self.assertTrue(backend.active)
        args = connection.signal_subscribe.call_args.args
        self.assertEqual(args[0], backend.BUS_NAME)
        self.assertEqual(args[1], backend.INTERFACE_NAME)
        self.assertEqual(args[2], backend.SIGNAL_NAME)
        self.assertEqual(args[3], backend.OBJECT_PATH)


if __name__ == "__main__":
    unittest.main()
