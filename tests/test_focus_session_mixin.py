"""Focus-session lifecycle integration seams without a live GTK desktop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.focus import FocusPhase, FocusPlan, FocusSession
from mochi.presence.focus_session import FocusSessionMixin, FocusWindow
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, StateMachine


class _Base:
    def _show_context_menu(self, *args) -> None:
        self.base_show_context_calls += 1
        self._context_menu_open = True

    def _on_context_menu_closed(self, _popover) -> None:
        self.base_close_context_calls += 1
        self._context_menu_open = False

    def _start_typing_emote(self) -> bool:
        self.base_typing_calls += 1
        return True

    def _maybe_resume_ambient_activity(self) -> bool:
        self.base_resume_calls += 1
        return False

    def _begin_sleep(self) -> None:
        self.base_sleep_calls += 1

    def _toggle_sleep(self, *args, **kwargs) -> None:
        self.base_toggle_sleep_calls += 1

    def shutdown_presence(self) -> None:
        self.base_shutdown_calls += 1


class _Harness(FocusSessionMixin, _Base):
    pass


def _harness() -> _Harness:
    harness = object.__new__(_Harness)
    harness._focus_window = None
    harness._focus_session = None
    harness._focus_plan = FocusPlan()
    harness._focus_source_id = None
    harness._focus_last_tick = None
    harness._focus_ambience = Mock()
    harness._focus_ambience.active_name = None
    harness._focus_completion_heart_pending = False
    harness._focus_setup_visible = False
    harness._focus_context_menu_visible = False
    harness._focus_setup_pending = False
    harness._context_menu_open = False
    harness._context_menu = Mock()
    harness._context_menu.get_visible.return_value = False
    harness._window = Mock()
    harness._logger = Mock()
    harness._bond_unsaved_xp = 0
    harness._dismiss_presence_bubble = Mock()
    harness._ensure_focus_visual = Mock(return_value=True)
    harness._ensure_focus_thinking_visual = Mock(return_value=True)
    harness._stop_focus_visual = Mock()
    harness._stop_focus_thinking_visual = Mock()
    harness._stop_focus_timer = Mock()
    harness._persist_focus_xp_if_needed = Mock()
    harness._show_focus_line = Mock()
    harness._award_bond = Mock()
    harness._wake_up = Mock()
    harness._stop_fedora_mode = Mock()
    harness._start_heart_emote = Mock()
    harness._schedule_computer_idle_emote = Mock()
    harness._fedora_mode_active = False
    harness.state = StateMachine()
    harness.player = SimpleNamespace(animation=object())
    harness.base_typing_calls = 0
    harness.base_resume_calls = 0
    harness.base_sleep_calls = 0
    harness.base_toggle_sleep_calls = 0
    harness.base_shutdown_calls = 0
    harness.base_show_context_calls = 0
    harness.base_close_context_calls = 0
    return harness


def test_focus_window_positions_beside_full_mochi_bounds() -> None:
    focus_window = object.__new__(FocusWindow)
    focus_window._position_serial = 7
    focus_window._logger = Mock()
    focus_window.window = Mock()
    focus_window.window.get_visible.return_value = True
    focus_window.window.get_width.return_value = 420
    focus_window.window.get_height.return_value = 455

    monitors = SimpleNamespace(
        get_n_items=lambda: 1,
        get_item=lambda _index: SimpleNamespace(
            get_geometry=lambda: SimpleNamespace(
                x=0,
                y=0,
                width=1920,
                height=1080,
            )
        ),
    )
    focus_window._owner = SimpleNamespace(
        get_width=lambda: 128,
        get_height=lambda: 128,
        get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
    )

    with patch(
        "mochi.presence.focus_session.get_window_position",
        return_value=(800, 400),
    ), patch(
        "mochi.presence.focus_session._window_coordinate_scale",
        return_value=1.0,
    ), patch(
        "mochi.presence.focus_session.menu_position_for_anchor",
        return_value=(940, 350),
    ) as position, patch(
        "mochi.presence.focus_session.move_window",
        return_value=True,
    ) as move:
        result = focus_window._position_if_current(7)

    assert result == 0
    position.assert_called_once()
    assert position.call_args.kwargs["anchor_width"] == 128
    move.assert_called_once_with(focus_window.window, 940, 350)


def test_focus_window_hide_notifies_the_thinking_lifecycle() -> None:
    focus_window = object.__new__(FocusWindow)
    focus_window._position_serial = 0
    focus_window.window = Mock()
    focus_window._on_hidden = Mock()

    focus_window._hide()

    focus_window.window.hide.assert_called_once_with()
    focus_window._on_hidden.assert_called_once_with()


def test_start_creates_one_timer_and_second_start_is_ignored() -> None:
    harness = _harness()
    plan = FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)

    with patch("mochi.presence.focus_session.GLib.timeout_add", return_value=41) as add:
        harness._start_focus_session(plan)
        harness._start_focus_session(plan)

    add.assert_called_once()
    assert harness._focus_source_id == 41
    assert harness._focus_session is not None
    assert harness._focus_setup_visible is False
    harness._stop_focus_thinking_visual.assert_called_once_with()
    harness._focus_ambience.start_selected.assert_called_once_with()


def test_stopped_session_can_start_again_with_one_fresh_timer() -> None:
    harness = _harness()
    harness._stop_focus_timer = FocusSessionMixin._stop_focus_timer.__get__(harness)
    plan = FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)

    with patch(
        "mochi.presence.focus_session.GLib.timeout_add",
        side_effect=(41, 42),
    ) as add, patch(
        "mochi.presence.focus_session.GLib.source_remove",
    ) as remove, patch(
        "mochi.presence.focus_session.time.monotonic",
        side_effect=(10.0, 11.0, 12.0),
    ):
        harness._start_focus_session(plan)
        first_session = harness._focus_session
        harness._cancel_focus_session()
        harness._start_focus_session(plan)

    assert add.call_count == 2
    remove.assert_called_once_with(41)
    assert harness._focus_source_id == 42
    assert harness._focus_session is not None
    assert harness._focus_session is not first_session


def test_start_exits_persistent_fedora_mode_before_writing() -> None:
    harness = _harness()
    harness._fedora_mode_active = True
    harness.state.current = MochiState.FEDORA

    with patch("mochi.presence.focus_session.GLib.timeout_add", return_value=41):
        harness._start_focus_session(FocusPlan())

    harness._stop_fedora_mode.assert_called_once_with()
    harness._ensure_focus_visual.assert_called_once_with()


def test_pause_and_resume_exclude_paused_wall_time_and_xp() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session
    harness._focus_last_tick = 100.0
    harness._focus_ambience.active_name = "mochi_rain"

    with patch("mochi.presence.focus_session.time.monotonic", return_value=160.0):
        harness._focus_tick()
        harness._toggle_focus_pause()
    with patch("mochi.presence.focus_session.time.monotonic", return_value=900.0):
        harness._focus_tick()
        harness._toggle_focus_pause()
    with patch("mochi.presence.focus_session.time.monotonic", return_value=960.0):
        harness._focus_tick()

    assert harness._award_bond.call_args_list[0].args == (1,)
    assert harness._award_bond.call_args_list[1].args == (1,)
    assert session.focus_minutes_completed == 2
    harness._focus_ambience.pause.assert_called_once_with()
    harness._focus_ambience.resume.assert_called_once_with()


def test_pause_settles_elapsed_time_since_the_last_timer_tick() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session
    harness._focus_last_tick = 10.0

    with patch("mochi.presence.focus_session.time.monotonic", return_value=70.0):
        harness._toggle_focus_pause()

    harness._award_bond.assert_called_once_with(1, persist=False)
    assert session.focus_minutes_completed == 1
    assert session.paused is True


def test_stop_keeps_earned_xp_without_completion_bonus() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    session.advance(60)
    harness._focus_session = session
    harness._focus_window = Mock()

    harness._cancel_focus_session()

    harness._stop_focus_timer.assert_called_once_with()
    harness._persist_focus_xp_if_needed.assert_called_once_with()
    harness._focus_ambience.stop.assert_called_once_with()
    assert harness._focus_session is None
    assert harness._focus_setup_visible is True
    harness._ensure_focus_thinking_visual.assert_called_once_with()
    harness._focus_window.present_setup.assert_called_once_with(session.plan)
    harness._show_focus_line.assert_called_once()


def test_stop_settles_elapsed_time_since_the_last_timer_tick() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session
    harness._focus_last_tick = 10.0

    with patch("mochi.presence.focus_session.time.monotonic", return_value=70.0):
        harness._cancel_focus_session()

    harness._award_bond.assert_called_once_with(1, persist=False)
    assert session.focus_minutes_completed == 1


def test_hidden_window_reopens_the_same_live_session() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan())
    harness._focus_session = session
    harness._focus_window = Mock()

    harness._show_focus_window()

    harness._focus_window.present_session.assert_called_once_with(session)
    assert harness._focus_session is session


def test_opening_setup_starts_the_thinking_visual() -> None:
    harness = _harness()
    harness._focus_window = Mock()

    harness._show_focus_window()

    assert harness._focus_setup_visible is True
    harness._ensure_focus_thinking_visual.assert_called_once_with()
    harness._focus_window.present_setup.assert_called_once_with(harness._focus_plan)


def test_hiding_setup_stops_the_thinking_visual() -> None:
    harness = _harness()
    harness._focus_setup_visible = True

    harness._on_focus_window_hidden()

    assert harness._focus_setup_visible is False
    harness._stop_focus_thinking_visual.assert_called_once_with()


def test_right_click_menu_owns_thinking_visual_while_open() -> None:
    harness = _harness()

    harness._show_context_menu("gesture", 1, 12.0, 18.0)

    assert harness.base_show_context_calls == 1
    assert harness._context_menu_open is True
    assert harness._focus_context_menu_visible is True
    assert harness._focus_should_think() is True
    harness._ensure_focus_thinking_visual.assert_called_once_with()

    harness._on_context_menu_closed(None)

    assert harness.base_close_context_calls == 1
    assert harness._context_menu_open is False
    assert harness._focus_context_menu_visible is False
    assert harness._focus_should_think() is False
    harness._stop_focus_thinking_visual.assert_called_once_with()


def test_right_click_menu_does_not_wake_a_sleeping_mochi() -> None:
    harness = _harness()
    harness._focus_context_menu_visible = True
    harness._context_menu_open = True
    harness.state.current = MochiState.SLEEPING

    assert FocusSessionMixin._ensure_focus_thinking_visual(harness) is False

    harness._wake_up.assert_not_called()


def test_right_click_menu_temporarily_replaces_active_focus_writing() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())

    assert harness._focus_should_work() is True

    harness._show_context_menu("gesture", 1, 12.0, 18.0)

    assert harness._focus_should_think() is True
    assert harness._focus_should_work() is False

    harness._on_context_menu_closed(None)

    assert harness._focus_should_think() is False
    assert harness._focus_should_work() is True
    harness._stop_focus_thinking_visual.assert_called_once_with()


def test_focus_action_handoff_keeps_thinking_owned_between_surfaces() -> None:
    harness = _harness()
    harness._focus_context_menu_visible = True
    harness._context_menu_open = True
    harness._focus_setup_pending = True

    harness._on_context_menu_closed(None)

    assert harness._focus_context_menu_visible is False
    assert harness._focus_setup_pending is True
    assert harness._focus_should_think() is True
    harness._stop_focus_thinking_visual.assert_not_called()

    harness._focus_window = Mock()
    harness._show_focus_window()

    assert harness._focus_setup_pending is False
    assert harness._focus_setup_visible is True
    assert harness._focus_should_think() is True
    harness._focus_window.present_setup.assert_called_once_with(harness._focus_plan)


def test_thinking_visual_plays_start_loop_and_end_sequence() -> None:
    harness = _harness()
    harness._focus_setup_visible = True
    harness._current_animation = "idle"
    harness._active_animation = ANIMATIONS["idle"]
    harness._pending_animation = None
    harness.player.animation = ANIMATIONS["idle"]
    harness._cancel_active_emote = Mock()
    harness._cancel_walk = Mock()
    harness._play_animation = Mock()

    def play(name: str, after=None) -> None:
        harness._current_animation = name
        harness._active_animation = ANIMATIONS[name]
        harness._pending_animation = after
        harness.player.animation = ANIMATIONS[name]

    harness._play_animation.side_effect = play
    harness._transition_to = Mock(
        side_effect=lambda next_state: (
            harness.state.transition_to(next_state) or True
        )
    )

    assert FocusSessionMixin._ensure_focus_thinking_visual(harness) is True
    harness._play_animation.assert_called_with("focus_thinking_start", after=None)
    assert harness.state.current is MochiState.IDLE_EMOTE

    start = harness._active_animation
    FocusSessionMixin._finish_reaction(harness, start)
    harness._play_animation.assert_called_with("focus_thinking_loop", after=None)

    harness._focus_setup_visible = False
    FocusSessionMixin._stop_focus_thinking_visual(harness)
    harness._play_animation.assert_called_with("focus_thinking_end", after=None)

    end = harness._active_animation
    FocusSessionMixin._finish_reaction(harness, end)
    harness._play_animation.assert_called_with("idle")
    assert harness.state.current is MochiState.IDLE


def test_starting_focus_exits_thinking_before_requesting_writing() -> None:
    harness = _harness()
    harness._focus_setup_visible = True
    harness.state.current = MochiState.IDLE_EMOTE
    harness._current_animation = "focus_thinking_loop"
    harness._active_animation = ANIMATIONS["focus_thinking_loop"]
    harness.player.animation = ANIMATIONS["focus_thinking_loop"]

    with patch("mochi.presence.focus_session.GLib.timeout_add", return_value=41):
        harness._start_focus_session(FocusPlan())

    assert harness._focus_setup_visible is False
    harness._stop_focus_thinking_visual.assert_called_once_with()
    harness._ensure_focus_visual.assert_called_once_with()


def test_focus_xp_uses_existing_bond_award_path_for_level_up_feedback() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan(focus_minutes=5, rounds=1))
    harness._focus_last_tick = 10.0

    with patch("mochi.presence.focus_session.time.monotonic", return_value=70.0):
        harness._focus_tick()

    harness._award_bond.assert_called_once_with(1, persist=False)


def test_focus_visual_resumes_after_temporary_interactions() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())

    assert harness._maybe_resume_ambient_activity() is True
    assert harness._start_typing_emote() is True
    assert harness._ensure_focus_visual.call_count == 2
    assert harness.base_resume_calls == 0
    assert harness.base_typing_calls == 0


def test_focus_tick_does_not_retake_visual_during_a_primary_press() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())
    harness._press = (20.0, 30.0)
    harness.state.current = MochiState.IDLE
    harness.player.animation = ANIMATIONS["idle"]
    harness._transition_to = Mock()
    harness._play_animation = Mock()

    assert FocusSessionMixin._ensure_focus_visual(harness) is False

    harness._transition_to.assert_not_called()
    harness._play_animation.assert_not_called()


def test_focus_visual_plays_writing_start_loop_and_stop_sequence() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())
    harness._current_animation = "idle"
    harness._active_animation = ANIMATIONS["idle"]
    harness._pending_animation = None
    harness.player.animation = ANIMATIONS["idle"]
    harness._cancel_active_emote = Mock()
    harness._cancel_walk = Mock()
    harness._play_animation = Mock()

    def play(name: str, after=None) -> None:
        harness._current_animation = name
        harness._active_animation = ANIMATIONS[name]
        harness._pending_animation = after
        harness.player.animation = ANIMATIONS[name]

    harness._play_animation.side_effect = play
    harness._transition_to = Mock(
        side_effect=lambda next_state: (
            harness.state.transition_to(next_state) or True
        )
    )

    assert FocusSessionMixin._ensure_focus_visual(harness) is True
    harness._play_animation.assert_called_with("focus_start", after=None)
    assert harness.state.current is MochiState.COMPUTER

    start = harness._active_animation
    FocusSessionMixin._finish_reaction(harness, start)
    harness._play_animation.assert_called_with("focus_loop", after=None)

    harness._focus_session.set_paused(True)
    FocusSessionMixin._stop_focus_visual(harness)
    harness._play_animation.assert_called_with("focus_stop", after=None)

    stop = harness._active_animation
    FocusSessionMixin._finish_reaction(harness, stop)
    harness._play_animation.assert_called_with("idle")
    assert harness.state.current is MochiState.IDLE


def test_stopping_during_focus_start_finishes_start_before_stop_transition() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())
    harness._focus_session.set_paused(True)
    harness.state.current = MochiState.COMPUTER
    harness._current_animation = "focus_start"
    harness._active_animation = ANIMATIONS["focus_start"]
    harness._pending_animation = None
    harness._play_animation = Mock()

    FocusSessionMixin._stop_focus_visual(harness)

    harness._play_animation.assert_not_called()

    FocusSessionMixin._finish_reaction(harness, harness._active_animation)

    harness._play_animation.assert_called_once_with("focus_stop", after=None)


def test_focus_resume_after_stop_requests_writing_sequence_restart() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())
    harness.state.current = MochiState.COMPUTER
    harness._current_animation = "focus_stop"
    harness._active_animation = ANIMATIONS["focus_stop"]
    harness._pending_animation = None
    harness._play_animation = Mock()
    harness._transition_to = Mock(
        side_effect=lambda next_state: (
            harness.state.transition_to(next_state) or True
        )
    )

    FocusSessionMixin._finish_reaction(harness, harness._active_animation)

    assert harness.state.current is MochiState.IDLE
    harness._play_animation.assert_called_once_with("idle")
    harness._ensure_focus_visual.assert_called_once_with()


def test_focus_stop_returns_breaks_to_normal_ambient_behavior() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan())
    session.phase = FocusPhase.BREAK
    harness._focus_session = session
    harness.state.current = MochiState.COMPUTER
    harness._current_animation = "focus_stop"
    harness._active_animation = ANIMATIONS["focus_stop"]
    harness._pending_animation = None
    harness._play_animation = Mock()
    harness._transition_to = Mock(
        side_effect=lambda next_state: (
            harness.state.transition_to(next_state) or True
        )
    )

    FocusSessionMixin._finish_reaction(harness, harness._active_animation)

    assert harness.base_resume_calls == 1
    harness._schedule_computer_idle_emote.assert_called_once_with()


def test_focus_suppresses_only_low_priority_unsolicited_presence_actions() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())

    assert harness._focus_allows_presence_action(SimpleNamespace(priority=10)) is False
    assert harness._focus_allows_presence_action(SimpleNamespace(priority=30)) is False
    assert harness._focus_allows_presence_action(SimpleNamespace(priority=40)) is True

    harness._focus_session.set_paused(True)
    assert harness._focus_allows_presence_action(SimpleNamespace(priority=10)) is True

    harness._focus_session.set_paused(False)
    harness._focus_session.phase = FocusPhase.BREAK
    assert harness._focus_allows_presence_action(SimpleNamespace(priority=10)) is True


def test_automatic_sleep_is_deferred_but_manual_sleep_pauses_focus() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())

    harness._begin_sleep()
    harness._toggle_sleep()

    assert harness.base_sleep_calls == 0
    assert harness._focus_session.paused is True
    harness._stop_focus_visual.assert_called_once_with()
    harness._focus_ambience.pause.assert_called_once_with()
    assert harness.base_toggle_sleep_calls == 1


def test_manual_sleep_settles_elapsed_focus_time_before_pausing() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session
    harness._focus_last_tick = 10.0

    with patch("mochi.presence.focus_session.time.monotonic", return_value=70.0):
        harness._toggle_sleep()

    harness._award_bond.assert_called_once_with(1, persist=False)
    assert session.focus_minutes_completed == 1
    assert session.paused is True
    assert harness.base_toggle_sleep_calls == 1


def test_wake_during_break_does_not_pause_the_running_break() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan())
    session.phase = FocusPhase.BREAK
    harness._focus_session = session
    harness.state.current = MochiState.SLEEPING

    harness._toggle_sleep()

    assert session.paused is False
    harness._stop_focus_visual.assert_not_called()
    harness._focus_ambience.pause.assert_not_called()
    assert harness.base_toggle_sleep_calls == 1


def test_resume_during_break_resumes_ambience_without_work_visual() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan())
    session.phase = FocusPhase.BREAK
    session.set_paused(True)
    harness._focus_session = session
    harness._focus_ambience.active_name = "mochi_rain"

    harness._toggle_focus_pause()

    assert session.paused is False
    harness._ensure_focus_visual.assert_not_called()
    harness._focus_ambience.resume.assert_called_once_with()


def test_focus_wakes_mochi_when_the_next_focus_round_begins() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=2))
    session.phase = FocusPhase.BREAK
    session.remaining_seconds = 1.0
    harness._focus_session = session
    harness._focus_last_tick = 10.0
    harness.state.current = MochiState.SLEEPING
    harness._ensure_focus_visual = Mock(side_effect=lambda: harness._wake_up())

    with patch("mochi.presence.focus_session.time.monotonic", return_value=11.0):
        harness._focus_tick()

    assert session.phase is FocusPhase.FOCUS
    harness._wake_up.assert_called_once_with()


def test_shutdown_removes_timer_and_flushes_pending_bond_xp() -> None:
    harness = _harness()
    harness._focus_source_id = 77
    harness._bond_unsaved_xp = 2
    harness._focus_window = Mock()
    window = harness._focus_window

    harness.shutdown_presence()

    harness._stop_focus_timer.assert_called_once_with()
    harness._persist_focus_xp_if_needed.assert_called_once_with()
    harness._focus_ambience.stop.assert_called_once_with()
    window.destroy.assert_called_once_with()
    assert harness._focus_window is None
    assert harness.base_shutdown_calls == 1


def test_shutdown_settles_elapsed_time_before_persisting() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session
    harness._focus_last_tick = 10.0

    with patch("mochi.presence.focus_session.time.monotonic", return_value=70.0):
        harness.shutdown_presence()

    harness._award_bond.assert_called_once_with(1, persist=False)
    assert session.focus_minutes_completed == 1
    harness._persist_focus_xp_if_needed.assert_called_once_with()
