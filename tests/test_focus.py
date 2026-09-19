from mochi.focus import (
    FOCUS_COMPLETION_BONUS_XP,
    FOCUS_XP_PER_MINUTE,
    FocusPhase,
    FocusPlan,
    FocusSession,
)


def test_focus_plan_clamps_invalid_values() -> None:
    plan = FocusPlan(
        focus_minutes=0,
        break_minutes=999,
        rounds=-3,
        encouragement_enabled=0,
    )

    assert plan.focus_minutes == 5
    assert plan.break_minutes == 30
    assert plan.rounds == 1
    assert plan.encouragement_enabled is False


def test_focus_session_awards_one_xp_per_completed_focus_minute() -> None:
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))

    almost = session.advance(59.9)
    minute = session.advance(0.1)

    assert almost.xp_earned == 0
    assert minute.xp_earned == FOCUS_XP_PER_MINUTE
    assert session.focus_minutes_completed == 1
    assert session.phase is FocusPhase.FOCUS


def test_break_time_awards_no_focus_xp() -> None:
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=2))

    focus = session.advance(5 * 60)
    rest = session.advance(60)

    assert focus.xp_earned == 5 * FOCUS_XP_PER_MINUTE
    assert focus.transitions == (FocusPhase.BREAK,)
    assert session.phase is FocusPhase.FOCUS
    assert session.round_number == 2
    assert rest.xp_earned == 0
    assert rest.transitions == (FocusPhase.FOCUS,)


def test_completed_session_gets_one_non_punitive_completion_bonus() -> None:
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))

    result = session.advance(5 * 60)

    assert result.completed is True
    assert result.transitions == (FocusPhase.COMPLETE,)
    assert result.xp_earned == (
        5 * FOCUS_XP_PER_MINUTE + FOCUS_COMPLETION_BONUS_XP
    )
    assert session.phase is FocusPhase.COMPLETE
    assert session.remaining_label == "00:00"

    assert session.advance(60).xp_earned == 0


def test_pause_freezes_timer_and_rewards() -> None:
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    session.set_paused(True)

    result = session.advance(5 * 60)

    assert result.xp_earned == 0
    assert session.remaining_seconds == 5 * 60
    assert session.phase is FocusPhase.FOCUS

    session.set_paused(False)
    session.advance(60)
    assert session.focus_minutes_completed == 1


def test_encouragement_is_sparse_and_threshold_based() -> None:
    session = FocusSession(
        FocusPlan(
            focus_minutes=10,
            break_minutes=1,
            rounds=1,
            encouragement_enabled=True,
        )
    )

    first = session.advance(210)
    second = session.advance(222)
    remainder = session.advance(100)

    assert first.encouragements_due == 1
    assert second.encouragements_due == 1
    assert remainder.encouragements_due == 0


def test_encouragement_can_be_disabled() -> None:
    session = FocusSession(
        FocusPlan(
            focus_minutes=10,
            break_minutes=1,
            rounds=1,
            encouragement_enabled=False,
        )
    )

    result = session.advance(9 * 60)

    assert result.encouragements_due == 0


def test_large_elapsed_step_crosses_breaks_without_losing_phase_order() -> None:
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=2))

    result = session.advance((5 + 1 + 5) * 60)

    assert result.transitions == (
        FocusPhase.BREAK,
        FocusPhase.FOCUS,
        FocusPhase.COMPLETE,
    )
    assert result.completed is True
    assert result.xp_earned == (
        10 * FOCUS_XP_PER_MINUTE + FOCUS_COMPLETION_BONUS_XP
    )
    assert session.focus_minutes_completed == 10
    assert session.phase is FocusPhase.COMPLETE
