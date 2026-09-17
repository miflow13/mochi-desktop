"""Non-punitive care and relationship progression primitives for Mochi."""

from __future__ import annotations

from dataclasses import dataclass


BOND_POINTS_PER_LEVEL = 4
DEFAULT_BOND_LEVEL = 1
DEFAULT_BOND_POINTS = 0


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BondState:
    """Persistent relationship progress, deliberately separate from animation state.

    Bond never decays. Points roll forward into levels in four-step cycles, so
    being away from Mochi cannot undo progress the user has already made.
    """

    level: int = DEFAULT_BOND_LEVEL
    points: int = DEFAULT_BOND_POINTS

    def __post_init__(self) -> None:
        level = max(DEFAULT_BOND_LEVEL, _coerce_int(self.level, DEFAULT_BOND_LEVEL))
        points = max(0, _coerce_int(self.points, DEFAULT_BOND_POINTS))
        levels_gained, points = divmod(points, BOND_POINTS_PER_LEVEL)
        object.__setattr__(self, "level", level + levels_gained)
        object.__setattr__(self, "points", points)

    @property
    def points_per_level(self) -> int:
        return BOND_POINTS_PER_LEVEL

    def award(self, amount: int = 1) -> "BondAdvance":
        """Return the next immutable bond state after a positive care action."""
        awarded = max(0, _coerce_int(amount, 0))
        next_state = BondState(level=self.level, points=self.points + awarded)
        return BondAdvance(
            state=next_state,
            points_awarded=awarded,
            levels_gained=next_state.level - self.level,
        )


@dataclass(frozen=True)
class BondAdvance:
    """Result metadata useful to UI/reaction layers without owning presentation."""

    state: BondState
    points_awarded: int
    levels_gained: int

    @property
    def levelled_up(self) -> bool:
        return self.levels_gained > 0
