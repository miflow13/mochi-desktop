import unittest

from mochi.gnome_helper import GnomeHelperLifecycle
from unittest.mock import Mock


class _Timers:
    def __init__(self):
        self.pending = {}
        self.delays = []
        self.serial = 0

    def timeout_add_seconds(self, delay, callback):
        self.serial += 1
        self.delays.append(delay)
        self.pending[self.serial] = callback
        return self.serial

    def source_remove(self, source):
        self.pending.pop(source, None)

    def fire(self):
        source = next(iter(self.pending))
        self.pending.pop(source)()


class _FakeGio:
    class BusType:
        SESSION = object()

    class BusNameWatcherFlags:
        NONE = object()

    connection = object()
    appeared = None
    vanished = None
    unwatched = []

    @classmethod
    def bus_get_sync(cls, _bus_type, _cancellable):
        return cls.connection

    @classmethod
    def bus_watch_name_on_connection(
        cls, _connection, _name, _flags, appeared, vanished
    ):
        cls.appeared = appeared
        cls.vanished = vanished
        return 41

    @classmethod
    def bus_unwatch_name(cls, watch_id):
        cls.unwatched.append(watch_id)


class _Connection:
    def __init__(self) -> None:
        self.emitted = []

    def emit_signal(self, *args):
        self.emitted.append(args)


class GnomeHelperLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeGio.appeared = None
        _FakeGio.vanished = None
        _FakeGio.unwatched = []
        self.connection = _Connection()
        _FakeGio.connection = self.connection
        self.events = []
        self.lifecycle = GnomeHelperLifecycle(
            on_available=lambda: self.events.append("available") or True,
            on_unavailable=lambda: self.events.append("unavailable"),
        )
        self.lifecycle._load_gio = lambda: _FakeGio
        self.timers = _Timers()
        self.lifecycle._load_glib = lambda: self.timers

    def test_late_helper_reconnects_dependents_and_requests_current_state(self):
        self.assertTrue(self.lifecycle.start())
        self.assertFalse(self.lifecycle.available)

        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")

        self.assertTrue(self.lifecycle.available)
        self.assertEqual(self.events, ["available"])
        self.assertEqual(len(self.connection.emitted), 1)
        self.assertEqual(
            self.connection.emitted[0][3], self.lifecycle.SYNC_SIGNAL_NAME
        )

    def test_repeated_owner_callbacks_do_not_duplicate_reconnect_or_sync(self):
        self.lifecycle.start()

        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")

        self.assertEqual(self.events, ["available"])
        self.assertEqual(len(self.connection.emitted), 1)

    def test_helper_can_disappear_and_return(self):
        self.lifecycle.start()
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")

        _FakeGio.vanished(self.connection, self.lifecycle.BUS_NAME)
        _FakeGio.vanished(self.connection, self.lifecycle.BUS_NAME)
        self.assertFalse(self.lifecycle.available)

        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.57")

        self.assertEqual(
            self.events, ["available", "unavailable", "available"]
        )
        self.assertEqual(len(self.connection.emitted), 2)

    def test_stop_unwatches_once_and_ignores_late_callbacks(self):
        self.lifecycle.start()
        appeared = _FakeGio.appeared
        vanished = _FakeGio.vanished

        self.lifecycle.stop()
        self.lifecycle.stop()
        appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        vanished(self.connection, self.lifecycle.BUS_NAME)

        self.assertEqual(_FakeGio.unwatched, [41])
        self.assertEqual(self.events, [])
        self.assertEqual(self.connection.emitted, [])
        self.assertFalse(self.lifecycle.available)

    def test_permanently_absent_helper_is_a_stable_unavailable_state(self):
        self.assertTrue(self.lifecycle.start())
        _FakeGio.vanished(self.connection, self.lifecycle.BUS_NAME)
        _FakeGio.vanished(self.connection, self.lifecycle.BUS_NAME)
        self.assertEqual(self.events, ["unavailable"])
        self.assertEqual(self.connection.emitted, [])
        self.assertFalse(self.lifecycle.available)
        self.lifecycle.stop()

    def test_sync_is_sent_only_after_dependents_attach(self):
        def attach():
            self.assertEqual(self.connection.emitted, [])
            self.events.append("attached")
            return True

        self.lifecycle._on_available = attach
        self.lifecycle.start()
        self.lifecycle.start()
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        self.assertEqual(self.events, ["attached"])
        self.assertEqual(self.connection.emitted[0][0], ":1.42")
        self.assertIsNone(self.connection.emitted[0][-1])

    def test_missing_session_bus_fails_gracefully(self):
        _FakeGio.connection = None
        self.assertFalse(self.lifecycle.start())
        self.assertFalse(self.lifecycle.available)
        self.lifecycle.stop()
        self.assertEqual(self.events, [])

    def test_failed_attachment_retries_before_sending_one_snapshot(self):
        attach = Mock(side_effect=[False, False, True])
        self.lifecycle._on_available = attach
        self.lifecycle.start()
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        self.assertEqual(self.connection.emitted, [])
        self.assertEqual(len(self.timers.pending), 1)
        self.timers.fire()
        self.assertEqual(self.connection.emitted, [])
        self.timers.fire()
        self.assertEqual(len(self.connection.emitted), 1)
        self.assertEqual(attach.call_count, 3)
        self.assertEqual(self.timers.delays, [1, 2])
        self.assertEqual(self.timers.pending, {})

    def test_owner_loss_and_shutdown_cancel_pending_attachment(self):
        self.lifecycle._on_available = Mock(return_value=False)
        self.lifecycle.start()
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        _FakeGio.vanished(self.connection, self.lifecycle.BUS_NAME)
        self.assertEqual(self.timers.pending, {})
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.43")
        self.assertEqual(self.timers.delays, [1, 1])
        self.lifecycle.stop()
        self.assertEqual(self.timers.pending, {})
        self.assertEqual(self.connection.emitted, [])

    def test_attachment_exception_recovers_and_snapshot_send_failure_retries(self):
        self.lifecycle._on_available = Mock(side_effect=[
            RuntimeError("temporary attachment failure"), True, True,
        ])
        self.connection.emit_signal = Mock(side_effect=[False, True])
        self.lifecycle.start()
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        self.connection.emit_signal.assert_not_called()
        self.timers.fire()
        self.assertEqual(len(self.timers.pending), 1)
        self.timers.fire()
        self.assertEqual(self.connection.emit_signal.call_count, 2)
        self.assertEqual(self.timers.pending, {})

    def test_persistent_failure_has_one_timer_with_capped_backoff(self):
        self.lifecycle._on_available = Mock(return_value=False)
        self.lifecycle.start()
        _FakeGio.appeared(self.connection, self.lifecycle.BUS_NAME, ":1.42")
        for _ in range(6):
            self.assertEqual(len(self.timers.pending), 1)
            self.timers.fire()
        self.assertEqual(self.timers.delays, [1, 2, 4, 8, 16, 30, 30])
        self.assertEqual(self.connection.emitted, [])
        self.lifecycle.stop()
        self.assertEqual(self.timers.pending, {})


if __name__ == "__main__":
    unittest.main()
