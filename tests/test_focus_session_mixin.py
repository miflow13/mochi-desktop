"""Focus-session lifecycle integration seams without a live GTK desktop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.focus import FocusPhase, FocusPlan, FocusSession
from mochi.presence.focus_session import FocusSessionMixin
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, StateMachine


class _Base:
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
    harness._context_menu_open = False
    harness._window = Mock()
    harness._logger = Mock()
    harness._bond_unsaved_xp = 0
    harness._dismiss_presence_bubble = Mock()
    harness._ensure_focus_visual = Mock(return_value=True)
    harness._stop_focus_visual = Mock()
    harness._stop_focus_timer = Mock()
    harness._persist_focus_xp_if_needed = Mock()
    harness._show_focus_line = Mock()
    harness._award_bond = Mock()
    harness._wake_up = Mock()
    harness._start_computer_emote = Mock()
    harness._start_heart_emote = Mock()
    harness.state = StateMachine()
    harness.player = SimpleNamespace(animation=object())
    harness.base_typing_calls = 0
    harness.base_resume_calls = 0
    harness.base_sleep_calls = 0
    harness.base_toggle_sleep_calls = 0
    harness.base_shutdown_calls = 0
    return harness


def test_start_creates_one_timer_and_second_start_is_ignored() -> None:
    harness = _harness()
    plan = FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)

    with patch("mochi.presence.focus_session.GLib.timeout_add", return_value=41) as add:
        harness._start_focus_session(plan)
        harness._start_focus_session(plan)

    add.assert_called_once()
    assert harness._focus_source_id == 41
    assert harness._focus_session is not None
    harness._focus_ambience.start_selected.assert_called_once_with()


def test_pause_and_resume_exclude_paused_wall_time_and_xp() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session
    harness._focus_last_tick = 100.0

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


def test_stop_keeps_earned_xp_without_completion_bonus() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    session.advance(60)
    harness._focus_session = session

    harness._cancel_focus_session()

    harness._stop_focus_timer.assert_called_once_with()
    harness._persist_focus_xp_if_needed.assert_called_once_with()
    harness._focus_ambience.stop.assert_called_once_with()
    assert harness._focus_session is None
    harness._show_focus_line.assert_called_once()


def test_hidden_window_reopens_the_same_live_session() -> None:
    harness = _harness()
    session = FocusSession(FocusPlan())
    harness._focus_session = session
    harness._focus_window = Mock()

    harness._show_focus_window()

    harness._focus_window.present_session.assert_called_once_with(session)
    assert harness._focus_session is session


def test_opening_setup_attempts_the_existing_computer_getting_ready_beat() -> None:
    harness = _harness()
    harness._focus_window = Mock()

    harness._show_focus_window()

    harness._start_computer_emote.assert_called_once_with()
    harness._focus_window.present_setup.assert_called_once_with(harness._focus_plan)


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


def test_focus_visual_reuses_existing_computer_typing_loop_and_outro() -> None:
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
    harness._play_animation.assert_called_with("computer_typing", after=None)
    assert harness.state.current is MochiState.COMPUTER

    harness._focus_session.set_paused(True)
    FocusSessionMixin._stop_focus_visual(harness)
    harness._play_animation.assert_called_with("computer_outro", after="idle")


def test_focus_resume_can_replace_an_in_progress_computer_outro() -> None:
    harness = _harness()
    harness._focus_session = FocusSession(FocusPlan())
    harness.state.current = MochiState.COMPUTER
    harness._current_animation = "computer_outro"
    harness._active_animation = ANIMATIONS["computer_outro"]
    harness.player.animation = ANIMATIONS["computer_outro"]
    harness._play_animation = Mock()

    assert FocusSessionMixin._ensure_focus_visual(harness) is True

    harness._play_animation.assert_called_once_with("computer_typing", after=None)


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
