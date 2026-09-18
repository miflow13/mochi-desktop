"""Observe suspend and the current desktop session's lock state via logind."""

from __future__ import annotations

from collections.abc import Callable
import logging


class SessionSignalMonitor:
    """Coalesce suspend/lock into one away -> returned lifecycle transition.

    Resolve the real session path: the /session/auto convenience object does
    not emit property changes itself. No login, lock or power action is issued.
    """

    BUS_NAME = "org.freedesktop.login1"
    MANAGER_PATH = "/org/freedesktop/login1"
    MANAGER_INTERFACE = "org.freedesktop.login1.Manager"
    SESSION_INTERFACE = "org.freedesktop.login1.Session"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

    def __init__(
        self,
        *,
        on_away: Callable[[], None],
        on_returned: Callable[[], None],
        logger: logging.Logger | None = None,
        gio_loader=None,
    ) -> None:
        self._on_away = on_away
        self._on_returned = on_returned
        self._logger = logger or logging.getLogger(__name__)
        self._gio_loader = gio_loader or self._load_gio
        self._connection = None
        self._subscriptions: list[int] = []
        self._session_path = None
        self._sleeping = False
        self._locked = False
        self._active = True
        self.blocked = False
        self.available = False

    @staticmethod
    def _load_gio():
        from gi.repository import Gio, GLib
        return Gio, GLib

    def start(self) -> bool:
        if self.available:
            return True
        try:
            self._gio, self._glib = self._gio_loader()
            self._connection = self._gio.bus_get_sync(self._gio.BusType.SYSTEM, None)
            reply = self._connection.call_sync(
                self.BUS_NAME, self.MANAGER_PATH, self.MANAGER_INTERFACE,
                "GetSession", self._glib.Variant("(s)", ("auto",)),
                self._glib.VariantType.new("(o)"),
                self._gio.DBusCallFlags.NONE, 1_000, None,
            )
            self._session_path = reply.unpack()[0]
            for interface, signal, path, arg0, callback in (
                (self.MANAGER_INTERFACE, "PrepareForSleep", self.MANAGER_PATH,
                 None, self._on_sleep),
                (self.PROPERTIES_INTERFACE, "PropertiesChanged", self._session_path,
                 self.SESSION_INTERFACE, self._on_session_changed),
            ):
                ident = self._connection.signal_subscribe(
                    self.BUS_NAME, interface, signal, path, arg0,
                    self._gio.DBusSignalFlags.NONE, callback,
                )
                self._subscriptions.append(ident)
            self._refresh_session()
            self.available = True
            self._reconcile()
            self._logger.debug("[session] baseline blocked=%s", self.blocked)
            return True
        except Exception as exc:
            self._logger.debug("[session] logind awareness unavailable: %s", exc)
            self.stop()
            return False

    def stop(self) -> None:
        self.available = False
        if self._connection is not None:
            for ident in self._subscriptions:
                self._connection.signal_unsubscribe(ident)
        self._subscriptions.clear()
        self._connection = None
        self._session_path = None
        self._sleeping = self._locked = self.blocked = False
        self._active = True

    def _refresh_session(self) -> None:
        reply = self._connection.call_sync(
            self.BUS_NAME, self._session_path, self.PROPERTIES_INTERFACE,
            "GetAll", self._glib.Variant("(s)", (self.SESSION_INTERFACE,)),
            self._glib.VariantType.new("(a{sv})"),
            self._gio.DBusCallFlags.NONE, 1_000, None,
        )
        properties = reply.unpack()[0]
        self._locked = bool(properties["LockedHint"])
        self._active = bool(properties["Active"])

    def _on_sleep(self, _bus, _sender, _path, _interface, _signal, parameters) -> None:
        if not self.available:
            return
        sleeping = parameters.unpack()[0]
        if not sleeping:
            try:
                # The screen may have locked while suspended. Read its current
                # state before allowing speech, regardless of signal ordering.
                self._refresh_session()
            except Exception as exc:
                self._logger.debug("[session] resume baseline unavailable: %s", exc)
                self._locked = True
        self._sleeping = sleeping
        self._reconcile()

    def _on_session_changed(
        self, _bus, _sender, _path, _interface, _signal, parameters
    ) -> None:
        if not self.available:
            return
        interface, changed, invalidated = parameters.unpack()
        if interface != self.SESSION_INTERFACE:
            return
        if "LockedHint" in changed:
            self._locked = bool(changed["LockedHint"])
        if "Active" in changed:
            self._active = bool(changed["Active"])
        if {"LockedHint", "Active"}.intersection(invalidated):
            try:
                self._refresh_session()
            except Exception as exc:
                self._logger.debug("[session] session baseline unavailable: %s", exc)
                self._locked = True
        self._reconcile()

    def _reconcile(self) -> None:
        blocked = self._sleeping or self._locked or not self._active
        if blocked == self.blocked:
            return
        self.blocked = blocked
        self._logger.debug("[session] %s", "away" if blocked else "returned")
        (self._on_away if blocked else self._on_returned)()
