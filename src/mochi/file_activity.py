"""Privacy-preserving file-browsing and download activity for Mochi.

The GNOME Shell companion extension reduces focused-window information to two
zero-payload semantic signals: ``FileBrowsingStarted`` and
``FileBrowsingStopped``. Mochi never receives application IDs, window titles,
file names, folder names, or paths from that signal.

Download awareness watches only the user's XDG Downloads directory for generic
filesystem activity. The Gio callback deliberately ignores the file objects it
receives and retains only a short-lived timestamp meaning "download-directory
activity happened recently".
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import time

from mochi.helper_connection import HelperConnection


class GnomeShellFileContextBackend:
    """Receive semantic file-browser focus state from the Mochi Shell extension."""

    name = "GNOME Shell file-browsing context"
    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    START_SIGNAL_NAME = "FileBrowsingStarted"
    STOP_SIGNAL_NAME = "FileBrowsingStopped"

    def __init__(self) -> None:
        self._helper = None
        self.last_error = None
        self._on_started = None
        self._on_stopped = None

    @property
    def active(self) -> bool:
        return self._helper is not None and self._helper.active

    @staticmethod
    def _load_gio():
        import gi

        from gi.repository import Gio, GLib

        return Gio, GLib

    def start(
        self, on_started: Callable[[], None], on_stopped: Callable[[], None]
    ) -> bool:
        if self._helper is not None:
            return True
        self._on_started = on_started
        self._on_stopped = on_stopped
        self._helper = HelperConnection(
            self._load_gio,
            {
                self.START_SIGNAL_NAME: self._on_started_signal,
                self.STOP_SIGNAL_NAME: self._on_stopped_signal,
            },
            on_state=lambda state: (
                self._on_started_signal() if state[1] else self._on_stopped_signal()
            ),
            on_lost=self._on_stopped_signal,
        )
        if self._helper.start():
            self.last_error = None
            return True
        self.last_error = self._helper.last_error
        self.stop()
        return False

    def stop(self) -> None:
        if self._helper is not None:
            self._helper.stop()
            self._helper = None
        self._on_started = None
        self._on_stopped = None

    def _on_started_signal(self, *_ignored) -> None:
        callback = self._on_started
        if callback is not None:
            callback()

    def _on_stopped_signal(self, *_ignored) -> None:
        callback = self._on_stopped
        if callback is not None:
            callback()


class DownloadsActivityBackend:
    """Reduce generic activity in the XDG Downloads directory to a pulse."""

    name = "Downloads directory activity"

    def __init__(self, downloads_path: Path | None = None) -> None:
        self._downloads_path = downloads_path
        self._monitor = None
        self._handler_id: int | None = None
        self._on_activity: Callable[[], None] | None = None
        self._interesting_events: frozenset[object] = frozenset()
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._monitor is not None

    @staticmethod
    def _load_gio():
        import gi

        from gi.repository import Gio, GLib

        return Gio, GLib

    def start(self, on_activity: Callable[[], None]) -> bool:
        if self.active:
            return True

        self.last_error = None
        try:
            Gio, GLib = self._load_gio()
            downloads_path = self._downloads_path or self._default_downloads_path(GLib)
            if not downloads_path.is_dir():
                self.last_error = "Downloads directory is unavailable"
                return False

            directory = Gio.File.new_for_path(str(downloads_path))
            monitor = directory.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            if monitor is None:
                self.last_error = "Downloads directory monitor could not be created"
                return False

            event_names = (
                "CHANGED",
                "CHANGES_DONE_HINT",
                "CREATED",
                "MOVED",
                "MOVED_IN",
                "RENAMED",
            )
            self._interesting_events = frozenset(
                event
                for name in event_names
                if (event := getattr(Gio.FileMonitorEvent, name, None)) is not None
            )
            self._monitor = monitor
            self._on_activity = on_activity
            self._handler_id = int(monitor.connect("changed", self._on_changed))
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

        return True

    def stop(self) -> None:
        if self._monitor is not None:
            if self._handler_id is not None:
                try:
                    self._monitor.disconnect(self._handler_id)
                except Exception:
                    pass
            try:
                self._monitor.cancel()
            except Exception:
                pass

        self._handler_id = None
        self._monitor = None
        self._on_activity = None
        self._interesting_events = frozenset()

    def _on_changed(
        self,
        _monitor,
        _file,
        _other_file,
        event_type,
    ) -> None:
        # PRIVACY BOUNDARY: intentionally ignore the Gio.File arguments. Mochi
        # never reads or stores a file name, path, URL, or file contents here.
        if event_type not in self._interesting_events:
            return
        callback = self._on_activity
        if callback is not None:
            callback()

    @staticmethod
    def _default_downloads_path(GLib) -> Path:
        try:
            value = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        except Exception:
            value = None
        return Path(value) if value else Path.home() / "Downloads"


class FileActivityMonitor:
    """Merge file-browser focus and recent download activity into one state."""

    POLL_INTERVAL_MS = 500
    DOWNLOAD_HOLD_SECONDS = 8.0

    def __init__(
        self,
        *,
        on_file_activity_started: Callable[[], None],
        on_file_activity_stopped: Callable[[], None],
        logger: logging.Logger | None = None,
        file_context_backend: GnomeShellFileContextBackend | None = None,
        downloads_backend: DownloadsActivityBackend | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._on_file_activity_started = on_file_activity_started
        self._on_file_activity_stopped = on_file_activity_stopped
        self._logger = logger or logging.getLogger(__name__)
        self._file_context_backend = file_context_backend or GnomeShellFileContextBackend()
        self._downloads_backend = downloads_backend or DownloadsActivityBackend()
        self._clock = clock
        self._source_id: int | None = None
        self._file_browser_active = False
        self._download_active_until: float | None = None
        self.file_activity_active = False
        self.file_context_available = False
        self.downloads_available = False
        self.available = False

    @property
    def backend_names(self) -> tuple[str, ...]:
        names: list[str] = []
        if self.file_context_available:
            names.append(self._file_context_backend.name)
        if self.downloads_available:
            names.append(self._downloads_backend.name)
        return tuple(names)

    def start(self) -> bool:
        if self.available:
            return True

        self.file_context_available = self._file_context_backend.start(
            self._on_file_browser_started,
            self._on_file_browser_stopped,
        )
        if not self.file_context_available:
            self._logger.debug(
                "File-browser awareness unavailable via %s: %s",
                self._file_context_backend.name,
                self._file_context_backend.last_error or "unknown error",
            )

        self.downloads_available = self._downloads_backend.start(
            self._on_download_activity,
        )
        if not self.downloads_available:
            self._logger.debug(
                "Download awareness unavailable via %s: %s",
                self._downloads_backend.name,
                self._downloads_backend.last_error or "unknown error",
            )

        self.available = self.file_context_available or self.downloads_available
        if not self.available:
            return False

        try:
            from gi.repository import GLib

            self._source_id = GLib.timeout_add(
                self.POLL_INTERVAL_MS,
                self._poll,
            )
        except Exception as exc:
            self._logger.debug("File activity timer unavailable: %s", exc)
            self._file_context_backend.stop()
            self._downloads_backend.stop()
            self.file_context_available = False
            self.downloads_available = False
            self.available = False
            return False

        self._logger.info(
            "File activity awareness enabled via %s",
            " + ".join(self.backend_names),
        )
        return True

    def stop(self) -> None:
        if self._source_id is not None:
            try:
                from gi.repository import GLib

                GLib.source_remove(self._source_id)
            except Exception:
                pass

        self._source_id = None
        self._file_context_backend.stop()
        self._downloads_backend.stop()
        self._file_browser_active = False
        self._download_active_until = None
        self.file_activity_active = False
        self.file_context_available = False
        self.downloads_available = False
        self.available = False

    def _on_file_browser_started(self) -> None:
        self._file_browser_active = True
        self._logger.debug("File-browsing activity active")
        self._refresh_activity_state()

    def _on_file_browser_stopped(self) -> None:
        self._file_browser_active = False
        self._logger.debug("File-browsing activity inactive")
        self._refresh_activity_state()

    def _on_download_activity(self) -> None:
        # Retain only an expiry timestamp. No path/file object reaches this API.
        self._download_active_until = self._clock() + self.DOWNLOAD_HOLD_SECONDS
        self._logger.debug("Download-directory activity detected")
        self._refresh_activity_state()

    def _poll(self) -> bool:
        if (
            self._download_active_until is not None
            and self._clock() >= self._download_active_until
        ):
            self._download_active_until = None
            self._refresh_activity_state()
        return True

    def _refresh_activity_state(self) -> None:
        now = self._clock()
        download_active = (
            self._download_active_until is not None
            and now < self._download_active_until
        )
        active = self._file_browser_active or download_active
        if active == self.file_activity_active:
            return

        self.file_activity_active = active
        if active:
            self._on_file_activity_started()
        else:
            self._on_file_activity_stopped()
