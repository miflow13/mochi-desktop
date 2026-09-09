"""Pure presentation rules for Mochi's contextual status overlay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mochi.state import MochiState


class OverlayTrigger(StrEnum):
    HOVER = "hover"


FRIENDLY_STATE_LABELS = {
    MochiState.IDLE: "Happy",
    MochiState.BLINKING: "Happy",
    MochiState.BOUNCING: "Happy",
    MochiState.SQUISHING: "Happy",
    MochiState.EXCITED: "Extra happy",
    MochiState.HEART: "Loved",
    MochiState.TYPING: "Typing",
    MochiState.WALKING: "Walking",
    MochiState.FALLING_ASLEEP: "Falling asleep",
    MochiState.SLEEPING: "Sleeping",
    MochiState.WAKING: "Waking up",
    MochiState.DRAGGED: "Dragged",
}


def friendly_state_label(state: MochiState) -> str:
    return FRIENDLY_STATE_LABELS[state]


def clamp_status_value(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


class OverlayMode(StrEnum):
    HIDDEN = "hidden"
    PEEK = "peek"
    EXPANDED = "expanded"


@dataclass
class OverlayVisibility:
    mode: OverlayMode = OverlayMode.HIDDEN
    generation: int = 0

    def present(self, mode: OverlayMode) -> int:
        self.mode = mode
        self.generation += 1
        return self.generation

    def hide(self) -> int:
        self.mode = OverlayMode.HIDDEN
        self.generation += 1
        return self.generation

    def can_hide(self, generation: int, mode: OverlayMode) -> bool:
        return self.generation == generation and self.mode is mode


def should_show_overlay(trigger: OverlayTrigger) -> bool:
    return trigger is OverlayTrigger.HOVER
