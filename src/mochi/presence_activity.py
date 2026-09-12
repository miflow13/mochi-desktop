"""Privacy-preserving user presence events for Mochi.

The optional GNOME Shell companion extension emits zero-payload ``UserIdle``
and ``UserActive`` signals derived from Mutter's server-global idle monitor.
Mochi receives only those semantic state transitions; no key, pointer, window,
or application details cross the D-Bus boundary.
"""

from __future__ import annotations

from collections.abc import Callable
import logging


class GnomeShellPresenceBackend:
    """Receive semantic idle/active transitions from the Mochi Shell extension."""

    name = "GNOME Shell user presence"
    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    IDLE_SIGNAL_NAME = "UserIdle"
    ACTIVE_SIGNAL_NAME = "UserActive"

    def __init__(self) -> None:
        self._connection = None
        self._idle_subscription_id: int | None = None
        self._active_subscription_id: int | None = None
        self._on_user_idle: Callable[[], None] | None = None
        self._on_user_active: Callable[[], None] | None = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return (
            self._connection is not None
            and self._idle_subscription_id is not None
            and self._active_subscription_id is not None
        )

    @staticmethod
    def _load_gio():
        import gi

        from gi.repository import Gio, GLib

        return Gio, GLib

    def start(
        self,
        on_user_idle: Callable[[], None],
        on_user_active: Callable[[], None],
    ) -> bool:
        if self.active:
            return True

        self.last_error = None
        try:
            Gio, GLib = self._load_gio()
            connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if connection is None:
                self.last_error = "session D-Bus connection is unavailable"
                return False

            reply = connection.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "NameHasOwner",
                GLib.Variant("(s)", (self.BUS_NAME,)),
                None,
                Gio.DBusCallFlags.NONE,
                1_000,
                None,
            )
            has_owner = bool(reply.unpack()[0]) if reply is not None else False
            if not has_owner:
                self.last_error = "GNOME Shell activity extension is not active"
                return False

            self._connection = connection
            self._on_user_idle = on_user_idle
            self._on_user_active = on_user_active

            idle_id = connection.signal_subscribe(
                self.BUS_NAME,
                self.INTERFACE_NAME,
                self.IDLE_SIGNAL_NAME,
                self.OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_idle_signal,
            )
            active_id = connection.signal_subscribe(
                self.BUS_NAME,
                self.INTERFACE_NAME,
                self.ACTIVE_SIGNAL_NAME,
                self.OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_active_signal,
            )
            if not idle_id or not active_id:
                self.last_error = "presence signal subscription failed"
                if idle_id:
                    self._idle_subscription_id = int(idle_id)
                if active_id:
                    self._active_subscription_id = int(active_id)
                self.stop()
                return False

            self._idle_subscription_id = int(idle_id)
            self._active_subscription_id = int(active_id)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

        return True

    def stop(self) -> None:
        if self._connection is not None:
            for subscription_id in (
                self._idle_subscription_id,
                self._active_subscription_id,
            ):
                if subscription_id is None:
                    continue
                try:
                    self._connection.signal_unsubscribe(subscription_id)
                except Exception:
                    pass

        self._idle_subscription_id = None
        self._active_subscription_id = None
        self._connection = None
        self._on_user_idle = None
        self._on_user_active = None

    def _on_idle_signal(self, *_ignored) -> None:
        # PRIVACY BOUNDARY: the signal is zero-payload. Ignore all Gio callback
        # bookkeeping arguments and expose only the semantic presence event.
        callback = self._on_user_idle
        if callback is not None:
            callback()

    def _on_active_signal(self, *_ignored) -> None:
        callback = self._on_user_active
        if callback is not None:
            callback()


class PresenceActivityMonitor:
    """Small lifecycle wrapper around the GNOME Shell presence backend."""

    def __init__(
        self,
        *,
        on_user_idle: Callable[[], None],
        on_user_active: Callable[[], None],
        logger: logging.Logger | None = None,
        backend: GnomeShellPresenceBackend | None = None,
    ) -> None:
        self._on_user_idle = on_user_idle
        self._on_user_active = on_user_active
        self._logger = logger or logging.getLogger(__name__)
        self._backend = backend or GnomeShellPresenceBackend()
        self.available = False
        self._user_idle = False

    @property
    def backend_name(self) -> str | None:
        return self._backend.name if self.available else None

    def start(self) -> bool:
        if self.available:
            return True

        self.available = self._backend.start(
            self._idle,
            self._active,
        )
        if self.available:
            self._logger.info(
                "Presence awareness enabled via %s",
                self._backend.name,
            )
        else:
            self._logger.debug(
                "Presence awareness unavailable via %s: %s",
                self._backend.name,
                self._backend.last_error or "unknown error",
            )
        return self.available

    def _idle(self) -> None:
        if not self._user_idle:
            self._user_idle = True
            self._on_user_idle()

    def _active(self) -> None:
        if self._user_idle:
            self._user_idle = False
            self._on_user_active()

    def on_gnome_helper_unavailable(self) -> None:
        self.stop()
        # Return to the startup assumption when global idle information is lost.
        self._active()

    def stop(self) -> None:
        if not self.available:
            return
        self._backend.stop()
        self.available = False
