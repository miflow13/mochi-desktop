"""Architecture regressions for the modular Buddy runtime."""

from __future__ import annotations

import inspect
import logging
from unittest.mock import Mock

from mochi.ambient_activity import AmbientActivityController
from mochi.buddy import Buddy
from mochi.buddy_menu import BuddyMenuController
from mochi.state import MochiState, StateMachine
from mochi.state_controller import BehaviorStateController


def test_buddy_uses_composition_instead_of_more_behavior_mixins() -> None:
    assert BuddyMenuController not in Buddy.__mro__
    assert AmbientActivityController not in Buddy.__mro__
    source = inspect.getsource(Buddy.__init__)
    assert "self._menu_ui = BuddyMenuController(self)" in source
    assert "self._ambient_activity = AmbientActivityController(self)" in source


def test_buddy_menu_hooks_are_thin_controller_delegates() -> None:
    source = inspect.getsource(Buddy._build_context_menu)
    assert "_menu_ui_for(self)._build_context_menu" in source
    assert "Gtk." not in source


def test_buddy_ambient_hooks_are_thin_controller_delegates() -> None:
    source = inspect.getsource(Buddy._start_typing_emote)
    assert "_ambient_activity_for(self)._start_typing_emote" in source
    assert "ANIMATIONS" not in source


def test_buddy_transition_method_delegates_to_state_controller() -> None:
    source = inspect.getsource(Buddy._transition_to)

    assert "_state_controller_for(self).request(next_state)" in source
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


def test_menu_windows_anchor_to_buddy_widget_not_controller() -> None:
    context_source = inspect.getsource(BuddyMenuController._build_context_menu)
    developer_source = inspect.getsource(BuddyMenuController._build_developer_menu)

    assert "anchor_widget=self._buddy" in context_source
    assert "anchor_widget=self._buddy" in developer_source
    assert "anchor_widget=self," not in context_source
    assert "anchor_widget=self," not in developer_source


def test_menu_animation_serial_is_owned_by_buddy() -> None:
    source = inspect.getsource(BuddyMenuController)

    assert 'getattr(self._buddy, "_menu_animation_serial", 0)' in source
    assert 'getattr(self, "_menu_animation_serial", 0)' not in source
