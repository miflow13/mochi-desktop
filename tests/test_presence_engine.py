from __future__ import annotations

import random
from unittest.mock import Mock, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")

from mochi.presence.context import AmbientContext, TypingIntensity
from mochi.presence.cooldowns import CooldownTracker
from mochi.presence.engine import (
    PresenceAction,
    PresenceEngine,
    PresenceTuning,
    speech_display_seconds,
)
from mochi.presence.integration import PresenceBuddyMixin
from mochi.presence.phrases import PhraseBank
from mochi.presence.signals import NetworkSignalAdapter, TypingIntensityTracker, UPowerSignalAdapter
from mochi.state import MochiState, StateMachine


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


def test_context_profiles_preserve_personality_and_add_relevant_categories():
    expected_context_categories = {
        "vscode": {"vscode", "developer"},
        "editor": {"developer"},
        "terminal": {"terminal", "developer"},
        "browser": {"browser"},
        "pixel_art": {"creative"},
    }
    generic = {"ambient", "encouragement", "companionship"}

    for index, (app_category, relevant) in enumerate(
        expected_context_categories.items()
    ):
        engine = PresenceEngine(
            tuning=generous_tuning(),
            rng=random.Random(100 + index),
            clock=Clock(),
        )
        context = AmbientContext(
            current_app_category=app_category,
            session_duration=10,
        )
        selected = {
            engine._select_unsolicited_category(context)
            for _ in range(2_000)
        }

        assert relevant <= selected
        assert selected & generic


def test_unknown_context_stays_generic_and_editor_never_uses_vscode_lines():
    generic = {"ambient", "encouragement", "companionship"}
    unknown_engine = PresenceEngine(
        tuning=generous_tuning(), rng=random.Random(31), clock=Clock()
    )
    editor_engine = PresenceEngine(
        tuning=generous_tuning(), rng=random.Random(32), clock=Clock()
    )
    unknown = AmbientContext(current_app_category="unknown", session_duration=10)
    editor = AmbientContext(current_app_category="editor", session_duration=10)

    assert {
        unknown_engine._select_unsolicited_category(unknown)
        for _ in range(1_000)
    } <= generic
    assert all(
        editor_engine._select_unsolicited_category(editor) != "vscode"
        for _ in range(1_000)
    )


def test_contextual_weighting_materially_increases_relevant_dialogue():
    relevant_by_context = {
        "vscode": {"vscode", "developer"},
        "editor": {"developer"},
        "terminal": {"terminal", "developer"},
        "browser": {"browser"},
        "pixel_art": {"creative"},
    }

    for index, (app_category, relevant) in enumerate(relevant_by_context.items()):
        engine = PresenceEngine(
            tuning=generous_tuning(),
            rng=random.Random(200 + index),
            clock=Clock(),
        )
        context = AmbientContext(
            current_app_category=app_category,
            session_duration=10,
        )
        relevant_count = sum(
            engine._select_unsolicited_category(context) in relevant
            for _ in range(1_000)
        )

        assert relevant_count >= 150, app_category


def test_event_priority_prefers_system_reaction():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=clock)
    engine.emit("media_started", now=0)
    engine.emit("network_lost", now=0)
    action = engine.evaluate(AmbientContext(), now=0)
    assert action is not None
    assert action.event == "network_lost"
    assert action.priority == 40


def test_network_restoration_invalidates_queued_offline_reaction():
    clock = Clock()
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=clock)
    engine.emit("network_lost", now=0)
    engine.emit("network_restored", now=1)

    action = engine.evaluate(AmbientContext(network_connected=True), now=1)

    assert action is not None
    assert action.event == "network_restored"


def test_network_event_is_dropped_when_current_baseline_disagrees():
    clock = Clock()
    engine = PresenceEngine(
        tuning=generous_tuning(ambient_min_seconds=9999, ambient_max_seconds=9999),
        rng=random.Random(1),
        clock=clock,
    )
    engine.emit("network_lost", now=0)

    action = engine.evaluate(AmbientContext(network_connected=True), now=1)

    assert action is None


