"""Direct click chirps and playful triple-click dialogue for Mochi."""

from __future__ import annotations

import random

from mochi.sound import SoundEvent

from .clicks import ClickBurstDetector
from .engine import speech_display_seconds
from .integration import (
    PresenceBuddy as BasePresenceBuddy,
    PresenceX11Buddy as BasePresenceX11Buddy,
)
from .music_dance import MusicDanceMixin


CLICK_BURST_PHRASES = (
    "owie!",
    "hey, i'm soft!",
    "gentle!",
    "eep!",
    "tiny creature here!",
)


class ClickDialogueMixin:
    """Add immediate click audio and a playful three-click response."""

    def __init__(self, *args, **kwargs) -> None:
        self._click_burst_detector = ClickBurstDetector(
            required_clicks=3,
            window_seconds=1.4,
        )
        self._last_click_burst_phrase: str | None = None
        super().__init__(*args, **kwargs)

    def react_to_click(self) -> None:
        burst_triggered = False
        if not self._preview_mode:
            # Play on the accepted pointer click itself, not later when a queued
            # bounce/squish animation happens to begin.
            self._sound.play(SoundEvent.CLICK)
            burst_triggered = self._click_burst_detector.record()

        super().react_to_click()

        if burst_triggered:
            self._show_click_burst_dialogue()

    def _show_click_burst_dialogue(self) -> bool:
        bubble = self._presence_bubble
        tuning = self._ambient_presence_engine.tuning
        if bubble is None or not tuning.speech_enabled or tuning.quiet_mode:
            return False

        choices = tuple(
            phrase
            for phrase in CLICK_BURST_PHRASES
            if phrase != self._last_click_burst_phrase
        ) or CLICK_BURST_PHRASES
        text = random.choice(choices)
        self._last_click_burst_phrase = text

        # This is a direct user interaction, not unsolicited ambient speech.
        # Replace any current bubble and do not spend Mochi Sense cooldown budget.
        self._dismiss_presence_bubble(user_initiated=False)
        shown = bubble.show(
            text,
            duration_seconds=min(3.0, speech_display_seconds(text)),
        )
        if shown:
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug("[presence] triple-click dialogue text=%r", text)
        return shown


class PresenceBuddy(ClickDialogueMixin, MusicDanceMixin, BasePresenceBuddy):
    """Layer-shell buddy with Mochi Sense, music dance, and click dialogue."""


class PresenceX11Buddy(ClickDialogueMixin, MusicDanceMixin, BasePresenceX11Buddy):
    """X11/XWayland buddy with Mochi Sense, music dance, and click dialogue."""
