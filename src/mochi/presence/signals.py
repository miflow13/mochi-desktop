"""Privacy-safe ambient signal helpers for the presence system."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import logging
import time

from .context import TypingIntensity


class TypingIntensityTracker:
    """Estimate broad typing intensity from anonymous event timestamps only."""

    def __init__(
        self,
        *,
        window_seconds: float = 10.0,
        medium_events_per_second: float = 1.5,
        high_events_per_second: float = 4.0,
        continuity_grace_seconds: float = 8.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = window_seconds
        self.medium_events_per_second = medium_events_per_second
        self.high_events_per_second = high_events_per_second
        self.continuity_grace_seconds = continuity_grace_seconds
        self._clock = clock
        self._events: deque[float] = deque()
        self._intensity = TypingIntensity.LOW
        self._level_since: float | None = None
        self._last_event_at: float | None = None
        self._stopped_at: float | None = None

    def record(self, now: float | None = None) -> TypingIntensity:
        timestamp = self._clock() if now is None else now
        if (
            self._stopped_at is not None
            and timestamp - self._stopped_at > self.continuity_grace_seconds
        ):
            self._events.clear()
            self._intensity = TypingIntensity.LOW
            self._level_since = timestamp
        self._stopped_at = None
        self._events.append(timestamp)
        self._last_event_at = timestamp
        self._prune(timestamp)
        self._update_level(timestamp)
        return self._intensity

    def stopped(self, now: float | None = None) -> None:
        self._stopped_at = self._clock() if now is None else now

    def snapshot(self, now: float | None = None) -> tuple[TypingIntensity, float]:
        timestamp = self._clock() if now is None else now
        if self._stopped_at is not None:
            if timestamp - self._stopped_at <= self.continuity_grace_seconds:
                sustained = (
                    0.0
                    if self._level_since is None
                    else max(0.0, timestamp - self._level_since)
                )
                return self._intensity, sustained
            self._events.clear()
            self._intensity = TypingIntensity.LOW
            self._level_since = timestamp
            self._stopped_at = None
        self._prune(timestamp)
        self._update_level(timestamp)
        sustained = 0.0 if self._level_since is None else max(0.0, timestamp - self._level_since)
        return self._intensity, sustained

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

    def _update_level(self, now: float) -> None:
        if not self._events:
            new_level = TypingIntensity.LOW
        else:
            oldest = self._events[0]
            observed_span = max(1.0, min(self.window_seconds, now - oldest + 1.0))
            rate = len(self._events) / observed_span
            if rate >= self.high_events_per_second:
                new_level = TypingIntensity.HIGH
            elif rate >= self.medium_events_per_second:
                new_level = TypingIntensity.MEDIUM
            else:
                new_level = TypingIntensity.LOW
        if new_level is not self._intensity:
            self._intensity = new_level
            self._level_since = now
        elif self._level_since is None:
            self._level_since = now


def _unpack(value):
    while hasattr(value, "unpack"):
        unpacked = value.unpack()
        if unpacked is value:
            break
        value = unpacked
    return value


class UPowerSignalAdapter:
    """Observe only battery percentage/charging transitions over system D-Bus."""

    BUS_NAME = "org.freedesktop.UPower"
    OBJECT_PATH = "/org/freedesktop/UPower/devices/DisplayDevice"
    INTERFACE = "org.freedesktop.UPower.Device"
    CHARGING_STATES = frozenset((1, 5))

    def __init__(
        self,
        *,
        on_battery_low: Callable[[float], None],
        on_charging_started: Callable[[float | None], None],
        low_threshold: float = 20.0,
        logger: logging.Logger | None = None,
        gio_loader: Callable[[], object] | None = None,
    ) -> None:
        self._on_battery_low = on_battery_low
        self._on_charging_started = on_charging_started
        self.low_threshold = low_threshold
        self._logger = logger or logging.getLogger(__name__)
        self._gio_loader = gio_loader or self._load_gio
        self._proxy = None
        self._handler_id: int | None = None
        self.available = False
        self.percent: float | None = None
        self.charging: bool | None = None
        self.last_error: str | None = None

    @staticmethod
    def _load_gio():
        import gi
        from gi.repository import Gio
        return Gio

    def start(self) -> bool:
        if self.available:
            return True
        try:
            Gio = self._gio_loader()
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                self.BUS_NAME,
                self.OBJECT_PATH,
                self.INTERFACE,
                None,
            )
            self._refresh(emit=False)
            self._handler_id = int(
                self._proxy.connect("g-properties-changed", self._on_properties_changed)
            )
            self.available = True
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

    def stop(self) -> None:
        if self._proxy is not None and self._handler_id is not None:
            try:
                self._proxy.disconnect(self._handler_id)
            except Exception:
                pass
        self._handler_id = None
        self._proxy = None
        self.available = False

    def _on_properties_changed(self, *_ignored) -> None:
        self._refresh(emit=True)

    def _refresh(self, *, emit: bool) -> None:
        if self._proxy is None:
            return
        old_percent = self.percent
        old_charging = self.charging
        percent_value = self._proxy.get_cached_property("Percentage")
        state_value = self._proxy.get_cached_property("State")
        self.percent = None if percent_value is None else float(_unpack(percent_value))
        state = None if state_value is None else int(_unpack(state_value))
        self.charging = None if state is None else state in self.CHARGING_STATES
        if not emit:
            return
        if old_charging is False and self.charging is True:
            self._on_charging_started(self.percent)
        if (
            self.percent is not None
            and self.charging is False
            and old_percent is not None
            and old_percent > self.low_threshold >= self.percent
        ):
            self._on_battery_low(self.percent)


class NetworkSignalAdapter:
    """Observe only NetworkManager's broad connected/disconnected state."""

    BUS_NAME = "org.freedesktop.NetworkManager"
    OBJECT_PATH = "/org/freedesktop/NetworkManager"
    INTERFACE = "org.freedesktop.NetworkManager"

    def __init__(
        self,
        *,
        on_lost: Callable[[], None],
        on_restored: Callable[[], None],
        logger: logging.Logger | None = None,
        gio_loader: Callable[[], object] | None = None,
    ) -> None:
        self._on_lost = on_lost
        self._on_restored = on_restored
        self._logger = logger or logging.getLogger(__name__)
        self._gio_loader = gio_loader or self._load_gio
        self._proxy = None
        self._handler_id: int | None = None
        self.available = False
        self.connected: bool | None = None
        self.last_error: str | None = None

    @staticmethod
    def _load_gio():
        import gi
        from gi.repository import Gio
        return Gio

    def start(self) -> bool:
        if self.available:
            return True
        try:
            Gio = self._gio_loader()
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                self.BUS_NAME,
                self.OBJECT_PATH,
                self.INTERFACE,
                None,
            )
            self._refresh(emit=False)
            self._handler_id = int(
                self._proxy.connect("g-properties-changed", self._on_properties_changed)
            )
            self.available = True
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

    def stop(self) -> None:
        if self._proxy is not None and self._handler_id is not None:
            try:
                self._proxy.disconnect(self._handler_id)
            except Exception:
                pass
        self._handler_id = None
        self._proxy = None
        self.available = False

    def _on_properties_changed(self, *_ignored) -> None:
        self._refresh(emit=True)

    def _refresh(self, *, emit: bool) -> None:
        if self._proxy is None:
            return
        old = self.connected
        state_value = self._proxy.get_cached_property("State")
        state = None if state_value is None else int(_unpack(state_value))
        # NetworkManager: 50+ means at least locally connected; 70 is global.
        self.connected = None if state is None else state >= 50
        if not emit or old is None or self.connected is None or old == self.connected:
            return
        if self.connected:
            self._on_restored()
        else:
            self._on_lost()


