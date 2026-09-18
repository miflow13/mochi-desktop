"""Regression coverage for presentation-priority speech suppression."""

from unittest.mock import Mock

from mochi.presence.bubble import SpeechBubble


def test_speech_bubble_rejects_quip_when_presentation_priority_blocks_it() -> None:
    bubble = object.__new__(SpeechBubble)
    bubble._can_show = Mock(return_value=False)
    bubble._logger = Mock()

    assert bubble.show("not now", duration_seconds=2.0) is False
    bubble._can_show.assert_called_once_with()
