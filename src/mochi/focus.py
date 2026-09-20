"""Pure focus-session timing and reward model for Work with Mochi."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


MIN_FOCUS_MINUTES = 5
MAX_FOCUS_MINUTES = 120
MIN_BREAK_MINUTES = 1
MAX_BREAK_MINUTES = 30
MIN_ROUNDS = 1
MAX_ROUNDS = 8

FOCUS_XP_PER_MINUTE = 1
FOCUS_COMPLETION_BONUS_XP = 10
FOCUS_ENCOURAGEMENT_MARKS = (0.35, 0.72)


def _clamp_int(value: object, minimum: int, maximum: int, default: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return max(minimum, min(normalized, maximum))


class FocusPhase(Enum):
    FOCUS = "focus"
    BREAK = "break"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class FocusPlan:
    focus_minutes: int = 25
    break_minutes: int = 5
    rounds: int = 4
    encouragement_enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "focus_minutes",
            _clamp_int(
                self.focus_minutes,
                MIN_FOCUS_MINUTES,
                MAX_FOCUS_MINUTES,
                25,
            ),
        )
        object.__setattr__(
            self,
            "break_minutes",
            _clamp_int(
                self.break_minutes,
                MIN_BREAK_MINUTES,
                MAX_BREAK_MINUTES,
                5,
            ),
        )
        object.__setattr__(
            self,
            "rounds",
            _clamp_int(self.rounds, MIN_ROUNDS, MAX_ROUNDS, 4),
        )
        object.__setattr__(
            self,
            "encouragement_enabled",
            bool(self.encouragement_enabled),
        )

    @property
    def focus_seconds(self) -> int:
        return self.focus_minutes * 60

    @property
    def break_seconds(self) -> int:
        return self.break_minutes * 60


@dataclass(frozen=True, slots=True)
class FocusAdvance:
    xp_earned: int = 0
    encouragements_due: int = 0
    transitions: tuple[FocusPhase, ...] = ()
    completed: bool = False


class FocusSession:
    """Mutable runtime clock with deterministic phase and reward transitions."""

    def __init__(self, plan: FocusPlan | None = None) -> None:
        self.plan = plan or FocusPlan()
        self.phase = FocusPhase.FOCUS
        self.round_number = 1
        self.remaining_seconds = float(self.plan.focus_seconds)
        self.paused = False
        self.focus_minutes_completed = 0
        self._focus_xp_seconds = 0.0
        self._encouragement_marks_seen: set[int] = set()

    @property
    def active(self) -> bool:
        return self.phase is not FocusPhase.COMPLETE

    @property
    def current_phase_seconds(self) -> int:
        if self.phase is FocusPhase.FOCUS:
            return self.plan.focus_seconds
        if self.phase is FocusPhase.BREAK:
            return self.plan.break_seconds
        return 0

    @property
    def progress_fraction(self) -> float:
        duration = self.current_phase_seconds
        if duration <= 0:
            return 1.0
        return min(
            1.0,
            max(0.0, 1.0 - self.remaining_seconds / float(duration)),
        )

    @property
    def remaining_label(self) -> str:
        remaining = max(0, math.ceil(self.remaining_seconds))
        minutes, seconds = divmod(remaining, 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def phase_label(self) -> str:
        if self.phase is FocusPhase.FOCUS:
            return f"Focus {self.round_number} of {self.plan.rounds}"
        if self.phase is FocusPhase.BREAK:
            return f"Break {self.round_number} of {self.plan.rounds}"
        return "Complete"

    def set_paused(self, paused: bool) -> None:
        if self.active:
            self.paused = bool(paused)

    def toggle_paused(self) -> bool:
        self.set_paused(not self.paused)
        return self.paused

    def advance(self, elapsed_seconds: float) -> FocusAdvance:
        """Advance by real elapsed time and report presentation/reward events."""
        if self.paused or not self.active:
            return FocusAdvance()

        try:
            remaining_input = float(elapsed_seconds)
        except (TypeError, ValueError):
            return FocusAdvance()
        if not math.isfinite(remaining_input) or remaining_input <= 0:
            return FocusAdvance()

        xp_earned = 0
        encouragements_due = 0
        transitions: list[FocusPhase] = []

        while remaining_input > 1e-9 and self.active:
            duration = self.current_phase_seconds
            before_remaining = self.remaining_seconds
            step = min(remaining_input, before_remaining)

            if self.phase is FocusPhase.FOCUS:
                before_elapsed = duration - before_remaining
                after_elapsed = before_elapsed + step
                self._focus_xp_seconds += step

                whole_minutes = int(self._focus_xp_seconds // 60)
                if whole_minutes:
                    xp_earned += whole_minutes * FOCUS_XP_PER_MINUTE
                    self.focus_minutes_completed += whole_minutes
                    self._focus_xp_seconds -= whole_minutes * 60

                if self.plan.encouragement_enabled:
                    for index, mark in enumerate(FOCUS_ENCOURAGEMENT_MARKS):
                        threshold = duration * mark
                        if (
                            index not in self._encouragement_marks_seen
                            and before_elapsed < threshold <= after_elapsed
                        ):
                            self._encouragement_marks_seen.add(index)
                            encouragements_due += 1

            self.remaining_seconds = max(0.0, before_remaining - step)
            remaining_input -= step

            if self.remaining_seconds > 1e-9:
                continue

            if self.phase is FocusPhase.FOCUS:
                self._focus_xp_seconds = 0.0
                if self.round_number >= self.plan.rounds:
                    self.phase = FocusPhase.COMPLETE
                    self.remaining_seconds = 0.0
                    xp_earned += FOCUS_COMPLETION_BONUS_XP
                    transitions.append(FocusPhase.COMPLETE)
                    break
                self.phase = FocusPhase.BREAK
                self.remaining_seconds = float(self.plan.break_seconds)
                transitions.append(FocusPhase.BREAK)
                continue

            if self.phase is FocusPhase.BREAK:
                self.round_number += 1
                self.phase = FocusPhase.FOCUS
                self.remaining_seconds = float(self.plan.focus_seconds)
                self._encouragement_marks_seen.clear()
                transitions.append(FocusPhase.FOCUS)

        return FocusAdvance(
            xp_earned=xp_earned,
            encouragements_due=encouragements_due,
            transitions=tuple(transitions),
            completed=self.phase is FocusPhase.COMPLETE,
        )
