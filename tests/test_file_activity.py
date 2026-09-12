import unittest
from unittest.mock import Mock

from mochi.file_activity import DownloadsActivityBackend, FileActivityMonitor


class _Backend:
    def __init__(self, name: str) -> None:
        self.name = name
        self.last_error = None

    def stop(self) -> None:
        pass


class _ReconnectableBackend(_Backend):
    def __init__(self, name: str, *, available: bool) -> None:
        super().__init__(name)
        self.available = available
        self.start_calls = 0
        self.stop_calls = 0
        self.on_started = None
        self.on_stopped = None

    def start(self, on_started, on_stopped) -> bool:
        self.start_calls += 1
        if not self.available:
            self.last_error = "unavailable"
            return False
        self.on_started = on_started
        self.on_stopped = on_stopped
        self.last_error = None
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self.on_started = None
        self.on_stopped = None


class FileActivityMonitorTests(unittest.TestCase):
    def _monitor(self, now):
        return FileActivityMonitor(
            on_file_activity_started=Mock(),
            on_file_activity_stopped=Mock(),
            file_context_backend=_Backend("file context"),
            downloads_backend=_Backend("downloads"),
            clock=lambda: now[0],
        )

    def test_file_browser_start_and_stop_emit_one_semantic_session(self) -> None:
        now = [10.0]
        monitor = self._monitor(now)

        monitor._on_file_browser_started()
        monitor._on_file_browser_started()
        self.assertTrue(monitor.file_activity_active)
        monitor._on_file_activity_started.assert_called_once_with()

        monitor._on_file_browser_stopped()
        self.assertFalse(monitor.file_activity_active)
        monitor._on_file_activity_stopped.assert_called_once_with()

    def test_download_activity_holds_searching_for_a_short_grace_period(self) -> None:
        now = [10.0]
        monitor = self._monitor(now)

        monitor._on_download_activity()
        self.assertTrue(monitor.file_activity_active)
        monitor._on_file_activity_started.assert_called_once_with()

        now[0] += monitor.DOWNLOAD_HOLD_SECONDS - 0.1
        monitor._poll()
        self.assertTrue(monitor.file_activity_active)
        monitor._on_file_activity_stopped.assert_not_called()

        now[0] += 0.2
        monitor._poll()
        self.assertFalse(monitor.file_activity_active)
        monitor._on_file_activity_stopped.assert_called_once_with()

    def test_repeated_download_activity_extends_the_grace_period(self) -> None:
        now = [10.0]
        monitor = self._monitor(now)

        monitor._on_download_activity()
        now[0] += 6.0
        monitor._on_download_activity()
        now[0] += 3.0
        monitor._poll()

        self.assertTrue(monitor.file_activity_active)
        monitor._on_file_activity_started.assert_called_once_with()
        monitor._on_file_activity_stopped.assert_not_called()

    def test_browser_stop_does_not_stop_searching_during_recent_download(self) -> None:
        now = [10.0]
        monitor = self._monitor(now)

        monitor._on_file_browser_started()
        monitor._on_download_activity()
        monitor._on_file_browser_stopped()

        self.assertTrue(monitor.file_activity_active)
        monitor._on_file_activity_stopped.assert_not_called()

    def test_file_context_reconnects_while_download_monitor_stays_running(self) -> None:
        now = [10.0]
        context = _ReconnectableBackend("file context", available=False)
        monitor = FileActivityMonitor(
            on_file_activity_started=Mock(),
            on_file_activity_stopped=Mock(),
            file_context_backend=context,
            downloads_backend=_Backend("downloads"),
            clock=lambda: now[0],
        )
        monitor.downloads_available = True
        monitor.available = True
        monitor._source_id = 42  # Existing Downloads expiry timer.

        self.assertFalse(monitor.on_gnome_helper_available())
        self.assertTrue(monitor.available)

        context.available = True
        self.assertTrue(monitor.on_gnome_helper_available())
        self.assertTrue(monitor.file_context_available)
        self.assertEqual(monitor._source_id, 42)
        context.on_started()
        context.on_started()
        monitor._on_file_activity_started.assert_called_once_with()

        monitor.on_gnome_helper_unavailable()
        self.assertFalse(monitor.file_context_available)
        self.assertTrue(monitor.available)
        monitor._on_file_activity_stopped.assert_called_once_with()

        self.assertTrue(monitor.on_gnome_helper_available())
        self.assertEqual(context.start_calls, 3)


class DownloadsActivityPrivacyTests(unittest.TestCase):
    def test_changed_callback_ignores_file_objects_and_emits_only_activity(self) -> None:
        event = object()
        callback = Mock()
        backend = DownloadsActivityBackend()
        backend._interesting_events = frozenset({event})
        backend._on_activity = callback

        class _ForbiddenFileObject:
            def __getattribute__(self, _name):
                raise AssertionError("file metadata must not be inspected")

        backend._on_changed(
            None,
            _ForbiddenFileObject(),
            _ForbiddenFileObject(),
            event,
        )

        callback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
