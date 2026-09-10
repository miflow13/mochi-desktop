"""The small, explicit state machine used by the buddy."""

from __future__ import annotations

from enum import Enum, auto
import logging


class MochiState(Enum):
    IDLE = auto()
    BLINKING = auto()
    BOUNCING = auto()
    SQUISHING = auto()
    EXCITED = auto()
    WALKING = auto()
    SLEEPING = auto()
    WAKING = auto()
    HEART = auto()
    COMPUTER = auto()
    TYPING = auto()
    WATCHING = auto()
    DANCING = auto()
    SEARCHING = auto()
    PICKUP = auto()
    DRAGGED = auto()
    DROPPING = auto()


class StateMachine:
    def __init__(self) -> None:
        self.current = MochiState.IDLE
        self._logger = logging.getLogger(__name__)

    def transition_to(self, next_state: MochiState) -> None:
        if next_state is self.current:
            return
        previous = self.current
        self.current = next_state
        self._logger.debug("Mochi state: %s -> %s", previous.name, next_state.name)
