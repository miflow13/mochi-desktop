"""Presentation-priority regression coverage for Mochi's state engine."""

from mochi.state import PresentationState, StateMachine


def test_level_up_presentation_blocks_dialogue_until_released() -> None:
    state = StateMachine()

    assert state.dialogue_allowed is True

    state.transition_presentation(PresentationState.LEVEL_UP)
    assert state.presentation is PresentationState.LEVEL_UP
    assert state.dialogue_allowed is False

    state.transition_presentation(PresentationState.NORMAL)
    assert state.presentation is PresentationState.NORMAL
    assert state.dialogue_allowed is True
