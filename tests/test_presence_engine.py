from __future__ import annotations

import random

from mochi.presence.context import AmbientContext, TypingIntensity
from mochi.presence.cooldowns import CooldownTracker
from mochi.presence.engine import PresenceEngine, PresenceTuning, speech_display_seconds
from mochi.presence.phrases import PhraseBank
from mochi.presence.signals import NetworkSignalAdapter, TypingIntensityTracker, UPowerSignalAdapter


class Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def generous_tuning(**overrides):
    tuning = PresenceTuning(
        ambient_min_seconds=0,
        ambient_max_seconds=0,
        ambient_silence_probability=0,
        global_cooldown_seconds=0,
        same_category_min_seconds=0,
        same_category_max_seconds=0,
        max_phrases_per_hour=50,
        typing_medium_sustain_seconds=10,
        typing_high_sustain_seconds=20,
        typing_comment_probability=1,
        return_probability=1,
        media_probability=1,
        system_event_probability=1,
        build_event_probability=1,
    )
    for key, value in overrides.items():
        setattr(tuning, key, value)
    return tuning


def test_cooldown_enforcement():
    clock = Clock()
    tracker = CooldownTracker(global_gap_seconds=300, max_per_hour=4, clock=clock)
    tracker.record("ambient", now=0, category_cooldown_seconds=1200)
    clock.advance(60)
    assert tracker.can_speak()[0] is False
    clock.advance(300)
    assert tracker.can_speak()[0] is True
    assert tracker.category_ready("ambient")[0] is False


def test_global_hourly_limit():
    clock = Clock()
    tracker = CooldownTracker(global_gap_seconds=0, max_per_hour=4, clock=clock)
    for _ in range(4):
        tracker.record("ambient", now=clock())
        clock.advance(10)
    assert tracker.can_speak()[0] is False
    clock.advance(3601)
    assert tracker.can_speak()[0] is True


def test_phrase_non_repetition():
    bank = PhraseBank(rng=random.Random(2), recent_limit=8)
    first = bank.choose("return_from_idle", remember=True)
    second = bank.choose("return_from_idle", remember=True)
    assert first != second


def test_category_selection_respects_context():
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(3), clock=Clock())
    context = AmbientContext(current_app_category="unknown", session_duration=10)
    for _ in range(20):
        assert engine._select_unsolicited_category(context) not in {"developer", "creative", "body_care", "rest"}


def test_vscode_makes_coding_phrases_more_likely_than_generic_editor():
    tuning = generous_tuning()
    editor_engine = PresenceEngine(tuning=tuning, rng=random.Random(17), clock=Clock())
    vscode_engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(17), clock=Clock())
    editor = AmbientContext(current_app_category="editor", session_duration=10)
    vscode = AmbientContext(current_app_category="vscode", session_duration=10)

    editor_coding = sum(
        editor_engine._select_unsolicited_category(editor) == "developer"
        for _ in range(1000)
    )
    vscode_coding = sum(
        vscode_engine._select_unsolicited_category(vscode) in {"developer", "vscode"}
        for _ in range(1000)
    )

    assert vscode_coding > editor_coding * 2


def test_vscode_specific_phrases_only_participate_in_vscode_context():
    editor_engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(5), clock=Clock())
    vscode_engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(5), clock=Clock())
    editor = AmbientContext(current_app_category="editor", session_duration=10)
    vscode = AmbientContext(current_app_category="vscode", session_duration=10)

    assert all(
        editor_engine._select_unsolicited_category(editor) != "vscode"
        for _ in range(500)
    )
    assert any(
        vscode_engine._select_unsolicited_category(vscode) == "vscode"
        for _ in range(500)
    )
    assert vscode_engine.phrases.choose("vscode")


def test_event_priority_prefers_system_reaction():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=clock)
    engine.emit("media_started", now=0)
    engine.emit("network_lost", now=0)
    action = engine.evaluate(AmbientContext(), now=0)
    assert action is not None
    assert action.event == "network_lost"
    assert action.priority == 40


def test_silence_probability_can_choose_silence():
    clock = Clock()
    tuning = generous_tuning(ambient_silence_probability=1)
    engine = PresenceEngine(tuning=tuning, rng=random.Random(1), clock=clock)
    action = engine.evaluate(AmbientContext(), now=0)
    assert action is None


def test_typing_threshold_levels():
    clock = Clock()
    tracker = TypingIntensityTracker(clock=clock, window_seconds=10, medium_events_per_second=1, high_events_per_second=3)
    for _ in range(12):
        tracker.record(clock())
        clock.advance(0.5)
    intensity, _ = tracker.snapshot(clock())
    assert intensity in (TypingIntensity.MEDIUM, TypingIntensity.HIGH)


def test_sustained_typing_required_before_comment():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(ambient_min_seconds=9999, ambient_max_seconds=9999), rng=random.Random(1), clock=clock)
    context = AmbientContext(typing_intensity=TypingIntensity.MEDIUM, typing_sustained_seconds=9)
    assert engine.evaluate(context, now=0) is None
    context.typing_sustained_seconds = 10
    action = engine.evaluate(context, now=0)
    assert action is not None
    assert action.category == "typing"


