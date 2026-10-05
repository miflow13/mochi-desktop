"""Regression coverage for active-window curiosity."""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cairo
import pytest

from mochi.focus import FocusPlan, FocusSession
from mochi.presence import curiosity
from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
from mochi.presence.curiosity import ActiveWindowCuriosityMixin
from mochi.presence.idle_look import IdleLookMixin
from mochi.presence.signals import AppCategorySignalAdapter
from mochi.state import MochiState, PresentationState, StateMachine


class _CuriosityBase:
    def __init__(self) -> None:
        self._presence_app_category = "browser"
        self._preview_mode = False
        self._presence_shutting_down = False
        self._user_idle = False
        self._context_menu_open = False
        self._press = None
        self._drag_started = False
        self._ambient_presence_engine = SimpleNamespace(
            tuning=SimpleNamespace(ambient_reactions_enabled=True, quiet_mode=False)
        )
        self.state = StateMachine()
        self.queue_draw = Mock()
        self._logger = Mock()
        self._placement = None
        self.idle_visual = True
        self.beats: list[str] = []
        self.focus_events: list[str] = []
        self.tab_events = 0
        self.base_press_args = None
        self.base_shutdown_called = False

    def _play_idle_beat(self, name: str) -> bool:
        if not self.idle_visual:
            return False
        self.beats.append(name)
        return True

    def _on_presence_app_category_changed(self, category: str) -> None:
        self._presence_app_category = category

    def _on_presence_app_focus_changed(self, category: str) -> None:
        self.focus_events.append(category)

    def _on_presence_browser_tab_changed(self) -> None:
        self.tab_events += 1

    def _draw(self, _area, context, _width: int, _height: int) -> None:
        context.rectangle(48, 78, 16, 24)
        context.set_source_rgba(0.2, 0.6, 0.3, 1.0)
        context.fill()

    def _tick(self) -> bool:
        return True

    def _on_pressed(self, *args) -> None:
        self.base_press_args = args

    def shutdown_presence(self) -> None:
        self.base_shutdown_called = True


class CuriosityHarness(ActiveWindowCuriosityMixin, _CuriosityBase):
    pass


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now


