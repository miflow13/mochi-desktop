"""Ask the GNOME helper whether the pointer is near the area under Mochi.

Mochi's buddy runs on XWayland, and a Wayland compositor only tells XWayland
where the pointer is while it is over XWayland's own windows. So Mochi cannot
notice the pointer approaching on its own. The optional GNOME helper can: Mochi
sends it a zone relative to the buddy window, and the helper answers with a
single boolean ``PointerNearChanged`` signal. Coordinates never leave GNOME
Shell.

``supported`` stays ``None`` until the helper answers, becomes ``False`` when
no helper (or an older one without this method) is running, and callers fall
back to hovering Mochi in that case.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from mochi.voice_control_model import Rect


BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
INTERFACE = BUS_NAME
SIGNAL_NAME = "PointerNearChanged"
CALL_TIMEOUT_MS = 1_000


def _session_bus() -> Gio.DBusConnection:
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def _watch_name(connection, appeared, vanished) -> int:
    return Gio.bus_watch_name_on_connection(
        connection, BUS_NAME, Gio.BusNameWatcherFlags.NONE, appeared, vanished
    )


class PointerProximityMonitor:
    def __init__(
        self,
        *,
        on_near_changed: Callable[[bool], None],
        logger: logging.Logger | None = None,
        connection_factory: Callable[[], Gio.DBusConnection] = _session_bus,
        watch_name: Callable[..., int] = _watch_name,
    ) -> None:
        self._on_near_changed = on_near_changed
        self._logger = logger or logging.getLogger(__name__)
        self._connection_factory = connection_factory
        self._watch_name = watch_name
        self._connection = None
        self._subscription_id: int | None = None
        self._watch_id = 0
        self._sent: tuple[int, ...] | None = None
        self.supported: bool | None = None

    def start(self) -> bool:
        try:
            self._connection = self._connection_factory()
            self._subscription_id = self._connection.signal_subscribe(
                BUS_NAME,
                INTERFACE,
                SIGNAL_NAME,
                OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_signal,
            )
            # A restarted helper (GNOME Shell restart, extension re-enabled,
            # or a helper that starts after Mochi) has no zone; resend it.
            self._watch_id = self._watch_name(
                self._connection,
                lambda *_args: self._on_helper_appeared(),
                lambda *_args: self._on_helper_vanished(),
            )
        except GLib.Error as error:
            self._logger.debug("Pointer proximity unavailable: %s", error.message)
            self._connection = None
            self.supported = False
            return False
        return True

    def stop(self) -> None:
        if self._connection is None:
            return
        self.set_zone(None, owner_width=1)
        if self._watch_id:
            Gio.bus_unwatch_name(self._watch_id)
            self._watch_id = 0
        if self._subscription_id:
            self._connection.signal_unsubscribe(self._subscription_id)
        self._subscription_id = None
        self._connection = None

    def set_zone(self, zone: Rect | None, *, owner_width: float) -> None:
        """Watch ``zone`` (relative to Mochi's window), or stop watching."""
        if self._connection is None:
            return
        if zone is None:
            if self._sent is not None:
                self._sent = None
                self._call("ClearProximityZone", None)
            return
        values = (
            round(zone.x),
            round(zone.y),
            round(zone.width),
            round(zone.height),
            max(1, round(owner_width)),
        )
        if values == self._sent:
            return
        self._sent = values
        self._call("SetProximityZone", GLib.Variant("(iiiii)", values))

    def _call(self, method: str, parameters) -> None:
        self._connection.call(
            BUS_NAME,
            OBJECT_PATH,
            INTERFACE,
            method,
            parameters,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            CALL_TIMEOUT_MS,
            None,
            self._on_call_finished,
        )

    def _on_call_finished(self, connection, result) -> None:
        try:
            connection.call_finish(result)
        except GLib.Error as error:
            if self.supported is not False:
                self._logger.debug(
                    "Pointer proximity via GNOME helper unavailable: %s", error.message
                )
            self.supported = False
            self._sent = None  # retry on the next zone once a helper appears
            return
        self.supported = True

    def _on_helper_appeared(self) -> None:
        self._sent = None  # the next zone update is sent again
        if self.supported is False:
            self.supported = None  # unknown again: try promptly, not on the slow retry

    def _on_helper_vanished(self) -> None:
        self._sent = None
        self.supported = False
        self._on_near_changed(False)

    def _on_signal(self, _connection, _sender, _path, _interface, _signal, parameters) -> None:
        (near,) = parameters.unpack()
        self.supported = True
        self._on_near_changed(bool(near))
