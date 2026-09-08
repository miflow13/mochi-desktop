"""Pure state and placement rules for Mochi's contextual nameplate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from mochi.state import MochiState


class NameplateMode(StrEnum):
    HIDDEN = "hidden"
    COMPACT = "compact"
    HOVER = "hover"
    CONTEXT = "context"
    STATUS = "status"


FRIENDLY_STATE_LABELS = {
    MochiState.IDLE: "Resting",
    MochiState.BLINKING: "Resting",
    MochiState.BOUNCING: "Happy",
    MochiState.SQUISHING: "Happy",
    MochiState.EXCITED: "Extra happy",
    MochiState.CURIOUS: "Curious",
    MochiState.SITTING: "Sitting",
    MochiState.HURT_SAD: "Sad",
    MochiState.WALKING: "Walking…",
    MochiState.SLEEPING: "Sleeping",
    MochiState.WAKING: "Waking up…",
    MochiState.DRAGGED: "Picked up",
}


def friendly_state_label(state: MochiState) -> str:
    return FRIENDLY_STATE_LABELS[state]


def sleep_action_label(state: MochiState) -> str:
    return "Wake" if state is MochiState.SLEEPING else "Sleep"


@dataclass
class NameplateState:
    mode: NameplateMode = NameplateMode.HIDDEN
    anchor_hovered: bool = False
    plate_hovered: bool = False
    generation: int = 0

    @property
    def hovered(self) -> bool:
        return self.anchor_hovered or self.plate_hovered

    def anchor_enter(self) -> NameplateMode:
        self.anchor_hovered = True
        if self.mode is not NameplateMode.CONTEXT:
            self.mode = NameplateMode.COMPACT
        self.generation += 1
        return self.mode

    def plate_enter(self) -> NameplateMode:
        self.plate_hovered = True
        return self.mode

    def expand_hover(self) -> NameplateMode:
        if self.hovered and self.mode is NameplateMode.COMPACT:
            self.mode = NameplateMode.HOVER
            self.generation += 1
        return self.mode

    def anchor_leave(self) -> NameplateMode:
        self.anchor_hovered = False
        return self.mode

    def plate_leave(self) -> NameplateMode:
        self.plate_hovered = False
        return self.mode

    def open_context(self) -> NameplateMode:
        self.mode = NameplateMode.CONTEXT
        self.generation += 1
        return self.mode

    def close(self) -> NameplateMode:
        self.mode = NameplateMode.COMPACT if self.hovered else NameplateMode.HIDDEN
        self.generation += 1
        return self.mode

    def close_context(self) -> NameplateMode:
        """Unconditionally release context interaction state; safe to repeat."""
        self.anchor_hovered = False
        self.plate_hovered = False
        self.mode = NameplateMode.HIDDEN
        self.generation += 1
        return self.mode

    def begin_drag(self) -> NameplateMode:
        self.anchor_hovered = False
        self.plate_hovered = False
        self.mode = NameplateMode.HIDDEN
        self.generation += 1
        return self.mode

    def can_hide(self, generation: int) -> bool:
        return generation == self.generation and self.mode is not NameplateMode.CONTEXT


class ContextActionDispatcher:
    """Hold a menu action until GTK confirms that its popover is closed."""

    def __init__(self) -> None:
        self._pending: tuple[Callable[..., None], tuple[object, ...]] | None = None

    @property
    def pending(self) -> bool:
        return self._pending is not None

    def begin(
        self,
        cleanup: Callable[[], None],
        callback: Callable[..., None] | None,
        *args: object,
    ) -> None:
        self._pending = None if callback is None else (callback, args)
        cleanup()

    def complete(self) -> None:
        pending = self._pending
        self._pending = None
        if pending is not None:
            callback, args = pending
            callback(*args)


@dataclass(frozen=True)
class PlatePlacement:
    side: str
    offset_x: int


def choose_plate_placement(
    pet_x: int, pet_width: int, plate_width: int, work_x: int, work_width: int,
    space_above: int, space_below: int, plate_height: int,
) -> PlatePlacement:
    side = "above" if space_above >= plate_height or space_above >= space_below else "below"
    centered = pet_x + (pet_width - plate_width) // 2
    clamped = max(work_x, min(centered, work_x + work_width - plate_width))
    return PlatePlacement(side, clamped - centered)