@pytest.fixture
def clock(monkeypatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(
        ActiveWindowCuriosityMixin, "_curiosity_now", lambda _self: fake.now
    )
    return fake


def _busy(buddy: CuriosityHarness, state: MochiState = MochiState.TYPING) -> None:
    buddy.idle_visual = False
    buddy.state.transition_to(state)


# -- Clock and pacing ---------------------------------------------------------


def test_clock_prefers_boottime() -> None:
    calls = []
    fake = SimpleNamespace(
        CLOCK_BOOTTIME=7,
        clock_gettime=lambda clock_id: calls.append(clock_id) or 42.0,
        monotonic=lambda: 1.0,
    )

    assert curiosity._boottime_seconds(fake) == 42.0
    assert calls == [7]


def test_clock_falls_back_without_boottime() -> None:
    fake = SimpleNamespace(monotonic=lambda: 9.5)

    assert curiosity._boottime_seconds(fake) == 9.5


def test_clock_falls_back_when_boottime_errors() -> None:
    def broken(_clock_id):
        raise OSError("unsupported")

    fake = SimpleNamespace(CLOCK_BOOTTIME=7, clock_gettime=broken, monotonic=lambda: 3.0)

    assert curiosity._boottime_seconds(fake) == 3.0


def test_habituated_cooldown_grows_and_clamps() -> None:
    cooldown = ActiveWindowCuriosityMixin._habituated_cooldown

    assert cooldown(20.0, 120.0, 0) == 20.0
    assert cooldown(20.0, 120.0, 1) == 30.0
    assert cooldown(20.0, 120.0, 2) == 45.0
    assert cooldown(20.0, 120.0, 10) == 120.0
    assert cooldown(120.0, 600.0, 4) == 600.0


def test_habituated_cooldown_caps_a_huge_streak() -> None:
    # 1.5 ** 1752 overflows a float. A very long busy session must still get
    # the cap, not an OverflowError from inside the GLib callback.
    cooldown = ActiveWindowCuriosityMixin._habituated_cooldown

    assert cooldown(20.0, 120.0, 10_000) == 120.0
    assert cooldown(120.0, 600.0, 10_000) == 600.0


# -- Triggers -----------------------------------------------------------------


def test_window_focus_pulse_schedules_debounced_reaction() -> None:
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add", return_value=11) as timeout_add:
        buddy._on_presence_app_focus_changed("browser")

    assert buddy.focus_events == ["browser"]
    timeout_add.assert_called_once_with(
        buddy.CURIOSITY_DEBOUNCE_MS, buddy._fire_curiosity
    )
    assert buddy._curiosity_source_id == 11
    assert buddy._curiosity_pending_reason == "window:browser"


def test_unrecognized_focus_category_is_ignored() -> None:
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_app_focus_changed("spreadsheet")

    timeout_add.assert_not_called()
    assert buddy._curiosity_source_id is None


@pytest.mark.parametrize("category", sorted(AppCategorySignalAdapter.ALLOWED))
def test_every_category_the_adapter_accepts_schedules_curiosity(category) -> None:
    # The allow-list lives in AppCategorySignalAdapter; curiosity must follow it
    # so a newly accepted category is never silently ignored here.
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add", return_value=3) as timeout_add:
        buddy._on_presence_app_focus_changed(category)

    timeout_add.assert_called_once_with(
        buddy.CURIOSITY_DEBOUNCE_MS, buddy._fire_curiosity
    )
    assert buddy._curiosity_pending_reason == f"window:{category}"


def test_category_reclassification_does_not_trigger_curiosity() -> None:
    # Ported from PR #133: categories can change while focus stays on the same
    # window (e.g. late identity), and only the focus/tab pulses mean attention moved.
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_app_category_changed("terminal")

    assert buddy._presence_app_category == "terminal"
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None
    timeout_add.assert_not_called()


def test_tab_pulses_restart_one_settle_timer() -> None:
    buddy = CuriosityHarness()

    with patch.object(
        curiosity.GLib, "timeout_add", side_effect=[1, 2, 3]
    ) as timeout_add, patch.object(curiosity.GLib, "source_remove") as source_remove:
        for _ in range(3):
            buddy._on_presence_browser_tab_changed()

    assert buddy.tab_events == 3
    assert [call.args[0] for call in timeout_add.call_args_list] == [1500, 1500, 1500]
    assert [call.args[0] for call in source_remove.call_args_list] == [1, 2]
    assert buddy._curiosity_source_id == 3
    assert buddy._curiosity_pending_reason == "tab"


def test_window_pulse_replaces_pending_tab_settle() -> None:
    buddy = CuriosityHarness()

    with patch.object(
        curiosity.GLib, "timeout_add", side_effect=[5, 6]
    ) as timeout_add, patch.object(curiosity.GLib, "source_remove") as source_remove:
        buddy._on_presence_browser_tab_changed()
        buddy._on_presence_app_focus_changed("terminal")

    source_remove.assert_called_once_with(5)
    assert timeout_add.call_args_list[-1].args[0] == buddy.CURIOSITY_DEBOUNCE_MS
    assert buddy._curiosity_source_id == 6
    assert buddy._curiosity_pending_reason == "window:terminal"


def test_nothing_is_scheduled_while_shutting_down() -> None:
    buddy = CuriosityHarness()
    buddy._presence_shutting_down = True

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_browser_tab_changed()

    timeout_add.assert_not_called()


def test_nothing_is_scheduled_in_preview_mode() -> None:
    buddy = CuriosityHarness()
    buddy._preview_mode = True

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_browser_tab_changed()
        buddy._on_presence_app_focus_changed("terminal")

    assert buddy.tab_events == 1
    assert buddy.focus_events == ["terminal"]
    timeout_add.assert_not_called()
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None


def test_firing_runs_the_pending_reaction_once(clock) -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 9
    buddy._curiosity_pending_reason = "tab"

    assert buddy._fire_curiosity() == curiosity.GLib.SOURCE_REMOVE

    assert buddy.beats == ["investigate"]
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None

    # A repeated fire must not replay the reaction. Move far past every cooldown
    # first, so only a leftover pending reason (not pacing) could make it react.
    clock.now += 10_000.0
    buddy.queue_draw.reset_mock()
    assert buddy._fire_curiosity() == curiosity.GLib.SOURCE_REMOVE

    assert buddy.beats == ["investigate"]
    assert buddy._curiosity_cue_active is False
    buddy.queue_draw.assert_not_called()


# -- Reaction ladder ----------------------------------------------------------


def test_idle_trigger_plays_investigate_beat(clock) -> None:
    buddy = CuriosityHarness()

    assert buddy._react_to_curiosity("tab") == "beat"

    assert buddy.beats == ["investigate"]
    assert buddy._curiosity_cue_active is False
    assert buddy.state.current is MochiState.IDLE


def test_busy_trigger_shows_cue_without_changing_state(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)

    assert buddy._react_to_curiosity("window:terminal") == "cue"

    assert buddy.beats == []
    assert buddy._curiosity_cue_active is True
    assert buddy.state.current is MochiState.TYPING
    buddy.queue_draw.assert_called_once_with()


def test_trigger_inside_reaction_gap_is_dropped(clock) -> None:
    buddy = CuriosityHarness()
    assert buddy._react_to_curiosity("tab") == "beat"

    clock.now += 10.0
    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy.beats == ["investigate"]


def test_trigger_inside_beat_cooldown_falls_back_to_cue(clock) -> None:
    buddy = CuriosityHarness()
    assert buddy._react_to_curiosity("tab") == "beat"

    clock.now += 31.0  # past the habituated 30 s gap, inside the 180 s beat cooldown
    assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy.beats == ["investigate"]


def test_idle_trigger_soon_after_a_cue_is_dropped_not_beat(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"

    buddy.idle_visual = True
    buddy.state.transition_to(MochiState.IDLE)
    clock.now += 25.0
    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy.beats == []


def test_habituation_lengthens_the_gap(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"  # streak 1, next gap 30 s
    clock.now += 30.0
    assert buddy._react_to_curiosity("tab") == "cue"  # streak 2, next gap 45 s
    clock.now += 44.0
    assert buddy._react_to_curiosity("tab") == "drop"
    clock.now += 1.0
    assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy._curiosity_streak == 3


def test_long_quiet_period_resets_habituation(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    for step in (0.0, 30.0, 45.0):
        clock.now += step
        assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy._curiosity_streak == 3

    clock.now += buddy.CURIOSITY_HABITUATION_RESET_SECONDS
    assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy._curiosity_streak == 1


def test_suppressed_trigger_does_not_touch_habituation(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"
    clock.now += 30.0
    assert buddy._react_to_curiosity("tab") == "cue"
    seeded_at = clock.now
    assert buddy._curiosity_streak == 2
    assert buddy._curiosity_last_trigger_at == seeded_at

    # Past the reset window, an eligible trigger would zero the streak and stamp
    # a new last-trigger time. A suppressed one must leave both exactly as they were.
    buddy._ambient_presence_engine.tuning.quiet_mode = True
    clock.now += buddy.CURIOSITY_HABITUATION_RESET_SECONDS + 1.0
    assert buddy._react_to_curiosity("tab") == "drop"

    assert buddy._curiosity_streak == 2
    assert buddy._curiosity_last_trigger_at == seeded_at
    assert buddy.beats == []


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("_user_idle", True),
        ("_context_menu_open", True),
        ("_press", (12.0, 18.0)),
        ("_drag_started", True),
        ("_preview_mode", True),
        ("_presence_shutting_down", True),
    ],
)
def test_direct_and_lifecycle_suppression(clock, attribute, value) -> None:
    buddy = CuriosityHarness()
    setattr(buddy, attribute, value)

    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy.beats == []
    assert buddy._curiosity_cue_active is False


def test_special_presentation_suppresses(clock) -> None:
    buddy = CuriosityHarness()
    buddy.state.presentation = PresentationState.LEVEL_UP

    assert buddy._react_to_curiosity("tab") == "drop"


@pytest.mark.parametrize("state", [MochiState.SLEEPING, MochiState.WAKING])
def test_sleep_suppresses(clock, state) -> None:
    buddy = CuriosityHarness()
    _busy(buddy, state)

    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy._curiosity_last_trigger_at == -math.inf


def test_ambient_reactions_off_suppresses(clock) -> None:
    buddy = CuriosityHarness()
    buddy._ambient_presence_engine.tuning.ambient_reactions_enabled = False

    assert buddy._react_to_curiosity("tab") == "drop"


class FocusAwareHarness(CuriosityHarness):
    """Adds the two FocusSessionMixin predicates behind the quiet-focus policy."""

    def __init__(self) -> None:
        super().__init__()
        self.focus_working = False
        self.focus_thinking = False

    def _focus_should_work(self) -> bool:
        return self.focus_working

    def _focus_should_think(self) -> bool:
        return self.focus_thinking


def test_focus_work_drops_without_touching_habituation(clock) -> None:
    # Focus work runs as COMPUTER, a cue-allowed state, so only the focus check
    # keeps curiosity quiet here.
    buddy = FocusAwareHarness()
    _busy(buddy, MochiState.COMPUTER)
    assert buddy._react_to_curiosity("tab") == "cue"
    clock.now += 30.0
    assert buddy._react_to_curiosity("tab") == "cue"
    seeded_at = clock.now
    buddy._clear_curiosity_cue()
    buddy.queue_draw.reset_mock()

    # Past the reset window, an eligible trigger would zero the streak and stamp
    # a new last-trigger time. A focus-suppressed one must leave both alone.
    buddy.focus_working = True
    clock.now += buddy.CURIOSITY_HABITUATION_RESET_SECONDS + 1.0
    assert buddy._react_to_curiosity("window:browser") == "drop"

    assert buddy._curiosity_streak == 2
    assert buddy._curiosity_last_trigger_at == seeded_at
    assert buddy._curiosity_cue_active is False
    assert buddy.beats == []
    buddy.queue_draw.assert_not_called()


def test_focus_thinking_drops(clock) -> None:
    # Focus setup or the user menu owns a thinking visual; standing idle
    # underneath must not turn into an investigate beat.
    buddy = FocusAwareHarness()
    buddy.focus_thinking = True

    assert buddy._react_to_curiosity("window:browser") == "drop"

    assert buddy.beats == []
    assert buddy._curiosity_cue_active is False
    assert buddy._curiosity_last_trigger_at == -math.inf


def test_active_cue_clears_on_tick_once_focus_starts(clock) -> None:
    buddy = FocusAwareHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("window:terminal") == "cue"

    # Starting Focus moves Mochi to COMPUTER, which alone would keep the cue.
    buddy.focus_working = True
    buddy.state.transition_to(MochiState.COMPUTER)
    clock.now += 0.2
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is False


def test_watching_drops_through_the_ladder(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy, MochiState.WATCHING)

    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy._curiosity_cue_active is False
    assert buddy._curiosity_last_trigger_at == clock.now


# -- Lifecycle ----------------------------------------------------------------


def test_press_cancels_pending_and_clears_cue() -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 42
    buddy._curiosity_pending_reason = "tab"
    buddy._curiosity_cue_active = True

    with patch.object(curiosity.GLib, "source_remove") as source_remove:
        buddy._on_pressed("gesture", 1, 12.0, 18.0)

    source_remove.assert_called_once_with(42)
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None
    assert buddy._curiosity_cue_active is False
    assert buddy.base_press_args == ("gesture", 1, 12.0, 18.0)


def test_shutdown_cancels_pending_and_preserves_chain() -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 42
    buddy._curiosity_pending_reason = "window:terminal"
    buddy._curiosity_cue_active = True

    with patch.object(curiosity.GLib, "source_remove") as source_remove:
        buddy.shutdown_presence()

    source_remove.assert_called_once_with(42)
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_cue_active is False
    assert buddy.base_shutdown_called is True


def test_cue_expires_without_changing_state(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"

    clock.now += buddy.CURIOSITY_CUE_DURATION_SECONDS
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is False
    assert buddy.state.current is MochiState.TYPING


def test_cue_continues_across_cue_allowed_states(clock) -> None:
    buddy = CuriosityHarness()
    buddy.idle_visual = False  # IDLE state but not the idle visual: cue, not beat
    assert buddy._react_to_curiosity("window:vscode") == "cue"

    buddy.state.transition_to(MochiState.TYPING)
    buddy.queue_draw.reset_mock()
    clock.now += 0.7
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is True
    buddy.queue_draw.assert_called_once_with()


def test_direct_press_clears_active_cue_on_next_tick(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"

    buddy._press = (1.0, 2.0)
    clock.now += 0.2
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is False


# -- Rendering ----------------------------------------------------------------


def _render(buddy: CuriosityHarness, size: int = 112) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    context = cairo.Context(surface)
    buddy._draw(None, context, size, size)
    surface.flush()
    return bytes(surface.get_data())


def test_cue_render_differs_from_baseline(clock) -> None:
    buddy = CuriosityHarness()
    baseline = _render(buddy)

    buddy._curiosity_cue_active = True
    buddy._curiosity_cue_started_at = clock.now - 0.6
    curious = _render(buddy)

    assert curious != baseline


def test_lean_offsets_are_whole_pixels() -> None:
    buddy = CuriosityHarness()

    for progress in (0.05, 0.1, 0.17, 0.4, 0.75, 0.9, 0.99):
        for scale in (0.57, 1.0, 1.37, 2.29):
            for direction in (1, -1):
                dx, dy = buddy._curiosity_lean_offsets(progress, direction, scale)
                assert isinstance(dx, int) and isinstance(dy, int)


def test_draw_translates_by_whole_pixels(clock) -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_cue_active = True
    buddy._curiosity_cue_started_at = clock.now - 0.1  # mid ease-in
    context = Mock()

    buddy._draw(None, context, 137, 137)

    dx, dy = context.translate.call_args_list[0].args
    assert isinstance(dx, int) and isinstance(dy, int)


@pytest.mark.parametrize(("size", "bubble"), [(64, False), (79, False), (80, True), (112, True)])
def test_bubble_only_at_readable_sizes(clock, size, bubble) -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_cue_active = True
    buddy._curiosity_cue_started_at = clock.now - 0.6

    with patch.object(ActiveWindowCuriosityMixin, "_draw_curiosity_bubble") as draw_bubble:
        _render(buddy, size)

    assert draw_bubble.called is bubble


# -- Production composition ---------------------------------------------------


@pytest.mark.parametrize("buddy_type", [PresenceBuddy, PresenceX11Buddy])
def test_curiosity_wraps_the_idle_beat_owner(buddy_type) -> None:
    bases = buddy_type.__bases__
    assert bases.index(ActiveWindowCuriosityMixin) + 1 == bases.index(IdleLookMixin)


@pytest.mark.parametrize("buddy_type", [PresenceBuddy, PresenceX11Buddy])
def test_production_buddies_keep_curiosity_quiet_during_focus(buddy_type) -> None:
    # Curiosity looks the focus predicates up defensively so lightweight
    # harnesses work. Real buddies must resolve them, or a rename in
    # FocusSessionMixin would silently let curiosity interrupt Focus.
    buddy = buddy_type.__new__(buddy_type)
    buddy.state = StateMachine()
    buddy._focus_session = None
    buddy._focus_context_menu_visible = False
    buddy._focus_setup_pending = False
    buddy._focus_setup_visible = False
    assert buddy._curiosity_allowed() is True

    buddy._focus_session = FocusSession(FocusPlan())
    assert buddy._curiosity_allowed() is False

    buddy._focus_session = None
    buddy._focus_setup_pending = True
    assert buddy._curiosity_allowed() is False


# -- Diagnostics --------------------------------------------------------------


def _debug_messages(buddy: CuriosityHarness) -> list[str]:
    return [
        call.args[0] % call.args[1:] for call in buddy._logger.debug.call_args_list
    ]


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        (lambda b: setattr(b._ambient_presence_engine.tuning, "quiet_mode", True), "quiet mode"),
        (lambda b: setattr(b._ambient_presence_engine.tuning, "ambient_reactions_enabled", False), "ambient reactions off"),
        (lambda b: setattr(b, "_user_idle", True), "user idle"),
        (lambda b: setattr(b, "_context_menu_open", True), "context menu"),
        (lambda b: setattr(b, "_drag_started", True), "dragging"),
        (lambda b: setattr(b, "_focus_should_work", lambda: True), "focus session"),
        (lambda b: setattr(b.state, "presentation", PresentationState.LEVEL_UP), "presentation LEVEL_UP"),
        (lambda b: _busy(b, MochiState.SLEEPING), "sleeping"),
    ],
)
def test_suppressed_drop_logs_its_cause(clock, setup, expected) -> None:
    buddy = CuriosityHarness()
    setup(buddy)

    assert buddy._react_to_curiosity("tab") == "drop"

    assert f"[curiosity] tab -> drop (suppressed: {expected})" in _debug_messages(buddy)


def test_cooldown_drop_logs_remaining_wait(clock) -> None:
    buddy = CuriosityHarness()
    assert buddy._react_to_curiosity("window:browser") == "beat"
    buddy._logger.debug.reset_mock()

    clock.now += 5.0
    assert buddy._react_to_curiosity("tab") == "drop"

    # streak 1 -> 30 s gap, 5 s elapsed -> 25 s left
    assert "[curiosity] tab -> drop (cooldown, 25s left)" in _debug_messages(buddy)


def test_state_drop_logs_the_blocking_state(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy, MochiState.WATCHING)

    assert buddy._react_to_curiosity("tab") == "drop"

    assert "[curiosity] tab -> drop (state WATCHING)" in _debug_messages(buddy)