def test_pending_system_event_can_defer_startup_greeting():
    engine = PresenceEngine(tuning=generous_tuning(), rng=random.Random(1), clock=Clock())
    engine.emit("media_started")
    assert engine.has_pending_event_at_least(40) is False
    engine.emit("network_lost")
    assert engine.has_pending_event_at_least(40) is True


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


@pytest.mark.parametrize(
    ("tuning_overrides", "context_overrides"),
    (
        ({"speech_enabled": False}, {}),
        ({"ambient_reactions_enabled": False}, {}),
        ({}, {"context_menu_open": True}),
        ({}, {"interaction_active": True}),
        ({}, {"transition_active": True}),
        ({}, {"overlay_visible": True}),
        ({}, {"mochi_state": "sleeping"}),
    ),
)
def test_context_routing_preserves_existing_suppression(
    tuning_overrides,
    context_overrides,
):
    engine = PresenceEngine(
        tuning=generous_tuning(**tuning_overrides),
        rng=random.Random(1),
        clock=Clock(),
    )

    assert engine.evaluate(
        AmbientContext(current_app_category="browser", **context_overrides),
        now=0,
    ) is None


def test_playing_media_keeps_priority_over_browser_chatter():
    engine = PresenceEngine(
        tuning=generous_tuning(), rng=random.Random(1), clock=Clock()
    )

    assert engine.evaluate(
        AmbientContext(current_app_category="browser", media_playing=True),
        now=0,
    ) is None


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


def test_app_focus_signal_emits_even_when_category_is_unchanged():
    from mochi.presence.signals import AppCategorySignalAdapter

    focus = []
    adapter = AppCategorySignalAdapter(
        on_category_changed=lambda _category: None,
        on_focus_changed=focus.append,
    )
    adapter.category = "browser"

    class Params:
        def unpack(self):
            return ("browser",)

    adapter._on_focus_signal(None, None, None, None, None, Params())

    assert focus == ["browser"]
    assert adapter.category == "browser"


def test_app_category_initial_snapshot_syncs_without_change_event():
    from mochi.presence.signals import AppCategorySignalAdapter

    snapshots = []
    changes = []
    adapter = AppCategorySignalAdapter(
        on_category_snapshot=snapshots.append,
        on_category_changed=changes.append,
    )

    adapter._on_state((False, False, False, "vscode"))

    assert adapter.category == "vscode"
    assert snapshots == ["vscode"]
    assert changes == []

    class Params:
        def unpack(self):
            return ("terminal",)

    adapter._on_category_signal(None, None, None, None, None, Params())

    assert snapshots == ["vscode"]
    assert changes == ["terminal"]


def test_presence_snapshot_updates_context_without_transition_side_effects():
    buddy = object.__new__(PresenceBuddyMixin)
    buddy._presence_app_category = "unknown"
    buddy._logger = Mock()
    buddy._on_user_active = Mock()
    buddy._schedule_vscode_coworking = Mock()
    buddy._stop_vscode_coworking = Mock()

    PresenceBuddyMixin._on_presence_app_category_snapshot(buddy, "vscode")

    assert buddy._presence_app_category == "vscode"
    buddy._on_user_active.assert_not_called()
    buddy._schedule_vscode_coworking.assert_not_called()
    buddy._stop_vscode_coworking.assert_not_called()


def test_real_category_change_runs_normal_transition_path():
    buddy = object.__new__(PresenceBuddyMixin)
    buddy._presence_app_category = "editor"
    buddy._logger = Mock()
    buddy._on_user_active = Mock()
    buddy._schedule_vscode_coworking = Mock()
    buddy._stop_vscode_coworking = Mock()
    buddy._vscode_coworking_active = False

    PresenceBuddyMixin._on_presence_app_category_changed(buddy, "vscode")

    assert buddy._presence_app_category == "vscode"
    buddy._on_user_active.assert_called_once_with()
    buddy._schedule_vscode_coworking.assert_called_once_with()
    buddy._stop_vscode_coworking.assert_not_called()


