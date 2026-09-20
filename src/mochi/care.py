"""Non-punitive care and relationship progression primitives for Mochi."""

from __future__ import annotations

from dataclasses import dataclass
import math


BOND_BASE_XP = 480
BOND_LEVEL_GROWTH_XP = 90
BOND_TYPING_XP_PER_SECOND = 1
BOND_FEED_FIRST_XP = 30
BOND_FEED_SECOND_XP = 10
BOND_FEED_REWARD_WINDOW_SECONDS = 10 * 60
DEFAULT_BOND_LEVEL = 1
DEFAULT_BOND_XP = 0


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def bond_feed_reward_xp(completed_feeds_in_window: int) -> int:
    """Return bond XP for the next feed in the current reward window.

    Feeding stays available for character interaction, but only the first two
    completed feeds after ten minutes of feed inactivity award bond XP.
    """

    completed = max(0, _coerce_int(completed_feeds_in_window, 0))
    if completed == 0:
        return BOND_FEED_FIRST_XP
    if completed == 1:
        return BOND_FEED_SECOND_XP
    return 0


def bond_xp_required(level: int) -> int:
    """XP required to move from the given level to the next bond level.

    The square-root curve keeps early progress readable without turning later
    levels into an exponential grind:

        required(level) = 480 + round(90 * sqrt(level - 1))

    At the typing rate of one XP per second this is roughly 8 minutes for
    level 1, 11 minutes for level 5, and 12.5 minutes for level 10.
    """
    normalized = max(DEFAULT_BOND_LEVEL, _coerce_int(level, DEFAULT_BOND_LEVEL))
    return BOND_BASE_XP + round(
        BOND_LEVEL_GROWTH_XP * math.sqrt(normalized - DEFAULT_BOND_LEVEL)
    )


@dataclass(frozen=True)
class BondState:
    """Persistent relationship progress, separate from animation/behavior state.

    Bond never decays. xp is progress inside the current level. Construction
    normalizes overflow so callers can award any positive amount without having
    to know where level boundaries fall.
    """

    level: int = DEFAULT_BOND_LEVEL
    xp: int = DEFAULT_BOND_XP

    def __post_init__(self) -> None:
        level = max(DEFAULT_BOND_LEVEL, _coerce_int(self.level, DEFAULT_BOND_LEVEL))
        xp = max(0, _coerce_int(self.xp, DEFAULT_BOND_XP))

        while xp >= bond_xp_required(level):
            xp -= bond_xp_required(level)
            level += 1

        object.__setattr__(self, "level", level)
        object.__setattr__(self, "xp", xp)

    @property
    def xp_required(self) -> int:
        return bond_xp_required(self.level)

    @property
    def progress_fraction(self) -> float:
        return min(1.0, max(0.0, self.xp / self.xp_required))

    @property
    def progress_percent(self) -> int:
        return round(self.progress_fraction * 100)

    def award(self, amount: int = 1) -> "BondAdvance":
        """Return the next immutable bond state after a positive shared action."""
        awarded = max(0, _coerce_int(amount, 0))
        next_state = BondState(level=self.level, xp=self.xp + awarded)
        return BondAdvance(
            state=next_state,
            xp_awarded=awarded,
            levels_gained=next_state.level - self.level,
        )


@dataclass(frozen=True)
class BondAdvance:
    """Result metadata useful to presentation layers without owning UI."""

    state: BondState
    xp_awarded: int
    levels_gained: int

    @property
    def levelled_up(self) -> bool:
        return self.levels_gained > 0
