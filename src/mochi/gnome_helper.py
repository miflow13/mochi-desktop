"""Own the optional GNOME helper's lifetime on the session bus."""

from collections.abc import Callable
import logging


class GnomeHelperLifecycle:
    """Reconnect dependents before requesting the helper's semantic snapshot.

    Gio delivers owner changes on the GLib main loop. No polling, input data,
    or application identities are needed to recover from a late Shell helper.
    """

    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = BUS_NAME
    SYNC_SIGNAL_NAME = "SyncStateRequested"

    def __init__(
        self,
        *,
        on_available: Callable[[], None],
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
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._owner is not None

    @staticmethod
    def _load_gio():
        from gi.repository import Gio

        return Gio

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
        if self._watch_id is not None:
            self._gio.bus_unwatch_name(self._watch_id)
        self._watch_id = None
        self._owner = None
        self._owner_known = False

    def _appeared(self, connection, _name, owner) -> None:
        if not self._running or owner == self._owner:
            return
        if self._owner is not None:
            self._on_unavailable()
        self._owner = owner
        self._owner_known = True
        self._on_available()
        # Subscriptions are attached before the request. The helper replies
        # using existing signals; a snapshot never synthesizes a typing pulse.
        try:
            connection.emit_signal(
                owner,
                self.OBJECT_PATH,
                self.INTERFACE_NAME,
                self.SYNC_SIGNAL_NAME,
                None,
            )
        except Exception as exc:
            self._logger.debug("GNOME helper state sync unavailable: %s", exc)

    def _vanished(self, _connection, _name) -> None:
        if not self._running or (self._owner_known and self._owner is None):
            return
        self._owner = None
        self._owner_known = True
        self._on_unavailable()
