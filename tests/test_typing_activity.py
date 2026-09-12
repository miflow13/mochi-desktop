import logging
import unittest

from mochi.typing_activity import (
    AtspiDeviceActivityBackend,
    AtspiTextActivityBackend,
    GnomeShellTypingPulseBackend,
    TypingActivityMonitor,
    TypingBurstDetector,
)


class TypingBurstDetectorTests(unittest.TestCase):
    def test_shortcut_sized_burst_does_not_start_typing(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.00, 1.03, 1.06, 1.09):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertFalse(detector.active)

    def test_ultrafast_chord_does_not_start_typing(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.00, 1.02, 1.04, 1.06, 1.08):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertFalse(detector.active)

    def test_sustained_five_event_burst_starts_typing(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.00, 1.10, 1.20, 1.30):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(1.40))
        self.assertTrue(detector.active)

    def test_old_events_roll_out_of_burst_window(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.0, 1.1, 1.2, 2.5, 2.6, 2.7, 2.8):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(2.9))

    def test_end_session_allows_fresh_burst(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.0, 1.1, 1.2, 1.3):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(1.4))
        self.assertTrue(detector.end_session())
        self.assertFalse(detector.end_session())
        for timestamp in (2.0, 2.1, 2.2, 2.3):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(2.4))

    def test_reset_discards_stale_activity(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.0, 1.1, 1.2, 1.3):
            self.assertFalse(detector.record_activity(timestamp))
        detector.reset()
        for timestamp in (1.4, 1.5, 1.6, 1.7):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(1.8))


class _FakeGLib:
    SOURCE_REMOVE = False

    def __init__(self) -> None:
        self._callbacks: dict[int, object] = {}
        self._next_source_id = 1
        self.removed: list[int] = []
        self.last_timeout_ms: int | None = None

    def timeout_add(self, milliseconds: int, callback: object) -> int:
        self.last_timeout_ms = milliseconds
        source_id = self._next_source_id
        self._next_source_id += 1
        self._callbacks[source_id] = callback
        return source_id

    def source_remove(self, source_id: int) -> None:
        self.removed.append(source_id)
        self._callbacks.pop(source_id, None)

    def fire_latest_timer(self) -> None:
        source_id = max(self._callbacks)
        callback = self._callbacks.pop(source_id)
        callback()

    @property
    def timer_count(self) -> int:
        return len(self._callbacks)


class _FakeBackend:
    def __init__(self, name: str, available: bool = True, error: str | None = None):
        self.name = name
        self.available = available
        self.last_error = error
        self.start_calls = 0
        self.stop_calls = 0
        self.callback = None

    def start(self, callback) -> bool:
        self.start_calls += 1
        if not self.available:
            return False
        self.callback = callback
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self.callback = None

    def emit(self, now: float | None = None) -> None:
        if self.callback is None:
            raise AssertionError("backend is not started")
        self.callback(now)


class _ListLogger(logging.Logger):
    def __init__(self) -> None:
        super().__init__("typing-test")
        self.messages: list[str] = []

    def info(self, msg, *args, **kwargs) -> None:
        self.messages.append(msg % args if args else str(msg))

    def debug(self, msg, *args, **kwargs) -> None:
        self.messages.append(msg % args if args else str(msg))


class TypingActivityMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.activity_calls = 0
        self.stop_calls = 0
        self.glib = _FakeGLib()
        self.backend = _FakeBackend("broad")
        self.monitor = TypingActivityMonitor(
            on_typing_activity=self._record_activity,
            on_typing_stopped=self._record_stop,
            backends=[self.backend],
        )
        self.monitor._glib = self.glib
        self.assertTrue(self.monitor.start())

    def _record_activity(self) -> None:
        self.activity_calls += 1

    def _record_stop(self) -> None:
        self.stop_calls += 1

    def _emit_sustained_typing_burst(self, start: float = 1.0) -> None:
        for offset in (0.0, 0.1, 0.2, 0.3, 0.4):
            self.backend.emit(start + offset)

    def test_shortcut_sized_burst_does_not_trigger_typing(self) -> None:
        for timestamp in (1.00, 1.03, 1.06, 1.09):
            self.backend.emit(timestamp)
        self.assertFalse(self.monitor.active)
        self.assertEqual(self.activity_calls, 0)

    def test_sustained_burst_triggers_typing(self) -> None:
        self._emit_sustained_typing_burst()
        self.assertTrue(self.monitor.active)
        self.assertEqual(self.activity_calls, 1)
        self.assertEqual(self.glib.timer_count, 1)
        self.assertEqual(self.glib.last_timeout_ms, 2250)

    def test_continued_activity_refreshes_same_session(self) -> None:
        self._emit_sustained_typing_burst()
        self.backend.emit(1.5)
        self.assertEqual(self.activity_calls, 2)
        self.assertEqual(self.glib.timer_count, 1)

    def test_inactivity_stops_typing_once(self) -> None:
        self._emit_sustained_typing_burst()
        self.glib.fire_latest_timer()
        self.assertFalse(self.monitor.active)
        self.assertEqual(self.stop_calls, 1)

    def test_reset_requires_fresh_sustained_burst(self) -> None:
        self._emit_sustained_typing_burst()
        self.monitor.reset()
        for timestamp in (2.0, 2.1, 2.2, 2.3):
            self.backend.emit(timestamp)
        self.assertFalse(self.monitor.active)
        self.backend.emit(2.4)
        self.assertTrue(self.monitor.active)

    def test_preferred_backend_prevents_fallback(self) -> None:
        preferred = _FakeBackend("device", available=True)
        fallback = _FakeBackend("text", available=True)
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        self.assertTrue(monitor.start())
        self.assertEqual(monitor.backend_name, "device")
        self.assertEqual(preferred.start_calls, 1)
        self.assertEqual(fallback.start_calls, 0)

    def test_default_runtime_prefers_shell_pulse_then_text_fallback(self) -> None:
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
        )
        self.assertEqual(len(monitor._backends), 2)
        self.assertIsInstance(monitor._backends[0], GnomeShellTypingPulseBackend)
        self.assertIsInstance(monitor._backends[1], AtspiTextActivityBackend)

    def test_failed_preferred_backend_falls_back(self) -> None:
        preferred = _FakeBackend("device", available=False, error="unavailable")
        fallback = _FakeBackend("text", available=True)
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        self.assertTrue(monitor.start())
        self.assertEqual(monitor.backend_name, "text")
        self.assertEqual(preferred.start_calls, 1)
        self.assertEqual(fallback.start_calls, 1)

    def test_helper_appearance_promotes_fallback_without_emitting_activity(self) -> None:
        activity = []
        stopped = []
        preferred = _FakeBackend("shell", available=False)
        fallback = _FakeBackend("text", available=True)
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: activity.append(True),
            on_typing_stopped=lambda: stopped.append(True),
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        self.assertTrue(monitor.start())
        self.assertEqual(monitor.backend_name, "text")

        preferred.available = True
        self.assertTrue(monitor.on_gnome_helper_available())

        self.assertEqual(monitor.backend_name, "shell")
        self.assertEqual(fallback.stop_calls, 1)
        self.assertEqual(activity, [])
        self.assertEqual(stopped, [])

    def test_helper_loss_restores_typing_fallback(self) -> None:
        preferred = _FakeBackend("shell", available=True)
        fallback = _FakeBackend("text", available=True)
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        self.assertTrue(monitor.start())

        preferred.available = False
        self.assertTrue(monitor.on_gnome_helper_unavailable())

        self.assertEqual(monitor.backend_name, "text")
        self.assertEqual(fallback.start_calls, 1)

    def test_fallback_availability_does_not_report_shell_attachment_success(self):
        preferred = _FakeBackend("shell", available=False)
        fallback = _FakeBackend("text")
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None, on_typing_stopped=lambda: None,
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        monitor.start()
        self.assertFalse(monitor.on_gnome_helper_available())
        self.assertTrue(monitor.available)
        self.assertEqual(monitor.backend_name, "text")

    def test_reconnecting_preserves_an_active_typing_session_and_timer(self) -> None:
        events = []
        preferred = _FakeBackend("shell", available=False)
        fallback = _FakeBackend("text")
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: events.append("activity"),
            on_typing_stopped=lambda: events.append("stopped"),
            backends=[preferred, fallback],
        )
        glib = _FakeGLib()
        monitor._glib = glib
        monitor.start()
        for now in (1.0, 1.1, 1.2, 1.3, 1.4):
            fallback.emit(now)
        timer = monitor._stop_source_id
        preferred.available = True
        monitor.on_gnome_helper_available()
        monitor.on_gnome_helper_available()
        self.assertTrue(monitor.active)
        self.assertEqual(monitor._stop_source_id, timer)
        self.assertEqual(preferred.start_calls, 2)  # Initial failure + promotion.
        self.assertEqual(events, ["activity"])
        preferred.available = False
        monitor.on_gnome_helper_unavailable()
        monitor.on_gnome_helper_unavailable()
        glib.fire_latest_timer()
        self.assertEqual(events, ["activity", "stopped"])
        self.assertFalse(monitor.active)

    def test_stop_disconnects_backend_once(self) -> None:
        self.monitor.stop()
        self.monitor.stop()
        self.assertEqual(self.backend.stop_calls, 1)
        self.assertFalse(self.monitor.available)


