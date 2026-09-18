"""Architecture regressions for the modular Buddy runtime."""

from __future__ import annotations

import inspect
import logging
from unittest.mock import Mock

from mochi.ambient_activity import AmbientActivityMixin
from mochi.buddy import Buddy
from mochi.buddy_menu import BuddyMenuMixin
from mochi.state import MochiState, StateMachine
from mochi.state_controller import BehaviorStateController


def test_buddy_composes_menu_and_ambient_modules() -> None:
    assert issubclass(Buddy, BuddyMenuMixin)
    assert issubclass(Buddy, AmbientActivityMixin)


def test_menu_responsibilities_are_not_declared_on_buddy_anymore() -> None:
    assert "_build_context_menu" not in Buddy.__dict__
    assert "_build_developer_menu" not in Buddy.__dict__
    assert "_show_context_menu" not in Buddy.__dict__
    assert "_show_developer_menu" not in Buddy.__dict__


def test_ambient_activity_routing_is_not_declared_on_buddy_anymore() -> None:
    assert "_on_typing_activity" not in Buddy.__dict__
    assert "_on_youtube_started" not in Buddy.__dict__
    assert "_on_file_activity_started" not in Buddy.__dict__
    assert "_on_user_idle" not in Buddy.__dict__


def test_buddy_transition_method_delegates_to_state_controller() -> None:
    source = inspect.getsource(Buddy._transition_to)

    assert "self.state_controller.request(next_state)" in source
    assert "can_transition" not in source


def test_state_controller_accepts_allowed_transition() -> None:
    state = StateMachine()
    guard = Mock(return_value=True)
    controller = BehaviorStateController(state, transition_guard=guard)

    assert controller.request(MochiState.TYPING) is True
    guard.assert_called_once_with(MochiState.IDLE, MochiState.TYPING)
    assert state.current is MochiState.TYPING


def test_state_controller_rejects_transition_without_mutating_state() -> None:
    state = StateMachine()
    logger = Mock(spec=logging.Logger)
    guard = Mock(return_value=False)
    controller = BehaviorStateController(
        state,
        logger=logger,
        transition_guard=guard,
    )

    assert controller.request(MochiState.SLEEPING) is False
    assert state.current is MochiState.IDLE
    logger.debug.assert_called_once()
