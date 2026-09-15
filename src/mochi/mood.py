"""Small event-driven mood model derived from Mochi's behavior state.

Mood is intentionally not a second behavior engine. It observes successful
MochiState transitions and exposes a compact emotional interpretation for the
reusable UI surface above Mochi.

Transient mechanical states (blink/pickup/drag/drop) do not change mood; they
preserve the last meaningful mood until Mochi enters another mapped state.
"""

from __future__ import annotations

from enum import Enum

from mochi.state import MochiState


class MochiMood(Enum):
    """Stable v0.3 mood vocabulary shown by the nameplate."""

    CONTENT = "content"
    COZY = "cozy"
    CURIOUS = "curious"
    SLEEPY = "sleepy"
    EXCITED = "excited"


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


class MoodModel:
    """Derive Mochi's current mood from meaningful behavior transitions."""

    def __init__(self, initial: MochiMood = MochiMood.CONTENT) -> None:
        self.current = initial

    @property
    def label(self) -> str:
        return self.current.value

    def observe_state(self, state: MochiState) -> MochiMood | None:
        """Observe one successful behavior-state transition.

        Returns the mapped mood when the state is emotionally meaningful.
        States absent from `_STATE_MOODS` are intentionally mood-neutral and
        return ``None`` while preserving the previous mood. This keeps
        animation/mechanical states such as BLINKING, PICKUP, DRAGGED, and
        DROPPING from making the nameplate flicker between unrelated labels.
        """
        mood = _STATE_MOODS.get(state)
        if mood is None:
            return None
        self.current = mood
        return mood
