"""Mood vocabulary and persistent affect state for Mochi.

MochiState answers what Mochi is doing right now (idle, walking, sleeping,
typing, and so on). MochiMood answers how Mochi feels while doing it.

By default the model still derives lightweight mood labels from accepted
behavior transitions for v0.3 compatibility. A persistent override can sit
above those observations so systems such as care/needs can later make Mochi
sad, happy, or otherwise affected without creating state-machine combinations
like SAD_WALKING or SAD_IDLE.
"""

from __future__ import annotations

from enum import Enum

from mochi.state import MochiState


class MochiMood(Enum):
    """Small mood vocabulary shared by behavior and presentation."""

    CONTENT = "content"
    COZY = "cozy"
    CURIOUS = "curious"
    SLEEPY = "sleepy"
    EXCITED = "excited"
    SAD = "sad"


_STATE_MOODS: dict[MochiState, MochiMood] = {
    MochiState.IDLE: MochiMood.CONTENT,
    MochiState.BOUNCING: MochiMood.EXCITED,
    MochiState.SQUISHING: MochiMood.EXCITED,
    MochiState.EXCITED: MochiMood.EXCITED,
    MochiState.WALKING: MochiMood.CURIOUS,
    MochiState.SLEEPING: MochiMood.SLEEPY,
    MochiState.WAKING: MochiMood.CURIOUS,
    MochiState.HEART: MochiMood.COZY,
    MochiState.COMPUTER: MochiMood.CURIOUS,
    MochiState.TYPING: MochiMood.CURIOUS,
    MochiState.WATCHING: MochiMood.CURIOUS,
    MochiState.DANCING: MochiMood.EXCITED,
    MochiState.SEARCHING: MochiMood.CURIOUS,
    MochiState.FEDORA: MochiMood.EXCITED,
}


def _coerce_mood(mood: MochiMood | str) -> MochiMood:
    if isinstance(mood, MochiMood):
        return mood
    return MochiMood(str(mood).strip().lower())


class MoodModel:
    """Track observed mood plus an optional persistent affect override."""

    def __init__(self, initial: MochiMood = MochiMood.CONTENT) -> None:
        self._observed = initial
        self._override: MochiMood | None = None

    @property
    def current(self) -> MochiMood:
        return self._override or self._observed

    @property
    def observed(self) -> MochiMood:
        return self._observed

    @property
    def override(self) -> MochiMood | None:
        return self._override

    @property
    def label(self) -> str:
        return self.current.value

    def set_override(self, mood: MochiMood | str) -> MochiMood:
        """Persist a mood until explicitly cleared."""
        self._override = _coerce_mood(mood)
        return self.current

    def clear_override(self) -> MochiMood:
        self._override = None
        return self.current

    def observe_state(self, state: MochiState) -> MochiMood | None:
        """Observe one accepted behavior transition."""
        mood = _STATE_MOODS.get(state)
        if mood is None:
            return None
        self._observed = mood
        return self.current
