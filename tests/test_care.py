"""Unit coverage for Mochi's non-punitive bond progression model."""

from mochi.care import (
    BOND_BASE_XP,
    BOND_FEED_XP,
    BOND_TYPING_XP_PER_SECOND,
    BondState,
    bond_xp_required,
)


def test_bond_curve_starts_gentle_and_grows_slowly() -> None:
    assert bond_xp_required(1) == BOND_BASE_XP == 480
    assert bond_xp_required(2) == 570
    assert bond_xp_required(5) == 660
    assert bond_xp_required(10) == 750


def test_bond_starts_at_level_one_with_empty_bar() -> None:
    state = BondState()

    assert state.level == 1
    assert state.xp == 0
    assert state.xp_required == 480
    assert state.progress_fraction == 0.0
    assert state.progress_percent == 0


def test_progress_fraction_tracks_xp_inside_current_level() -> None:
    state = BondState(level=1, xp=240)

    assert state.progress_fraction == 0.5
    assert state.progress_percent == 50


def test_award_crosses_level_boundary_and_keeps_overflow() -> None:
    advance = BondState(level=1, xp=470).award(25)

    assert advance.state == BondState(level=2, xp=15)
    assert advance.xp_awarded == 25
    assert advance.levels_gained == 1
    assert advance.levelled_up is True


def test_large_award_can_cross_multiple_levels() -> None:
    advance = BondState(level=1, xp=0).award(1060)

    assert advance.state == BondState(level=3, xp=10)
    assert advance.levels_gained == 2


def test_invalid_or_negative_values_never_reduce_progress() -> None:
    assert BondState(level=-4, xp=-9) == BondState()
    assert BondState(level="bad", xp="bad") == BondState()

    state = BondState(level=3, xp=20)
    assert state.award(-5).state == state
    assert state.award("bad").state == state


def test_activity_awards_are_small_continuous_vs_feed_boost() -> None:
    assert BOND_TYPING_XP_PER_SECOND == 1
    assert BOND_FEED_XP == 60
    assert BOND_FEED_XP > BOND_TYPING_XP_PER_SECOND
