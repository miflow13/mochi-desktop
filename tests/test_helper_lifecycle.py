"""Exercise helper ownership changes through real adapter callbacks."""
from types import SimpleNamespace

import pytest

from mochi.presence_activity import GnomeShellPresenceBackend


class Variant:
    def __init__(self, signature, value):
        self.value = value

    def unpack(self):
        return self.value


class Bus:
    def __init__(self):
        self.owner = None
        self.subscriptions = {}
        self.next_id = 0
        self.syncs = 0
        self.state = (True, True, True, "terminal")
        self.watches = {}

    def signal_subscribe(self, *args):
        self.next_id += 1
        self.subscriptions[self.next_id] = args
        return self.next_id

    def signal_unsubscribe(self, ident):
        del self.subscriptions[ident]

    def call_sync(self, *args):
        if args[3] == "NameHasOwner":
            return Variant("(b)", (bool(self.owner),))
        self.syncs += 1
        return Variant("(bbbs)", self.state)

    def watch(self, connection, name, flags, appeared, vanished):
        self.next_id += 1
        ident = self.next_id
        self.watches[ident] = (appeared, vanished)
        if self.owner:
            appeared(self, name, self.owner)
        else:
            vanished(self, name)
        return ident

    def change_owner(self, owner):
        self.owner = owner
        for appeared, vanished in list(self.watches.values()):
            if owner:
                appeared(self, "helper", owner)
            else:
                vanished(self, "helper")

    def loader(self):
        flags = SimpleNamespace(NONE=0)
        return SimpleNamespace(
            BusType=SimpleNamespace(SESSION=0), DBusCallFlags=flags,
            DBusSignalFlags=flags, BusNameWatcherFlags=flags,
            bus_get_sync=lambda *_: self,
            bus_watch_name_on_connection=self.watch,
            bus_unwatch_name=lambda ident: self.watches.pop(ident),
        ), SimpleNamespace(Variant=Variant, VariantType=SimpleNamespace(new=lambda value: value))


@pytest.mark.parametrize("restarted_owner", [":1.2", ":1.3"])
def test_presence_late_helper_and_restart(restarted_owner):
    bus = Bus()
    backend = GnomeShellPresenceBackend()
    backend._load_gio = bus.loader
    events = []
    backend.start(lambda: events.append("idle"), lambda: events.append("active"))
    bus.change_owner(":1.2")
    assert events == ["idle"]
    assert len(bus.subscriptions) == 2
    assert bus.syncs == 1
    stale = list(bus.subscriptions.values())[0][-1]
    bus.change_owner(None)
    assert events == ["idle", "active"]
    assert not bus.subscriptions
    stale(None, None, None, None, None, None)
    assert events == ["idle", "active"]
    bus.change_owner(restarted_owner)
    bus.change_owner(restarted_owner)
    assert events == ["idle", "active", "idle"]
    assert len(bus.subscriptions) == 2
    assert bus.syncs == 2
    backend.stop()
    backend.stop()
    assert not bus.subscriptions
    assert not bus.watches


def test_already_running_sync_and_start_stop_start():
    bus = Bus()
    bus.owner = ":1.1"
    backend = GnomeShellPresenceBackend()
    backend._load_gio = bus.loader
    events = []
    assert backend.start(lambda: events.append("idle"), lambda: events.append("active"))
    assert backend.start(lambda: None, lambda: None)
    assert events == ["idle"]
    assert bus.syncs == 1
    backend.stop()
    assert backend.start(lambda: events.append("idle"), lambda: events.append("active"))
    assert events == ["idle", "active", "idle"]
    assert bus.syncs == 2
    backend.stop()


def test_app_category_owner_replacement_clears_and_resyncs():
    from mochi.presence.signals import AppCategorySignalAdapter
    bus = Bus()
    events = []
    adapter = AppCategorySignalAdapter(on_category_changed=events.append, gio_loader=bus.loader)
    assert adapter.start()
    bus.change_owner(":1.1")
    bus.state = (False, False, False, "browser")
    bus.change_owner(":1.2")
    # The first helper snapshot establishes a baseline. A reconnect after
    # losing the helper is a real state change and still reaches consumers.
    assert events == ["unknown", "browser"]
    assert len(bus.subscriptions) == 2
    subscribed_signals = {args[2] for args in bus.subscriptions.values()}
    assert subscribed_signals == {"AppCategoryChanged", "AppFocusChanged"}
    adapter.stop()
    assert events[-1] == "unknown"
    bus.change_owner(":1.3")
    assert len(bus.subscriptions) == 0


