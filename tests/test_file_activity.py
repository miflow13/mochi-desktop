import unittest
from unittest.mock import Mock

from mochi.file_activity import DownloadsActivityBackend, FileActivityMonitor


class _Backend:
    def __init__(self, name: str) -> None:
        self.name = name
        self.last_error = None

    def stop(self) -> None:
        pass


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
