"""Exercise suspend/unlock ordering and the greeting's dialogue ownership."""

import random
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mochi.presence.context import AmbientContext
from mochi.presence.engine import PresenceEngine, PresenceTuning
from mochi.presence.phrases import PHRASES
from mochi.presence.session import SessionSignalMonitor
from mochi.state import MochiState, StateMachine


class Variant:
    def __init__(self, _signature, value):
        self.value = value

    def unpack(self):
        return self.value


class SessionBus:
    def __init__(self, *, locked=False):
        self.properties = {"LockedHint": locked, "Active": True}
        self.subscriptions = {}
        self.next_id = 0
        self.fail_refresh = False

    def loader(self):
        gio = SimpleNamespace(
            BusType=SimpleNamespace(SYSTEM=1),
            DBusCallFlags=SimpleNamespace(NONE=0),
            DBusSignalFlags=SimpleNamespace(NONE=0),
            bus_get_sync=lambda *_: self,
        )
        glib = SimpleNamespace(Variant=Variant, VariantType=SimpleNamespace(new=lambda s: s))
        return gio, glib

    def call_sync(self, _name, path, _interface, method, parameters, *_rest):
        if method == "GetSession":
            assert parameters.unpack() == ("auto",)
            return Variant("(o)", ("/org/freedesktop/login1/session/7",))
        assert method == "GetAll"
        assert path == "/org/freedesktop/login1/session/7"
        if self.fail_refresh:
            raise RuntimeError("session unavailable")
        return Variant("(a{sv})", (dict(self.properties),))

    def signal_subscribe(self, name, interface, signal, path, arg0, flags, callback):
        self.next_id += 1
        self.subscriptions[self.next_id] = (signal, callback)
        return self.next_id

    def signal_unsubscribe(self, ident):
        del self.subscriptions[ident]

    def emit(self, signal, parameters):
        for subscribed_signal, callback in tuple(self.subscriptions.values()):
            if subscribed_signal == signal:
                callback(None, None, None, None, signal, Variant("", parameters))

    def sleep(self, sleeping):
        self.emit("PrepareForSleep", (sleeping,))

    def change(self, **properties):
        self.properties.update(properties)
        self.emit("PropertiesChanged", (SessionSignalMonitor.SESSION_INTERFACE, properties, []))


def start_monitor(bus, events):
    monitor = SessionSignalMonitor(
        on_away=lambda: events.append("away"),
        on_returned=lambda: events.append("returned"),
        gio_loader=bus.loader,
    )
    assert monitor.start()
    return monitor


@pytest.mark.parametrize("unlock_before_resume", [True, False])
def test_suspend_and_unlock_produce_one_return(unlock_before_resume):
    bus, events = SessionBus(), []
    monitor = start_monitor(bus, events)
    assert events == []  # Initial active/unlocked state is not a return.
    bus.change(LockedHint=True)
    bus.sleep(True)
    bus.sleep(True)
    if unlock_before_resume:
        bus.change(LockedHint=False)
        assert monitor.blocked
        bus.sleep(False)
    else:
        bus.sleep(False)
        assert monitor.blocked
        bus.change(LockedHint=False)
    bus.sleep(False)
    bus.change(LockedHint=False)
    assert events == ["away", "returned"]
    assert not monitor.blocked


def test_resume_reads_lock_before_its_property_signal_arrives():
    bus, events = SessionBus(), []
    monitor = start_monitor(bus, events)
    bus.sleep(True)
    bus.properties["LockedHint"] = True
    bus.sleep(False)
    assert monitor.blocked
    assert events == ["away"]
    bus.change(LockedHint=False)
    assert events == ["away", "returned"]


def test_repeated_unlocked_suspend_cycles_and_shutdown():
    bus, events = SessionBus(), []
    monitor = start_monitor(bus, events)
    assert monitor.start()
    assert len(bus.subscriptions) == 2
    for _ in range(2):
        bus.sleep(True)
        bus.sleep(False)
    assert events == ["away", "returned", "away", "returned"]
    monitor.stop()
    monitor.stop()
    bus.sleep(True)
    assert not bus.subscriptions
    assert events == ["away", "returned", "away", "returned"]


def test_initial_locked_session_waits_for_unlock():
    bus, events = SessionBus(locked=True), []
    monitor = start_monitor(bus, events)
    assert monitor.blocked
    assert events == ["away"]
    bus.change(LockedHint=False)
    assert events == ["away", "returned"]


def test_failed_resume_snapshot_waits_for_known_session_state():
    bus, events = SessionBus(), []
    monitor = start_monitor(bus, events)
    bus.sleep(True)
    bus.fail_refresh = True
    bus.sleep(False)
    assert monitor.blocked
    bus.fail_refresh = False
    bus.change(LockedHint=False)
    assert events == ["away", "returned"]


def test_unavailable_logind_is_optional_and_cleans_subscriptions():
    bus = SessionBus()
    bus.fail_refresh = True
    monitor = SessionSignalMonitor(on_away=lambda: None, on_returned=lambda: None,
                                   gio_loader=bus.loader)
    assert not monitor.start()
    assert not monitor.available
    assert not bus.subscriptions


def engine_for_session():
    return PresenceEngine(
        tuning=PresenceTuning(ambient_min_seconds=9999, ambient_max_seconds=9999,
                              system_event_probability=1),
        rng=random.Random(1), clock=lambda: 0,
    )


