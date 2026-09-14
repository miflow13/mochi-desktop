"""Direct click chirps and playful triple-click dialogue for Mochi."""

from __future__ import annotations

import random

from gi.repository import GLib

from mochi.quick_start import QuickStartMixin
from mochi.sound import SoundEvent

from .clicks import ClickBurstDetector
from .edge_roam_controls import EdgeRoamMixin
from .engine import SpeechText, speech_display_seconds
from .fedora_mode import FedoraModeMixin
from .idle_look import IdleLookMixin
from .integration import (
    PresenceBuddy as BasePresenceBuddy,
    PresenceX11Buddy as BasePresenceX11Buddy,
)
from .music_dance import MusicDanceMixin
from .nameplate_controls import NameplateMixin
from .terminal_cowork import TerminalCoworkMixin


CLICK_BURST_PHRASES = (
    "owie!",
    "hey, i'm soft!",
    "gentle!",
    "eep!",
    "tiny creature here!",
)

FIRST_STARTUP_GREETING = (
    "Hi! I'm Mochi 🌱\n"
    "I'll hang out while you work and react to little things you do.\n"
    'Right-click me anytime and choose "What can Mochi do?" to learn more.\n'
    "I'll try not to get in the way. ♡"
)
FIRST_STARTUP_GREETING_SECONDS = 12.0
STARTUP_GREETING_RETRY_MS = 600
STARTUP_GREETING_MAX_ATTEMPTS = 10


class ClickDialogueMixin:
    """Add immediate click audio and a playful three-click response."""

    def __init__(self, *args, **kwargs) -> None:
        self._click_burst_detector = ClickBurstDetector(
            required_clicks=3,
            window_seconds=1.4,
        )
        self._fedora_click_detector = ClickBurstDetector(
            required_clicks=6,
            window_seconds=2.4,
        )
        self._last_click_burst_phrase: str | None = None
        self._preserve_presence_bubble_for_press = False
        self._startup_greeting_attempts = 0
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
        fedora_triggered = False
        if not self._preview_mode:
            # Play on the accepted pointer click itself, not later when a queued
            # bounce/squish animation happens to begin.
            self._sound.play(SoundEvent.CLICK)
            burst_triggered = self._click_burst_detector.record()
            fedora_triggered = self._fedora_click_detector.record()

        if fedora_triggered:
            # Six rapid clicks are intentionally secret. They take precedence
            # over the normal triple-click line and toggle the held Fedora mode.
            self._click_burst_detector.reset()
            self._toggle_fedora_mode()
            return

        if getattr(self, "_fedora_mode_holding", False):
            # Keep counting toward the secret six-click toggle without letting
            # normal click reactions replace the Fedora hat loop.
            return

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
        # Replace any current bubble and do not spend AmbiSense cooldown budget.
        self._dismiss_presence_bubble(user_initiated=False)
        shown = bubble.show(
            text,
            duration_seconds=min(3.0, speech_display_seconds(text)),
        )
        if shown:
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug("[presence] triple-click dialogue text=%r", text)
        return shown

    def _schedule_startup_greeting_retry(self, reason: str) -> bool:
        """Retry a startup greeting that lost a temporary presentation race."""
        self._startup_greeting_attempts += 1
        if self._startup_greeting_attempts >= STARTUP_GREETING_MAX_ATTEMPTS:
            self._logger.debug(
                "[presence] startup greeting abandoned after %d attempts reason=%s",
                self._startup_greeting_attempts,
                reason,
            )
            return GLib.SOURCE_REMOVE

        self._presence_startup_source_id = GLib.timeout_add(
            STARTUP_GREETING_RETRY_MS,
            self._show_startup_greeting,
        )
        self._logger.debug(
            "[presence] startup greeting deferred attempt=%d reason=%s",
            self._startup_greeting_attempts,
            reason,
        )
        return GLib.SOURCE_REMOVE

    def _show_startup_greeting(self) -> bool:
        """Show first-run onboarding once, then greet every later app launch."""
        self._presence_startup_source_id = None
        if self._presence_shutting_down or self._preview_mode:
            return GLib.SOURCE_REMOVE

        tuning = self._ambient_presence_engine.tuning
        if (
            not tuning.speech_enabled
            or not tuning.ambient_reactions_enabled
            or tuning.quiet_mode
        ):
            return GLib.SOURCE_REMOVE

        bubble = self._presence_bubble
        if bubble is None:
            return self._schedule_startup_greeting_retry("bubble-not-ready")
        if self._user_idle:
            return self._schedule_startup_greeting_retry("user-idle")
        if bubble.visible:
            return self._schedule_startup_greeting_retry("bubble-busy")

        first_startup = not self._config.load_first_startup_dialogue_seen()
        if first_startup:
            text = FIRST_STARTUP_GREETING
            duration_seconds = FIRST_STARTUP_GREETING_SECONDS
        else:
            text = self._ambient_presence_engine.phrases.choose(
                "startup",
                exclude_recent=True,
            )
            duration_seconds = speech_display_seconds(text)

        presentation = SpeechText(text, typing_preview=True)
        if not bubble.show(
            presentation,
            duration_seconds=duration_seconds,
        ):
            return self._schedule_startup_greeting_retry("bubble-rejected")

        self._startup_greeting_attempts = 0
        if first_startup:
            # Persist only after the bubble is actually visible. A temporary
            # startup race now retries in-session instead of consuming the intro.
            self._config.save_first_startup_dialogue_seen(True)
            self._logger.info("[presence] first-startup introduction shown")
        else:
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug(
                "[presence] session startup greeting typing-preview text=%r",
                text,
            )
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


class PresenceBuddy(
    ClickDialogueMixin,
    IdleLookMixin,
    QuickStartMixin,
    FedoraModeMixin,
    TerminalCoworkMixin,
    MusicDanceMixin,
    EdgeRoamMixin,
    NameplateMixin,
    BasePresenceBuddy,
):
    """Layer-shell buddy with terminal coworking, AmbiSense, music, and dialogue."""


class PresenceX11Buddy(
    ClickDialogueMixin,
    IdleLookMixin,
    QuickStartMixin,
    FedoraModeMixin,
    TerminalCoworkMixin,
    MusicDanceMixin,
    EdgeRoamMixin,
    NameplateMixin,
    BasePresenceX11Buddy,
):
    """X11 buddy with terminal coworking, AmbiSense, music, and dialogue."""