@pytest.mark.parametrize("app_category", ("vscode", "terminal"))
def test_contextual_speech_reaches_bubble_during_focused_app_coworking(
    app_category,
):
    """Exercise the live evaluator seam used while focused work owns TYPING."""
    action = PresenceAction(
        "speech",
        app_category,
        f"{app_category} context",
        10,
    )
    engine = Mock()
    engine.typing_snapshot.return_value = (TypingIntensity.LOW, 0.0)
    engine.evaluate.return_value = action
    bubble = Mock(visible=False)
    bubble.show.return_value = True

    buddy = object.__new__(PresenceBuddyMixin)
    buddy._presence_shutting_down = False
    buddy._ambient_presence_engine = engine
    buddy._media_monitor = None
    buddy._system_signal_monitor = None
    buddy._session_signal_monitor = None
    buddy._user_idle = False
    buddy._presence_active_session_started_at = 0.0
    buddy._presence_app_category = app_category
    buddy._context_menu_open = False
    buddy._press = None
    buddy._drag_started = False
    buddy._presence_bubble = bubble
    buddy.state = StateMachine()
    buddy.state.transition_to(MochiState.TYPING)

    with patch("mochi.presence.integration.time.monotonic", return_value=30.0):
        result = PresenceBuddyMixin._evaluate_ambient_presence(buddy)

    context = engine.evaluate.call_args.args[0]
    assert context.current_app_category == app_category
    assert context.mochi_state == "typing"
    bubble.show.assert_called_once_with(
        action.text,
        duration_seconds=action.display_seconds,
    )
    engine.record_delivered.assert_called_once_with(action, now=30.0)
    assert result


@pytest.mark.parametrize(
    ("app_category", "phrase_category"),
    (
        ("browser", "browser"),
        ("vscode", "vscode"),
        ("terminal", "terminal"),
        ("editor", "developer"),
        ("pixel_art", "creative"),
        ("unknown", "ambient"),
    ),
)
def test_contextual_preview_uses_production_app_categories(
    app_category,
    phrase_category,
):
    buddy = object.__new__(PresenceBuddyMixin)
    buddy._presence_app_category = app_category
    buddy._presence_context_preview_selector = None
    buddy._preview_presence_category = Mock()

    PresenceBuddyMixin._test_presence_contextual(buddy, Mock())

    buddy._preview_presence_category.assert_called_once_with(phrase_category)


@pytest.mark.parametrize(
    ("selected", "phrase_category"),
    (
        (1, "browser"),
        (2, "vscode"),
        (3, "terminal"),
        (4, "developer"),
        (5, "creative"),
    ),
)
def test_contextual_preview_can_force_each_coarse_context(
    selected,
    phrase_category,
):
    buddy = object.__new__(PresenceBuddyMixin)
    buddy._presence_app_category = "unknown"
    buddy._presence_context_preview_selector = Mock()
    buddy._presence_context_preview_selector.get_selected.return_value = selected
    buddy._preview_presence_category = Mock()

    PresenceBuddyMixin._test_presence_contextual(buddy, Mock())

    buddy._preview_presence_category.assert_called_once_with(phrase_category)


def test_developer_preview_does_not_spend_production_cooldowns():
    engine = PresenceEngine(
        tuning=generous_tuning(), rng=random.Random(1), clock=Clock()
    )
    buddy = object.__new__(PresenceBuddyMixin)
    buddy._ambient_presence_engine = engine
    buddy._presence_bubble = Mock()
    buddy._presence_bubble.show.return_value = True
    buddy._dismiss_presence_bubble = Mock()
    buddy._logger = Mock()
    history_before = tuple(engine.cooldowns._history)

    PresenceBuddyMixin._preview_presence_category(buddy, "browser")

    assert tuple(engine.cooldowns._history) == history_before


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