@pytest.mark.parametrize("context", [
    AmbientContext(user_active=False), AmbientContext(mochi_state="waking"),
    AmbientContext(context_menu_open=True), AmbientContext(overlay_visible=True),
    AmbientContext(interaction_active=True), AmbientContext(application_shutting_down=True),
])
def test_return_greeting_waits_for_ownership_then_delivers_once(context):
    engine = engine_for_session()
    engine.note_session_returned()
    assert engine.evaluate(context, now=0) is None
    action = engine.evaluate(AmbientContext(), now=300)
    assert action.event == "welcome_back"
    assert action.text in PHRASES["welcome_back"]
    engine.record_delivered(action, now=300)
    assert engine.evaluate(AmbientContext(), now=400) is None


def test_system_event_and_cooldown_defer_but_do_not_lose_welcome():
    engine = engine_for_session()
    engine.note_session_returned()
    engine.emit("network_lost", now=0)
    context = AmbientContext(network_connected=False)
    action = engine.evaluate(context, now=0)
    assert action.event == "network_lost"
    engine.record_delivered(action, now=0)
    assert engine.evaluate(context, now=1) is None
    assert engine.evaluate(context, now=26).event == "welcome_back"


def test_suspend_discards_environment_events_and_preserves_user_request():
    engine = engine_for_session()
    engine.emit("network_lost")
    engine.emit("media_started")
    engine.force_contextual("developer")
    engine.note_session_away()
    engine.note_user_idle(now=0)
    engine.note_session_returned()
    engine.note_user_active(now=700)
    assert engine.evaluate(AmbientContext(), now=1).event == "force_contextual"
    action = engine.evaluate(AmbientContext(), now=2)
    assert action.event == "welcome_back"
    engine.record_delivered(action, now=2)
    assert engine.evaluate(AmbientContext(), now=700) is None


def test_integration_wakes_and_cancels_duplicate_startup(monkeypatch):
    from mochi.presence.integration import PresenceBuddyMixin
    from mochi.presence import integration

    removed, active = [], []
    monkeypatch.setattr(integration.GLib, "source_remove", removed.append)
    buddy = SimpleNamespace(
        _presence_shutting_down=False, _preview_mode=False,
        _presence_startup_source_id=12, _ambient_presence_engine=engine_for_session(),
        _on_user_active=lambda: active.append(True),
    )
    PresenceBuddyMixin._on_presence_session_returned(buddy)
    assert active == [True]
    assert removed == [12]
    assert buddy._presence_startup_source_id is None
    assert buddy._ambient_presence_engine.evaluate(AmbientContext(), now=0).event == "welcome_back"


def test_production_buddy_uses_the_centralized_startup_flow():
    from mochi.presence.click_dialogue import PresenceBuddy
    from mochi.presence.integration import PresenceBuddyMixin

    assert PresenceBuddy._show_startup_greeting is PresenceBuddyMixin._show_startup_greeting


def test_startup_wave_is_scheduled_only_once(monkeypatch):
    from mochi.presence import integration
    from mochi.presence.integration import PresenceBuddyMixin

    scheduled = []
    monkeypatch.setattr(
        integration.GLib,
        "idle_add",
        lambda callback: scheduled.append(callback) or 23,
    )
    buddy = SimpleNamespace(
        _preview_mode=False,
        _presence_shutting_down=False,
        _presence_startup_wave_played=False,
        _presence_startup_wave_source_id=None,
        _play_startup_wave=Mock(),
    )

    PresenceBuddyMixin._schedule_startup_wave(buddy)
    PresenceBuddyMixin._schedule_startup_wave(buddy)

    assert scheduled == [buddy._play_startup_wave]
    assert buddy._presence_startup_wave_source_id == 23


def test_startup_wave_plays_once_and_returns_source_remove():
    from mochi.presence.integration import PresenceBuddyMixin

    buddy = SimpleNamespace(
        _preview_mode=False,
        _presence_shutting_down=False,
        _presence_startup_wave_played=False,
        _presence_startup_wave_source_id=23,
        state=StateMachine(),
        _is_idle_visual_active=Mock(return_value=True),
        _play_autonomous_catalogue_emote=Mock(return_value=True),
    )

    first = PresenceBuddyMixin._play_startup_wave(buddy)
    second = PresenceBuddyMixin._play_startup_wave(buddy)

    assert first is False
    assert second is False
    assert buddy._presence_startup_wave_source_id is None
    assert buddy._presence_startup_wave_played is True
    buddy._play_autonomous_catalogue_emote.assert_called_once_with("wave")


def test_startup_wave_does_not_interrupt_a_state_that_claimed_mochi_first():
    from mochi.presence.integration import PresenceBuddyMixin

    state = StateMachine()
    state.transition_to(MochiState.TYPING)
    buddy = SimpleNamespace(
        _preview_mode=False,
        _presence_shutting_down=False,
        _presence_startup_wave_played=False,
        _presence_startup_wave_source_id=23,
        state=state,
        _is_idle_visual_active=Mock(return_value=False),
        _play_autonomous_catalogue_emote=Mock(),
    )

    PresenceBuddyMixin._play_startup_wave(buddy)

    buddy._play_autonomous_catalogue_emote.assert_not_called()
    assert buddy._presence_startup_wave_played is True


@pytest.mark.parametrize("flag", ["_preview_mode", "_presence_shutting_down"])
def test_integration_ignores_resume_during_preview_or_shutdown(flag):
    from mochi.presence.integration import PresenceBuddyMixin

    buddy = SimpleNamespace(_presence_shutting_down=False, _preview_mode=False)
    setattr(buddy, flag, True)
    PresenceBuddyMixin._on_presence_session_returned(buddy)
