"""Own the optional GNOME helper's lifetime on the session bus."""

from collections.abc import Callable
import logging


class GnomeHelperLifecycle:
    """Reconnect dependents before requesting the helper's semantic snapshot.

    Gio delivers owner changes on the GLib main loop. Failed attachment retries
    use one backoff timer; a successful attachment has no timer or polling.
    """

    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = BUS_NAME
    SYNC_SIGNAL_NAME = "SyncStateRequested"

    def __init__(
        self,
        *,
        on_available: Callable[[], bool],
        on_unavailable: Callable[[], None],
        logger: logging.Logger | None = None,
    ) -> None:
        self._on_available = on_available
        self._on_unavailable = on_unavailable
        self._logger = logger or logging.getLogger(__name__)
        self._gio = None
        self._watch_id = None
        self._running = False
        self._owner: str | None = None
        self._owner_known = False
        self._retry_source_id = None
        self._retry_delay = 1
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._owner is not None

    @staticmethod
    def _load_gio():
        from gi.repository import Gio

        return Gio

    @staticmethod
    def _load_glib():
        from gi.repository import GLib

        return GLib

    def start(self) -> bool:
        if self._running:
            return True
        try:
            self._gio = self._load_gio()
            connection = self._gio.bus_get_sync(self._gio.BusType.SESSION, None)
            if connection is None:
                return False
            self._running = True
            self._watch_id = self._gio.bus_watch_name_on_connection(
                connection,
                self.BUS_NAME,
                self._gio.BusNameWatcherFlags.NONE,
                self._appeared,
                self._vanished,
            )
            if not self._watch_id:
                self.stop()
                return False
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._logger.debug("GNOME helper watcher unavailable: %s", self.last_error)
            self.stop()
            return False

    def stop(self) -> None:
        self._running = False
        self._cancel_retry()
        if self._watch_id is not None:
            self._gio.bus_unwatch_name(self._watch_id)
        self._watch_id = None
        self._owner = None
        self._owner_known = False

    def _appeared(self, connection, _name, owner) -> None:
        if not self._running or owner == self._owner:
            return
        self._cancel_retry()
        if self._owner is not None:
            self._on_unavailable()
        self._owner = owner
        self._owner_known = True
        self._attempt_attachment(connection, owner)

    def _attempt_attachment(self, connection, owner) -> None:
        if not self._running or owner != self._owner:
            return
        # Subscriptions are attached before the request. The helper replies
        # using existing signals; a snapshot never synthesizes a typing pulse.
        try:
            if not self._on_available():
                self._schedule_retry(connection, owner)
                return
            if not self._running or owner != self._owner:
                return
            sent = connection.emit_signal(
                owner,
                self.OBJECT_PATH,
                self.INTERFACE_NAME,
                self.SYNC_SIGNAL_NAME,
                None,
            )
            if sent is False:
                raise RuntimeError("snapshot request was not sent")
            self.last_error = None
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._logger.debug("GNOME helper attachment/sync unavailable: %s", exc)
            self._schedule_retry(connection, owner)

    def _schedule_retry(self, connection, owner) -> None:
        if (not self._running or owner != self._owner
                or self._retry_source_id is not None):
            return

        def retry():
            self._retry_source_id = None
            self._attempt_attachment(connection, owner)
            return False

        self._retry_source_id = self._load_glib().timeout_add_seconds(
            self._retry_delay, retry,
        )
        self._retry_delay = min(self._retry_delay * 2, 30)

    def _cancel_retry(self) -> None:
        if self._retry_source_id is not None:
            self._load_glib().source_remove(self._retry_source_id)
        self._retry_source_id = None
        self._retry_delay = 1

    def _vanished(self, _connection, _name) -> None:
        if not self._running or (self._owner_known and self._owner is None):
            return
        self._cancel_retry()
        self._owner = None
        self._owner_known = True
        self._on_unavailable()
