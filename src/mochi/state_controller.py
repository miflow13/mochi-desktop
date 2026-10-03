"""Single owner for guarded Mochi behavior-state transitions."""

from __future__ import annotations

from collections.abc import Callable
import logging

from mochi.behavior import can_transition
from mochi.state import MochiState, StateMachine


TransitionGuard = Callable[[MochiState, MochiState], bool]


class BehaviorStateController:
    """Apply behavior transition policy before mutating the shared state machine.

    Feature mixins should request transitions through Buddy._transition_to(),
    which delegates here. This keeps rejection policy/logging centralized while
    preserving StateMachine as the small observable state record.
    """

    def __init__(
        self,
        state: StateMachine,
        *,
        logger: logging.Logger | None = None,
        transition_guard: TransitionGuard = can_transition,
    ) -> None:
        self._state = state
        self._logger = logger or logging.getLogger(__name__)
        self._transition_guard = transition_guard

    @property
    def state(self) -> StateMachine:
        return self._state

    def allows(self, next_state: MochiState) -> bool:
        """Check transition policy without mutating the shared state machine."""
        return self._transition_guard(self._state.current, next_state)

    def request(self, next_state: MochiState) -> bool:
        current = self._state.current
        if not self.allows(next_state):
            self._logger.debug(
                "Rejected state transition: %s -> %s",
                current.name,
                next_state.name,
            )
            return False
        self._state.transition_to(next_state)
        return True
