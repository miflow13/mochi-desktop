import logging
import unittest

from mochi.presence_activity import GnomeShellPresenceBackend, PresenceActivityMonitor


class _Variant:
    def __init__(self, _signature, value):
        self.value = value

    def unpack(self):
        return self.value


class _GLib:
    Variant = _Variant


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
        self.subscriptions = []
        self.callbacks = {}
        self.unsubscribed = []
        self._next_id = 11

    def call_sync(self, *args):
        return _Variant("(b)", (self.has_owner,))

    def signal_subscribe(self, *args):
        subscription_id = self._next_id
        self._next_id += 1
        signal_name = args[2]
        self.subscriptions.append(args)
        self.callbacks[signal_name] = args[-1]
        return subscription_id

    def signal_unsubscribe(self, subscription_id):
        self.unsubscribed.append(subscription_id)


class PresenceBackendTests(unittest.TestCase):
    def _backend(self, connection):
        backend = GnomeShellPresenceBackend()
        _Gio.connection = connection
        backend._load_gio = lambda: (_Gio, _GLib)
        return backend

    def test_extension_owner_is_required(self) -> None:
        backend = self._backend(_Connection(has_owner=False))
        self.assertFalse(backend.start(lambda: None, lambda: None))
        self.assertFalse(backend.active)

    def test_subscribes_to_idle_and_active_zero_payload_signals(self) -> None:
        connection = _Connection()
        backend = self._backend(connection)
        idle_calls = 0
        active_calls = 0

        def idle():
            nonlocal idle_calls
            idle_calls += 1

        def active():
            nonlocal active_calls
            active_calls += 1

        self.assertTrue(backend.start(idle, active))
        self.assertTrue(backend.active)
        self.assertIn(backend.IDLE_SIGNAL_NAME, connection.callbacks)
        self.assertIn(backend.ACTIVE_SIGNAL_NAME, connection.callbacks)

        connection.callbacks[backend.IDLE_SIGNAL_NAME](object(), object(), object())
        connection.callbacks[backend.ACTIVE_SIGNAL_NAME](object(), object(), object())
        self.assertEqual(idle_calls, 1)
        self.assertEqual(active_calls, 1)

    def test_callbacks_ignore_dbus_payload_objects(self) -> None:
        class Explosive:
            def __repr__(self):
                raise AssertionError("presence callback payload must not be formatted")

            def __str__(self):
                raise AssertionError("presence callback payload must not be inspected")

        backend = GnomeShellPresenceBackend()
        calls = []
        backend._on_user_idle = lambda: calls.append("idle")
        backend._on_user_active = lambda: calls.append("active")
        secret = Explosive()

        backend._on_idle_signal(secret, secret, secret)
        backend._on_active_signal(secret, secret, secret)
        self.assertEqual(calls, ["idle", "active"])
        self.assertNotIn(secret, vars(backend).values())

    def test_stop_unsubscribes_both_once(self) -> None:
        connection = _Connection()
        backend = self._backend(connection)
        self.assertTrue(backend.start(lambda: None, lambda: None))

        backend.stop()
        backend.stop()
        self.assertEqual(connection.unsubscribed, [11, 12])
        self.assertFalse(backend.active)


class _FakeBackend:
    name = "fake presence"

    def __init__(self, available=True):
        self.available = available
        self.last_error = None if available else "unavailable"
        self.idle = None
        self.active = None
        self.stop_calls = 0

    def start(self, idle, active):
        if not self.available:
            return False
        self.idle = idle
        self.active = active
        return True

    def stop(self):
        self.stop_calls += 1


class PresenceMonitorTests(unittest.TestCase):
    def test_monitor_forwards_semantic_presence_events(self) -> None:
        backend = _FakeBackend()
        events = []
        monitor = PresenceActivityMonitor(
            on_user_idle=lambda: events.append("idle"),
            on_user_active=lambda: events.append("active"),
            backend=backend,
        )
        self.assertTrue(monitor.start())
        backend.idle()
        backend.active()
        self.assertEqual(events, ["idle", "active"])
        self.assertEqual(monitor.backend_name, "fake presence")

    def test_unavailable_backend_fails_gracefully(self) -> None:
        backend = _FakeBackend(available=False)
        monitor = PresenceActivityMonitor(
            on_user_idle=lambda: None,
            on_user_active=lambda: None,
            backend=backend,
            logger=logging.getLogger("presence-test"),
        )
        self.assertFalse(monitor.start())
        self.assertIsNone(monitor.backend_name)

    def test_stop_is_idempotent(self) -> None:
        backend = _FakeBackend()
        monitor = PresenceActivityMonitor(
            on_user_idle=lambda: None,
            on_user_active=lambda: None,
            backend=backend,
        )
        self.assertTrue(monitor.start())
        monitor.stop()
        monitor.stop()
        self.assertEqual(backend.stop_calls, 1)

    def test_replayed_presence_does_not_duplicate_events_or_wake_on_initial_active(self):
        backend = _FakeBackend()
        events = []
        monitor = PresenceActivityMonitor(
            on_user_idle=lambda: events.append("idle"),
            on_user_active=lambda: events.append("active"),
            backend=backend,
        )
        monitor.start()
        backend.active()
        self.assertEqual(events, [])
        backend.idle()
        backend.idle()
        backend.active()
        backend.active()
        self.assertEqual(events, ["idle", "active"])