def test_file_loss_preserves_download_activity():
    from mochi.file_activity import GnomeShellFileContextBackend, FileActivityMonitor
    bus = Bus()
    backend = GnomeShellFileContextBackend()
    backend._load_gio = bus.loader
    events = []
    now = [0.0]
    monitor = FileActivityMonitor(
        on_file_activity_started=lambda: events.append(True),
        on_file_activity_stopped=lambda: events.append(False),
        file_context_backend=backend, clock=lambda: now[0],
    )
    backend.start(monitor._on_file_browser_started, monitor._on_file_browser_stopped)
    bus.change_owner(":1.1")
    monitor._on_download_activity()
    bus.change_owner(None)
    assert not monitor._file_browser_active
    assert monitor.file_activity_active
    assert events == [True]
    now[0] = 10.0
    monitor._poll()
    assert events == [True, False]
    bus.change_owner(":1.2")
    assert events == [True, False, True]
    backend.stop()


def test_media_loss_clears_focus_without_disconnecting_mpris():
    from mochi.media_activity import MprisMediaBackend
    bus = Bus()
    bus.state = (False, False, True, "browser")
    backend = MprisMediaBackend()
    backend._load_gio = bus.loader
    events = []
    backend.set_youtube_focus_changed_callback(events.append)
    assert backend.start()
    connection = backend._connection
    bus.change_owner(":1.1")
    assert backend._youtube_focused and backend._focused_browser
    bus.change_owner(None)
    assert not backend._youtube_focused and not backend._focused_browser
    assert backend.active and backend._connection is connection
    bus.change_owner(":1.2")
    assert events == [True, False, True]
    assert len(bus.subscriptions) == 3
    backend.stop()
    assert not bus.watches and not bus.subscriptions


def test_old_helper_without_snapshot_still_receives_events():
    bus = Bus()
    def unsupported(*args):
        raise RuntimeError("UnknownMethod")
    bus.call_sync = unsupported
    backend = GnomeShellPresenceBackend()
    backend._load_gio = bus.loader
    events = []
    backend.start(lambda: events.append("idle"), lambda: events.append("active"))
    bus.change_owner(":1.1")
    assert backend.active
    idle = next(args[-1] for args in bus.subscriptions.values() if args[2] == "UserIdle")
    idle(None, None, None, None, None, None)
    assert events == ["idle"]
    backend.stop()


def test_partial_subscription_failure_cleans_up_and_recovers_on_next_owner():
    bus = Bus()
    subscribe = bus.signal_subscribe
    def fail_second(*args):
        return 0 if bus.subscriptions else subscribe(*args)
    bus.signal_subscribe = fail_second
    backend = GnomeShellPresenceBackend()
    backend._load_gio = bus.loader
    backend.start(lambda: None, lambda: None)
    bus.change_owner(":1.1")
    assert not bus.subscriptions
    assert not backend.active
    assert bus.syncs == 0
    bus.signal_subscribe = subscribe
    bus.change_owner(":1.2")
    assert backend.active and len(bus.subscriptions) == 2
    backend.stop()


def test_typing_fallback_is_gated_and_loss_ends_session():
    from mochi.typing_activity import GnomeShellTypingPulseBackend, TypingActivityMonitor
    from test_typing_activity import _FakeBackend, _FakeGLib
    bus = Bus()
    helper = GnomeShellTypingPulseBackend()
    helper._load_gio = bus.loader
    fallback = _FakeBackend("fallback")
    events = []
    monitor = TypingActivityMonitor(
        on_typing_activity=lambda: events.append("typing"),
        on_typing_stopped=lambda: events.append("stopped"),
        backends=[helper, fallback],
    )
    monitor._glib = _FakeGLib()
    monitor._log_accessibility_coverage_hint = lambda: None
    assert monitor.start()
    for t in (1.0, 1.1, 1.2, 1.3, 1.4):
        fallback.emit(t)
    assert events == ["typing"]
    bus.change_owner(":1.1")
    fallback.emit(1.5)
    assert events == ["typing"]
    bus.change_owner(None)
    assert events == ["typing", "stopped"]
    assert not monitor.active
    for t in (2.0, 2.1, 2.2, 2.3, 2.4):
        fallback.emit(t)
    assert events[-1] == "typing"
    bus.change_owner(":1.2")
    assert len(bus.subscriptions) == 1
    assert bus.syncs == 0  # A pulse is an event, never replayed as state.
    monitor.stop()
    assert fallback.stop_calls == 1
    assert not bus.watches and not bus.subscriptions


def test_stop_while_waiting_prevents_late_attachment():
    bus = Bus()
    backend = GnomeShellPresenceBackend()
    backend._load_gio = bus.loader
    assert backend.start(lambda: None, lambda: None)
    backend.stop()
    bus.change_owner(":1.1")
    assert not backend.active
    assert not bus.watches and not bus.subscriptions
    assert bus.syncs == 0
