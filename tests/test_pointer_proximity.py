"""Mochi side of the helper's pointer-proximity bridge."""

from __future__ import annotations

import logging

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from mochi.pointer_proximity import PointerProximityMonitor  # noqa: E402
from mochi.voice_control_model import Rect  # noqa: E402


class _FakeConnection:
    def __init__(self, *, fail_with: GLib.Error | None = None) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.fail_with = fail_with
        self.signal_handler = None

    def signal_subscribe(self, sender, interface, member, path, arg0, flags, callback):
        assert member == "PointerNearChanged"
        self.signal_handler = callback
        return 7

    def signal_unsubscribe(self, ident):
        self.signal_handler = None

    def call(self, name, path, interface, method, params, reply_type, flags, timeout, cancellable, callback):
        self.calls.append((method, params.unpack() if params is not None else ()))
        callback(self, method)

    def call_finish(self, result):
        if self.fail_with is not None:
            raise self.fail_with
        return GLib.Variant("()", ())

    def emit(self, near: bool) -> None:
        self.signal_handler(self, ":1.5", "/p", "i", "PointerNearChanged", GLib.Variant("(b)", (near,)))


def _monitor(connection, seen):
    monitor = PointerProximityMonitor(
        on_near_changed=seen.append,
        logger=logging.getLogger("test.proximity"),
        connection_factory=lambda: connection,
        watch_name=lambda *_args: 0,
    )
    assert monitor.start()
    return monitor


def test_zone_is_sent_relative_to_mochi_and_only_when_it_changes() -> None:
    connection, seen = _FakeConnection(), []
    monitor = _monitor(connection, seen)

    monitor.set_zone(Rect(10.4, 120.0, 80.0, 60.0), owner_width=112)
    monitor.set_zone(Rect(10.4, 120.0, 80.0, 60.0), owner_width=112)

    assert connection.calls == [("SetProximityZone", (10, 120, 80, 60, 112))]
    assert monitor.supported is True


def test_clearing_the_zone_tells_the_helper_once() -> None:
    connection, seen = _FakeConnection(), []
    monitor = _monitor(connection, seen)
    monitor.set_zone(Rect(0, 0, 10, 10), owner_width=100)

    monitor.set_zone(None, owner_width=100)
    monitor.set_zone(None, owner_width=100)

    assert [method for method, _args in connection.calls] == [
        "SetProximityZone",
        "ClearProximityZone",
    ]


def test_helper_signal_reports_near_and_far() -> None:
    connection, seen = _FakeConnection(), []
    _monitor(connection, seen)

    connection.emit(True)
    connection.emit(False)

    assert seen == [True, False]


def test_an_older_helper_without_the_method_means_unsupported() -> None:
    error = GLib.Error.new_literal(
        Gio.dbus_error_quark(), "no such method", Gio.DBusError.UNKNOWN_METHOD
    )
    connection, seen = _FakeConnection(fail_with=error), []
    monitor = _monitor(connection, seen)

    monitor.set_zone(Rect(0, 0, 10, 10), owner_width=100)

    assert monitor.supported is False


def test_no_helper_running_means_unsupported() -> None:
    error = GLib.Error.new_literal(
        Gio.dbus_error_quark(), "not running", Gio.DBusError.SERVICE_UNKNOWN
    )
    connection, seen = _FakeConnection(fail_with=error), []
    monitor = _monitor(connection, seen)

    monitor.set_zone(Rect(0, 0, 10, 10), owner_width=100)

    assert monitor.supported is False


def test_zone_is_resent_when_the_helper_restarts() -> None:
    connection, seen = _FakeConnection(), []
    monitor = _monitor(connection, seen)
    zone = Rect(0, 0, 10, 10)
    monitor.set_zone(zone, owner_width=100)

    monitor._on_helper_appeared()  # GNOME Shell restarted; the helper lost it
    monitor.set_zone(zone, owner_width=100)

    assert [method for method, _args in connection.calls] == [
        "SetProximityZone",
        "SetProximityZone",
    ]