def test_body_care_throttling():
    clock = Clock()
    tracker = CooldownTracker(global_gap_seconds=0, max_per_hour=50, clock=clock)
    tracker.record("body_care", now=0, category_cooldown_seconds=3600)
    clock.advance(3599)
    assert tracker.category_ready("body_care")[0] is False
    clock.advance(2)
    assert tracker.category_ready("body_care")[0] is True


def test_event_collision_returns_at_most_one_action():
    clock = Clock()
    tuning = generous_tuning(global_cooldown_seconds=300)
    engine = PresenceEngine(tuning=tuning, rng=random.Random(1), clock=clock)
    engine.emit("network_lost", now=0)
    engine.emit("battery_low", now=0)
    first = engine.evaluate(AmbientContext(), now=0)
    assert first is not None
    engine.record_delivered(first, now=0)
    assert engine.evaluate(AmbientContext(), now=1) is None


def test_unavailable_signal_adapters_fail_closed():
    def fail_loader():
        raise RuntimeError("no dbus")

    battery = UPowerSignalAdapter(
        on_battery_low=lambda _percent: None,
        on_charging_started=lambda _percent: None,
        gio_loader=fail_loader,
    )
    network = NetworkSignalAdapter(
        on_lost=lambda: None,
        on_restored=lambda: None,
        gio_loader=fail_loader,
    )
    assert battery.start() is False
    assert network.start() is False
    assert battery.available is False
    assert network.available is False


def test_quiet_mode_suppression():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(quiet_mode=True), rng=random.Random(1), clock=clock)
    engine.force_ambient()
    assert engine.evaluate(AmbientContext(), now=0) is None


def test_dragging_and_pickup_suppression():
    clock = Clock()
    for state in ("dragged", "pickup"):
        engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=clock)
        engine.force_ambient()
        assert engine.evaluate(AmbientContext(mochi_state=state), now=0) is None


def test_sleeping_suppression():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=clock)
    engine.force_ambient()
    assert engine.evaluate(AmbientContext(mochi_state="sleeping"), now=0) is None


def test_user_return_detection():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=clock)
    engine.note_user_idle(now=0)
    engine.note_user_active(now=601)
    action = engine.evaluate(AmbientContext(), now=601)
    assert action is not None
    assert action.event == "user_returned"


def test_phrase_display_lifetime_logic():
    assert 3 <= speech_display_seconds("hello") <= 4
    assert 5 <= speech_display_seconds("this is a moderately long phrase for mochi") <= 7
    assert speech_display_seconds("x" * 100) <= 7


def test_app_category_adapter_accepts_only_coarse_allow_list():
    from mochi.presence.signals import AppCategorySignalAdapter

    seen = []
    adapter = AppCategorySignalAdapter(on_category_changed=seen.append)

    class Params:
        def __init__(self, value):
            self.value = value

        def unpack(self):
            return (self.value,)

    adapter._on_category_signal(None, None, None, None, None, Params("editor"))
    adapter._on_category_signal(None, None, None, None, None, Params("vscode"))
    adapter._on_category_signal(None, None, None, None, None, Params("secret-app-id"))
    adapter._on_category_signal(None, None, None, None, None, Params("pixel_art"))

    assert seen == ["editor", "vscode", "pixel_art"]
    assert adapter.category == "pixel_art"


def test_upower_reacts_only_to_meaningful_transitions():
    low = []
    charging = []
    adapter = UPowerSignalAdapter(
        on_battery_low=low.append,
        on_charging_started=charging.append,
        low_threshold=20,
    )

    class Value:
        def __init__(self, value):
            self.value = value

        def unpack(self):
            return self.value

    class Proxy:
        def __init__(self):
            self.percent = 50.0
            self.state = 2

        def get_cached_property(self, name):
            return Value(self.percent if name == "Percentage" else self.state)

    proxy = Proxy()
    adapter._proxy = proxy
    adapter._refresh(emit=False)
    proxy.percent = 19.0
    adapter._refresh(emit=True)
    adapter._refresh(emit=True)
    proxy.state = 1
    adapter._refresh(emit=True)

    assert low == [19.0]
    assert charging == [19.0]


def test_network_reacts_only_when_connected_state_changes():
    lost = []
    restored = []
    adapter = NetworkSignalAdapter(on_lost=lambda: lost.append(True), on_restored=lambda: restored.append(True))

    class Value:
        def __init__(self, value):
            self.value = value

        def unpack(self):
            return self.value

    class Proxy:
        state = 70

        def get_cached_property(self, _name):
            return Value(self.state)

    proxy = Proxy()
    adapter._proxy = proxy
    adapter._refresh(emit=False)
    proxy.state = 20
    adapter._refresh(emit=True)
    adapter._refresh(emit=True)
    proxy.state = 70
    adapter._refresh(emit=True)

    assert lost == [True]
    assert restored == [True]