class GnomeShellTypingPulseBackendTests(unittest.TestCase):
    class _Variant:
        def __init__(self, _signature, value):
            self.value = value

        def unpack(self):
            return self.value

    class _GLib:
        Variant = None

    class _Gio:
        class BusType:
            SESSION = object()

        class DBusCallFlags:
            NONE = object()

        class DBusSignalFlags:
            NONE = object()

        connection = None

        @classmethod
        def bus_get_sync(cls, _bus_type, _cancellable):
            return cls.connection

    class _Connection:
        def __init__(self, *, has_owner=True):
            self.has_owner = has_owner
            self.callback = None
            self.subscribe_args = None
            self.unsubscribed = []

        def call_sync(self, *args):
            return GnomeShellTypingPulseBackendTests._Variant(
                "(b)", (self.has_owner,)
            )

        def signal_subscribe(self, *args):
            self.subscribe_args = args
            self.callback = args[-1]
            return 17

        def signal_unsubscribe(self, subscription_id):
            self.unsubscribed.append(subscription_id)
            self.callback = None

    def _backend_with_connection(self, connection):
        backend = GnomeShellTypingPulseBackend()
        gio = self._Gio
        glib = self._GLib
        glib.Variant = self._Variant
        gio.connection = connection
        backend._load_gio = lambda: (gio, glib)
        return backend

    def test_extension_owner_is_required(self) -> None:
        backend = self._backend_with_connection(self._Connection(has_owner=False))

        self.assertFalse(backend.start(lambda: None))
        self.assertEqual(
            backend.last_error, "GNOME Shell typing extension is not active"
        )
        self.assertFalse(backend.active)

    def test_subscribes_to_zero_payload_pulse(self) -> None:
        connection = self._Connection()
        backend = self._backend_with_connection(connection)
        calls = 0

        def activity():
            nonlocal calls
            calls += 1

        self.assertTrue(backend.start(activity))
        self.assertTrue(backend.active)
        self.assertEqual(connection.subscribe_args[0], backend.BUS_NAME)
        self.assertEqual(connection.subscribe_args[1], backend.INTERFACE_NAME)
        self.assertEqual(connection.subscribe_args[2], backend.SIGNAL_NAME)
        self.assertEqual(connection.subscribe_args[3], backend.OBJECT_PATH)

        connection.callback(object(), object(), object(), object(), object(), object())
        self.assertEqual(calls, 1)

    def test_stop_unsubscribes_once(self) -> None:
        connection = self._Connection()
        backend = self._backend_with_connection(connection)
        self.assertTrue(backend.start(lambda: None))

        backend.stop()
        backend.stop()

        self.assertEqual(connection.unsubscribed, [17])
        self.assertFalse(backend.active)

    def test_pulse_callback_never_inspects_payload(self) -> None:
        class Explosive:
            def __repr__(self):
                raise AssertionError("D-Bus callback payload must not be formatted")

            def __str__(self):
                raise AssertionError("D-Bus callback payload must not be inspected")

        backend = GnomeShellTypingPulseBackend()
        calls = 0

        def activity():
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = Explosive()
        backend._on_pulse(secret, secret, secret, secret, secret, secret)

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())


class DeviceCapabilityTests(unittest.TestCase):
    class _Capability:
        KEYBOARD_MONITOR = 1

    class _Atspi:
        DeviceCapability = None

    class _Device:
        def __init__(self, *, existing=0, enabled=1):
            self.existing = existing
            self.enabled = enabled
            self.requested = None

        def get_capabilities(self):
            return self.existing

        def set_capabilities(self, requested):
            self.requested = requested
            return self.enabled

    def test_keyboard_monitor_capability_is_requested_and_verified(self) -> None:
        backend = AtspiDeviceActivityBackend()
        atspi = type("Atspi", (), {"DeviceCapability": self._Capability})
        device = self._Device(existing=2, enabled=3)

        self.assertTrue(backend._enable_keyboard_monitor(device, atspi))
        self.assertEqual(device.requested, 3)
        self.assertIsNone(backend.last_error)

    def test_refused_keyboard_monitor_capability_fails_backend(self) -> None:
        backend = AtspiDeviceActivityBackend()
        atspi = type("Atspi", (), {"DeviceCapability": self._Capability})
        device = self._Device(enabled=0)

        self.assertFalse(backend._enable_keyboard_monitor(device, atspi))
        self.assertEqual(
            backend.last_error, "keyboard-monitor capability was not enabled"
        )

    def test_missing_capability_api_fails_cleanly(self) -> None:
        backend = AtspiDeviceActivityBackend()
        atspi = type("Atspi", (), {"DeviceCapability": None})
        device = self._Device()

        self.assertFalse(backend._enable_keyboard_monitor(device, atspi))
        self.assertEqual(
            backend.last_error, "keyboard-monitor capability API is unavailable"
        )


class BackendPrivacyTests(unittest.TestCase):
    class _ExplosivePayload:
        def __repr__(self) -> str:
            raise AssertionError("keyboard payload must never be formatted")

        def __str__(self) -> str:
            raise AssertionError("keyboard payload must never be inspected")

    def test_device_backend_discards_signal_payload(self) -> None:
        backend = AtspiDeviceActivityBackend()
        calls = 0

        def activity() -> None:
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = self._ExplosivePayload()
        backend._on_key_pressed(object(), secret, secret, secret, secret)

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())

    def test_text_fallback_reads_only_event_type(self) -> None:
        backend = AtspiTextActivityBackend()
        calls = 0

        def activity() -> None:
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = self._ExplosivePayload()
        event = type(
            "Event",
            (),
            {
                "type": "object:text-changed:insert",
                "source": secret,
                "any_data": secret,
            },
        )()
        backend._on_accessibility_event(event, secret)

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())


if __name__ == "__main__":
    unittest.main()
