"""Ambient activity routing for Mochi's core buddy behavior.

Typing, video watching, file browsing, and user-presence callbacks live here so
the base Buddy widget does not own detector-specific behavior orchestration.
"""

from __future__ import annotations

import time

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class AmbientActivityMixin:
    """Translate ambient activity callbacks into Mochi behavior states."""

    def _on_typing_activity(self) -> None:
        """Mirror a recognized typing burst without inspecting typed content."""
        self._last_interaction = time.monotonic()
        if self._user_idle or self.state.current is MochiState.SLEEPING:
            self._on_user_active()
        if self.state.current is MochiState.TYPING:
            return
        self._start_typing_emote()

    def _start_typing_emote(self) -> bool:
        if (
            self.state.current not in (
                MochiState.IDLE,
                MochiState.WATCHING,
                MochiState.SEARCHING,
            )
            or self._context_menu_open
            or (
                self.state.current is MochiState.IDLE
                and self.player.animation is not ANIMATIONS["idle"]
            )
        ):
            return False
        if not self._transition_to(MochiState.TYPING):
            return False
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._play_animation("typing_intro", after="typing_loop")
        self._logger.debug("Typing mirror animation started")
        return True

    def _on_typing_stopped(self) -> None:
        if self.state.current is not MochiState.TYPING:
            return
        self._last_interaction = time.monotonic()
        if self._current_animation == "typing_intro":
            self._pending_animation = "typing_outro"
        elif self._current_animation == "typing_loop":
            self._play_animation("typing_outro", after="idle")
        self._logger.debug("Typing mirror animation stopping")

    def _on_youtube_started(self) -> None:
        """Start Mochi's low-priority watch-along when YouTube is playing."""
        self._on_user_active()
        self._start_watching_emote()

    def _on_youtube_stopped(self) -> None:
        if self.state.current is not MochiState.WATCHING:
            return

        self._transition_to(MochiState.IDLE)
        self._play_animation("idle")
        self._logger.debug("YouTube watch-along stopped")

        # Resolve the next state immediately. This matters when the user tabs
        # from YouTube into Files: the file-browsing signal may have arrived
        # while WATCHING still had higher priority.
        if self._user_idle:
            self._begin_sleep()
        elif not self._maybe_resume_searching():
            self._schedule_computer_idle_emote()

    def _start_watching_emote(self) -> bool:
        if (
            self.state.current not in (MochiState.IDLE, MochiState.SEARCHING)
            or self._context_menu_open
            or (
                self.state.current is MochiState.IDLE
                and self.player.animation is not ANIMATIONS["idle"]
            )
        ):
            return False
        if not self._transition_to(MochiState.WATCHING):
            return False
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._play_animation("watch", after=None)
        self._logger.debug("YouTube watch-along started")
        return True

    def _maybe_resume_watching(self) -> bool:
        if (
            self._media_monitor is None
            or not self._media_monitor.youtube_playing
            or self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        return self._start_watching_emote()

    def _on_file_activity_started(self) -> None:
        """Start Mochi's low-priority magnifying-glass file activity emote."""
        self._on_user_active()
        self._start_searching_emote()

    def _on_file_activity_stopped(self) -> None:
        if self.state.current is not MochiState.SEARCHING:
            return
        self._transition_to(MochiState.IDLE)
        self._play_animation("idle")
        self._logger.debug("File activity emote stopped")
        if not self._maybe_resume_watching():
            self._schedule_computer_idle_emote()

    def _start_searching_emote(self) -> bool:
        if (
            self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        if not self._transition_to(MochiState.SEARCHING):
            return False
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._play_animation("searching", after=None)
        self._logger.debug("File activity emote started")
        return True

    def _maybe_resume_searching(self) -> bool:
        if (
            self._file_activity_monitor is None
            or not self._file_activity_monitor.file_activity_active
            or self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        return self._start_searching_emote()

    def _maybe_resume_ambient_activity(self) -> bool:
        # Ambient priority: watching > searching > idle. Typing and direct
        # interaction sit above both and call this only after they finish.
        return self._maybe_resume_watching() or self._maybe_resume_searching()

    def _on_user_idle(self) -> None:
        """Put Mochi to sleep when truly idle, except during active playback."""
        self._user_idle = True
        if self._preview_mode or self.state.current not in (
            MochiState.IDLE, MochiState.BLINKING, MochiState.WALKING,
        ):
            return
        if self._context_menu_open:
            self._logger.debug("Presence idle deferred while context menu is open")
            return
        if self._media_monitor is not None and self._media_monitor.youtube_playing:
            self._logger.debug("Presence idle deferred while YouTube is playing")
            return
        self._logger.debug("User presence: idle")
        self._begin_sleep()

    def _on_user_active(self) -> None:
        """Wake sleeping Mochi on the first real user input after idle."""
        self._user_idle = False
        self._logger.debug("User presence: active")
        if self.state.current is MochiState.SLEEPING:
            self._wake_up()

    def _cancel_active_emote(self) -> bool:
        if self.state.current not in (
            MochiState.HEART,
            MochiState.COMPUTER,
            MochiState.TYPING,
            MochiState.WATCHING,
            MochiState.SEARCHING,
        ):
            return False
        if self.state.current is MochiState.TYPING and self._typing_monitor is not None:
            self._typing_monitor.reset()
        self._transition_to(MochiState.IDLE)
        self._play_animation("idle")
        return True
