"""Direct click chirps and playful triple-click dialogue for Mochi."""

from __future__ import annotations

import random

from gi.repository import GLib

from mochi.sound import SoundEvent

from .clicks import ClickBurstDetector
from .engine import SpeechText, speech_display_seconds
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
        self._preserve_presence_bubble_for_press = False
        super().__init__(*args, **kwargs)

    def _on_pressed(self, *args) -> None:
        """Keep an existing speech bubble alive while a press may become a drag.

        PresenceBuddyMixin historically dismissed speech on every press. That made
        the bubble disappear before X11 drag-following could move it. Preserve the
        current line during the press sequence; explicit UI actions such as opening
        the context menu still dismiss through their own paths.
        """
        self._preserve_presence_bubble_for_press = True
        try:
            super()._on_pressed(*args)
        finally:
            self._preserve_presence_bubble_for_press = False

    def _dismiss_presence_bubble(self, *, user_initiated: bool) -> None:
        if user_initiated and self._preserve_presence_bubble_for_press:
            return
        super()._dismiss_presence_bubble(user_initiated=user_initiated)

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

    def _show_startup_greeting(self) -> bool:
        """Show startup speech with the same visible typing beat as ambient lines."""
        self._presence_startup_source_id = None
        if self._presence_shutting_down or self._preview_mode:
            return GLib.SOURCE_REMOVE

        tuning = self._ambient_presence_engine.tuning
        bubble = self._presence_bubble
        if (
            not tuning.speech_enabled
            or not tuning.ambient_reactions_enabled
            or tuning.quiet_mode
            or self._user_idle
            or bubble is None
        ):
            return GLib.SOURCE_REMOVE

        text = self._ambient_presence_engine.phrases.choose(
            "startup",
            exclude_recent=True,
        )
        presentation = SpeechText(text, typing_preview=True)
        if bubble.show(
            presentation,
            duration_seconds=speech_display_seconds(text),
        ):
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug("[presence] startup greeting typing-preview text=%r", text)
        return GLib.SOURCE_REMOVE

    def _preview_presence_category(self, category: str) -> None:
        """Preview production-style typing presentation from Mochi Lab on demand."""
        bubble = self._presence_bubble
        if bubble is None:
            self._logger.debug("[presence] developer preview unavailable: no bubble")
            return

        self._dismiss_presence_bubble(user_initiated=False)
        try:
            text = self._ambient_presence_engine.phrases.choose(
                category,
                exclude_recent=True,
            )
        except KeyError:
            category = "ambient"
            text = self._ambient_presence_engine.phrases.choose(
                category,
                exclude_recent=True,
            )

        presentation = SpeechText(text, typing_preview=True)
        if bubble.show(
            presentation,
            duration_seconds=speech_display_seconds(text),
        ):
            # Developer previews remain outside production cooldown accounting.
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug(
                "[presence] developer typing-preview category=%s text=%r",
                category,
                text,
            )


class PresenceBuddy(ClickDialogueMixin, MusicDanceMixin, BasePresenceBuddy):
    """Layer-shell buddy with Mochi Sense, music dance, and click dialogue."""


class PresenceX11Buddy(ClickDialogueMixin, MusicDanceMixin, BasePresenceX11Buddy):
    """X11/XWayland buddy with Mochi Sense, music dance, and click dialogue."""