class AppCategorySignalAdapter:
    """Receive only a coarse focused-application category from GNOME Shell.

    The companion extension performs classification inside the compositor and
    sends one of a tiny allow-list of semantic categories. Application IDs,
    window titles, file names, and content never cross this D-Bus boundary.
    Older extension versions simply never emit this optional signal, leaving
    the category as ``unknown`` without affecting Mochi.
    """

    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE = "io.github.mochi_desktop.Mochi.TypingMonitor"
    SIGNAL_NAME = "AppCategoryChanged"
    ALLOWED = frozenset(("vscode", "editor", "terminal", "browser", "media", "pixel_art", "unknown"))

    def __init__(
        self,
        *,
        on_category_changed: Callable[[str], None],
        logger: logging.Logger | None = None,
        gio_loader: Callable[[], tuple[object, object]] | None = None,
    ) -> None:
        self._on_category_changed = on_category_changed
        self._logger = logger or logging.getLogger(__name__)
        self._gio_loader = gio_loader or self._load_gio
        self._connection = None
        self._subscription_id: int | None = None
        self.available = False
        self.category = "unknown"
        self.last_error: str | None = None

    @staticmethod
    def _load_gio():
        import gi
        from gi.repository import Gio, GLib
        return Gio, GLib

    def start(self) -> bool:
        if self.available:
            return True
        try:
            Gio, GLib = self._gio_loader()
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
            subscription_id = connection.signal_subscribe(
                self.BUS_NAME,
                self.INTERFACE,
                self.SIGNAL_NAME,
                self.OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_category_signal,
            )
            if not subscription_id:
                self.last_error = "application-category subscription failed"
                return False
            self._connection = connection
            self._subscription_id = int(subscription_id)
            self.available = True
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

    def stop(self) -> None:
        if self._connection is not None and self._subscription_id is not None:
            try:
                self._connection.signal_unsubscribe(self._subscription_id)
            except Exception:
                pass
        self._subscription_id = None
        self._connection = None
        self.available = False
        self.category = "unknown"

    def on_gnome_helper_unavailable(self) -> None:
        previous = self.category
        self.stop()
        if previous != "unknown":
            self._on_category_changed("unknown")

    def _on_category_signal(
        self,
        _connection,
        _sender_name,
        _object_path,
        _interface_name,
        _signal_name,
        parameters,
    ) -> None:
        try:
            unpacked = parameters.unpack()
            category = unpacked[0] if isinstance(unpacked, tuple) else unpacked
        except Exception:
            return
        if category not in self.ALLOWED or category == self.category:
            return
        self.category = category
        self._logger.debug("[presence] app category -> %s", category)
        self._on_category_changed(category)


class SystemSignalMonitor:
    """Lifecycle wrapper for optional UPower and NetworkManager adapters."""

    def __init__(
        self,
        *,
        on_battery_low: Callable[[float], None],
        on_charging_started: Callable[[float | None], None],
        on_network_lost: Callable[[], None],
        on_network_restored: Callable[[], None],
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self.battery = UPowerSignalAdapter(
            on_battery_low=on_battery_low,
            on_charging_started=on_charging_started,
            logger=self._logger,
        )
        self.network = NetworkSignalAdapter(
            on_lost=on_network_lost,
            on_restored=on_network_restored,
            logger=self._logger,
        )

    def start(self) -> None:
        if self.battery.start():
            self._logger.info("Ambient battery awareness enabled via UPower")
        else:
            self._logger.debug("UPower ambient signal unavailable: %s", self.battery.last_error)
        if self.network.start():
            self._logger.info("Ambient network awareness enabled via NetworkManager")
        else:
            self._logger.debug(
                "NetworkManager ambient signal unavailable: %s", self.network.last_error
            )

    def stop(self) -> None:
        self.battery.stop()
        self.network.stop()
