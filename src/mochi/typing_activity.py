"""Privacy-preserving typing activity detection for Mochi's typing mirror.

On GNOME, the preferred backend receives zero-payload ``Pulse`` signals from the
optional Mochi GNOME Shell extension. The extension observes only that a key-press
event happened; neither side reads or transports key identity or text. AT-SPI
text/caret events remain a limited fallback when the extension is unavailable.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
import logging
import time
from typing import Protocol


DEFAULT_START_EVENT_COUNT = 2
DEFAULT_BURST_WINDOW_SECONDS = 0.60
DEFAULT_STOP_DELAY_SECONDS = 0.80


class TypingBurstDetector:
    """Turn anonymous activity timestamps into typing start/stop sessions."""

    def __init__(
        self,
        *,
        start_event_count: int = DEFAULT_START_EVENT_COUNT,
        burst_window_seconds: float = DEFAULT_BURST_WINDOW_SECONDS,
        stop_delay_seconds: float = DEFAULT_STOP_DELAY_SECONDS,
    ) -> None:
        # One isolated press must not make Mochi start typing.
        if start_event_count < 2:
            raise ValueError("start_event_count must be at least 2")
        if burst_window_seconds <= 0 or stop_delay_seconds <= 0:
            raise ValueError("typing timing values must be positive")

        self.start_event_count = start_event_count
        self.burst_window_seconds = burst_window_seconds
        self.stop_delay_seconds = stop_delay_seconds
        self.active = False
        self._event_times: deque[float] = deque(maxlen=start_event_count)

    def record_activity(self, now: float | None = None) -> bool:
        """Record one anonymous activity timestamp.

        Returns ``True`` only when this event starts a new typing session.
        Only timestamps are retained; this detector has no key-payload API.
        """
        timestamp = time.monotonic() if now is None else now
        self._event_times.append(timestamp)

        if self.active or len(self._event_times) < self.start_event_count:
            return False

        if self._event_times[-1] - self._event_times[0] <= self.burst_window_seconds:
            self.active = True
            return True

        return False

    def end_session(self) -> bool:
        """End the active typing session and report whether one was active."""
        was_active = self.active
        self.active = False
        self._event_times.clear()
        return was_active

    def reset(self) -> None:
        """Forget the current session/burst without emitting a stop event."""
        self.active = False
        self._event_times.clear()


class TypingActivityBackend(Protocol):
    """Backend contract: emit anonymous activity, never keyboard payloads."""

    name: str
    last_error: str | None

    def start(self, on_activity: Callable[[], None]) -> bool:
        ...

    def stop(self) -> None:
        ...


class GnomeShellTypingPulseBackend:
    """Anonymous keyboard activity from Mochi's GNOME Shell companion extension.

    The D-Bus ``Pulse`` signal has no arguments. No key symbol, keycode, Unicode
    value, modifier state, shortcut, or text crosses the process boundary.
    """

    name = "GNOME Shell typing pulse extension"
    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    SIGNAL_NAME = "Pulse"

    def __init__(self) -> None:
        self._connection = None
        self._subscription_id: int | None = None
        self._on_activity: Callable[[], None] | None = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._connection is not None and self._subscription_id is not None

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
                self.last_error = "GNOME Shell typing extension is not active"
                return False

            self._connection = connection
            self._on_activity = on_activity
            subscription_id = connection.signal_subscribe(
                self.BUS_NAME,
                self.INTERFACE_NAME,
                self.SIGNAL_NAME,
                self.OBJECT_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_pulse,
            )
            if not subscription_id:
                self.last_error = "typing Pulse signal subscription failed"
                self.stop()
                return False
            self._subscription_id = int(subscription_id)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

        return True

    def stop(self) -> None:
        if self._connection is not None and self._subscription_id is not None:
            try:
                self._connection.signal_unsubscribe(self._subscription_id)
            except Exception:
                pass

        self._subscription_id = None
        self._connection = None
        self._on_activity = None

    def _on_pulse(self, *_ignored) -> None:
        # PRIVACY BOUNDARY: Pulse has an empty payload. Never inspect D-Bus
        # callback arguments here; Mochi only learns that activity occurred.
        callback = self._on_activity
        if callback is not None:
            callback()


class AtspiDeviceActivityBackend:
    """Broad GNOME/Wayland keyboard activity via Atspi.DeviceA11yManager.

    ``Atspi.Device::key-pressed`` includes key metadata in its native signal
    signature. ``_on_key_pressed`` intentionally accepts all payload arguments
    only as ``*_ignored`` and never inspects them. Only anonymous activity
    crosses this backend boundary.
    """

    name = "AT-SPI DeviceA11yManager keyboard activity"

    def __init__(self) -> None:
        self._device = None
        self._handler_id: int | None = None
        self._on_activity: Callable[[], None] | None = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._device is not None and self._handler_id is not None

    def start(self, on_activity: Callable[[], None]) -> bool:
        if self.active:
            return True

        self.last_error = None
        try:
            import gi

            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi

            Atspi.init()
            manager_type = getattr(Atspi, "DeviceA11yManager", None)
            if manager_type is None:
                self.last_error = "DeviceA11yManager is unavailable"
                return False

            try_new = getattr(manager_type, "try_new", None)
            if try_new is None:
                self.last_error = "DeviceA11yManager.try_new is unavailable"
                return False

            device = try_new()
            if device is None:
                self.last_error = "DeviceA11yManager.try_new returned no device"
                return False

            # Since AT-SPI 2.60, merely creating a DeviceA11yManager and
            # connecting the key-pressed signal is not enough to request
            # keystroke monitoring. Explicitly enable the keyboard-monitor
            # capability before treating this backend as usable. If Mutter or
            # AT-SPI refuses the capability, fail cleanly so the monitor can
            # fall back to anonymous text/caret activity instead of selecting a
            # silent backend.
            if not self._enable_keyboard_monitor(device, Atspi):
                return False

            # Keep the object alive for the entire listener lifetime. The native
            # signal's payload is intentionally discarded in _on_key_pressed.
            self._device = device
            self._on_activity = on_activity
            handler_id = device.connect("key-pressed", self._on_key_pressed)
            if not handler_id:
                self.last_error = "key-pressed signal connection returned no handler"
                self.stop()
                return False
            self._handler_id = int(handler_id)
        except Exception as exc:
            # Startup exceptions contain no keyboard event payload. Never log or
            # retain runtime signal arguments here.
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

        return True

    def _enable_keyboard_monitor(self, device, Atspi) -> bool:
        """Request only anonymous keyboard-monitor capability from AT-SPI."""
        capability_type = getattr(Atspi, "DeviceCapability", None)
        keyboard_monitor = (
            None
            if capability_type is None
            else getattr(capability_type, "KEYBOARD_MONITOR", None)
        )
        set_capabilities = getattr(device, "set_capabilities", None)
        if keyboard_monitor is None or set_capabilities is None:
            self.last_error = "keyboard-monitor capability API is unavailable"
            return False

        get_capabilities = getattr(device, "get_capabilities", None)
        existing = get_capabilities() if get_capabilities is not None else 0
        requested = existing | keyboard_monitor
        enabled = set_capabilities(requested)
        if not (enabled & keyboard_monitor):
            self.last_error = "keyboard-monitor capability was not enabled"
            return False

        return True

    def stop(self) -> None:
        if self._device is not None and self._handler_id is not None:
            try:
                self._device.disconnect(self._handler_id)
            except Exception:
                pass

        self._handler_id = None
        self._device = None
        self._on_activity = None

    def _on_key_pressed(self, *_ignored) -> None:
        # PRIVACY BOUNDARY: NEVER inspect *_ignored. AT-SPI provides key metadata
        # here, but Mochi immediately reduces the signal to "activity happened".
        callback = self._on_activity
        if callback is not None:
            callback()


class AtspiTextActivityBackend:
    """Safe AT-SPI text/caret activity backend.

    Coverage depends on applications exposing accessibility events. Event
    contents and accessible source objects are never inspected. This is the
    default Wayland-safe runtime backend because compositor-wide keyboard
    monitoring is privileged for screen-reader use on GNOME.
    """

    name = "AT-SPI text/caret activity"
    TEXT_CHANGED_EVENT = "object:text-changed"
    CARET_MOVED_EVENT = "object:text-caret-moved"

    def __init__(self) -> None:
        self._listener = None
        self._registered_events: list[str] = []
        self._on_activity: Callable[[], None] | None = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._listener is not None

    def start(self, on_activity: Callable[[], None]) -> bool:
        if self.active:
            return True

        self.last_error = None
        try:
            import gi

            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi

            Atspi.init()
            listener = Atspi.EventListener.new(self._on_accessibility_event, None)
            self._listener = listener
            self._on_activity = on_activity

            for event_name in (self.TEXT_CHANGED_EVENT, self.CARET_MOVED_EVENT):
                if listener.register(event_name):
                    self._registered_events.append(event_name)

            if not self._registered_events:
                self.last_error = "text/caret listeners could not be registered"
                self.stop()
                return False
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

        return True

    def stop(self) -> None:
        if self._listener is not None:
            for event_name in tuple(self._registered_events):
                try:
                    self._listener.deregister(event_name)
                except Exception:
                    pass

        self._listener = None
        self._registered_events.clear()
        self._on_activity = None

    def _on_accessibility_event(self, event, *_ignored) -> None:
        # Inspect only the event category. Never inspect source, inserted text,
        # key values, or any other accessibility payload.
        event_type = getattr(event, "type", "") or ""
        if not (
            event_type.startswith(self.TEXT_CHANGED_EVENT)
            or event_type.startswith(self.CARET_MOVED_EVENT)
        ):
            return

        callback = self._on_activity
        if callback is not None:
            callback()


class TypingActivityMonitor:
    """Convert anonymous AT-SPI activity into Mochi typing sessions.

    ``on_typing_activity`` is emitted while a recognized typing session is
    active. This preserves Buddy's existing behavior: if a low-priority typing
    emote cannot begin immediately, a later fresh activity event can try again.
    """

    # Preserve these aliases for existing tests/debug tooling.
    TEXT_CHANGED_EVENT = AtspiTextActivityBackend.TEXT_CHANGED_EVENT
    CARET_MOVED_EVENT = AtspiTextActivityBackend.CARET_MOVED_EVENT

    def __init__(
        self,
        *,
        on_typing_activity: Callable[[], None],
        on_typing_stopped: Callable[[], None],
        detector: TypingBurstDetector | None = None,
        backends: Iterable[TypingActivityBackend] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._on_typing_activity = on_typing_activity
        self._on_typing_stopped = on_typing_stopped
        self._detector = detector or TypingBurstDetector()
        # Prefer the tiny GNOME Shell companion extension for broad activity.
        # It sends a zero-argument D-Bus Pulse and never transports key data.
        # AT-SPI text/caret activity remains a limited fallback when the
        # extension is not installed or enabled.
        self._backends = tuple(backends) if backends is not None else (
            GnomeShellTypingPulseBackend(),
            AtspiTextActivityBackend(),
        )
        self._logger = logger or logging.getLogger(__name__)

        self._backend: TypingActivityBackend | None = None
        self._glib = None
        self._stop_source_id: int | None = None
        self._unavailable_logged = False

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def active(self) -> bool:
        return self._detector.active

    @property
    def backend_name(self) -> str | None:
        return None if self._backend is None else self._backend.name

    def start(self) -> bool:
        """Start the first configured safe anonymous-activity backend."""
        if self._backend is not None:
            return True

        if self._glib is None:
            try:
                from gi.repository import GLib
            except (ImportError, ValueError) as exc:
                if not self._unavailable_logged:
                    self._logger.info(
                        "Typing mirror unavailable: GLib bindings missing (%s)", exc
                    )
                    self._unavailable_logged = True
                return False
            self._glib = GLib

        for backend in self._backends:
            self._logger.debug("Typing backend trying: %s", backend.name)
            try:
                started = backend.start(self._record_anonymous_activity)
            except Exception as exc:
                started = False
                # This is backend initialization, never a keyboard callback.
                self._logger.debug(
                    "Typing backend %s failed during startup: %s: %s",
                    backend.name,
                    type(exc).__name__,
                    exc,
                )

            if not started:
                reason = getattr(backend, "last_error", None)
                if reason:
                    self._logger.debug(
                        "Typing backend unavailable: %s (%s)", backend.name, reason
                    )
                try:
                    backend.stop()
                except Exception:
                    pass
                continue

            self._backend = backend
            self._unavailable_logged = False
            self._logger.info(
                "Typing mirror enabled via %s "
                "(anonymous activity timing only; key content is discarded)",
                backend.name,
            )
            self._log_accessibility_coverage_hint()
            return True

        self._log_unavailable_once()
        return False

    def _log_accessibility_coverage_hint(self) -> None:
        """Warn when GNOME accessibility exposure is disabled; never change it."""
        try:
            from gi.repository import Gio

            settings = Gio.Settings.new("org.gnome.desktop.interface")
            enabled = settings.get_boolean("toolkit-accessibility")
        except Exception:
            return

        if not enabled:
            self._logger.info(
                "Typing mirror coverage may be limited: GNOME toolkit-accessibility "
                "is disabled; Mochi will not change this system setting automatically"
            )

    def reset(self) -> None:
        """Cancel the session; a fresh two-event burst is required to restart."""
        self._cancel_stop_timer()
        self._detector.reset()

    def stop(self) -> None:
        """Disconnect backend/timer and clear anonymous activity state."""
        self._cancel_stop_timer()
        self._detector.reset()

        backend = self._backend
        self._backend = None
        if backend is not None:
            try:
                backend.stop()
            except Exception:
                pass

        self._glib = None

    def _record_anonymous_activity(self, now: float | None = None) -> None:
        started = self._detector.record_activity(now)

        if not self._detector.active:
            return

        # Refresh the inactivity timeout for every event in an active session.
        self._arm_stop_timer()
        self._on_typing_activity()

        if started:
            self._logger.debug("Typing activity started")

    def _arm_stop_timer(self) -> None:
        if self._glib is None:
            return

        self._cancel_stop_timer()
        self._stop_source_id = self._glib.timeout_add(
            round(self._detector.stop_delay_seconds * 1_000),
            self._finish_typing_session,
        )

    def _cancel_stop_timer(self) -> None:
        if self._stop_source_id is None or self._glib is None:
            self._stop_source_id = None
            return

        try:
            self._glib.source_remove(self._stop_source_id)
        except Exception:
            pass
        self._stop_source_id = None

    def _finish_typing_session(self) -> bool:
        self._stop_source_id = None
        if self._detector.end_session():
            self._logger.debug("Typing activity stopped")
            self._on_typing_stopped()

        return getattr(self._glib, "SOURCE_REMOVE", False)

    def _log_unavailable_once(self) -> None:
        if self._unavailable_logged:
            return
        self._unavailable_logged = True
        self._logger.info(
            "Typing mirror unavailable: no safe AT-SPI typing activity backend"
        )
