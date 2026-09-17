"""Unit coverage for Mochi's non-punitive bond progression model."""

from mochi.care import BOND_POINTS_PER_LEVEL, BondState


def test_bond_starts_at_level_one_with_no_progress() -> None:
    state = BondState()

    assert state.level == 1
    assert state.points == 0
    assert state.points_per_level == BOND_POINTS_PER_LEVEL == 4


def test_award_advances_progress_without_decay() -> None:
    state = BondState()
    advance = state.award(2)

    assert state == BondState()
    assert advance.state == BondState(level=1, points=2)
    assert advance.points_awarded == 2
    assert advance.levels_gained == 0
    assert advance.levelled_up is False


def test_four_points_roll_into_the_next_level() -> None:
    advance = BondState(level=1, points=3).award(1)

    assert advance.state == BondState(level=2, points=0)
    assert advance.levels_gained == 1
    assert advance.levelled_up is True


def test_large_award_can_cross_multiple_levels() -> None:
    advance = BondState(level=2, points=1).award(10)

    assert advance.state == BondState(level=4, points=3)
    assert advance.levels_gained == 2


def test_invalid_or_negative_values_never_reduce_progress() -> None:
    assert BondState(level=-4, points=-9) == BondState()
    assert BondState(level="bad", points="bad") == BondState()

    state = BondState(level=3, points=2)
    assert state.award(-5).state == state
    assert state.award("bad").state == state
