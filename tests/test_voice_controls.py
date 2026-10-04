"""Buddy wiring for the "Talk to Mochi" control."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from mochi.presence.voice_controls import VoiceControlMixin


class _Base:
    def __init__(self, placement) -> None:
        self._placement = placement
        self._preview_mode = False
        self._window = None
        self._logger = logging.getLogger(__name__)


class _Buddy(VoiceControlMixin, _Base):
    pass


def test_the_layer_shell_buddy_gets_no_control() -> None:
    # Positioning is X11-only; on native Wayland the control would map
    # detached from Mochi, so it is not created (and no D-Bus is touched).
    buddy = _Buddy(SimpleNamespace(layer_shell_enabled=True))

    assert buddy._voice_control is None
    assert buddy._voice_proximity is None
