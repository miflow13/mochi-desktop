"""Music-reactive dance behavior layered around Mochi's stable Buddy core."""

from __future__ import annotations

from gi.repository import GLib

from mochi.music_activity import MusicActivityMonitor
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class MusicDanceMixin:
    """Dance during recognized music playback without touching pointer handling.

    Ambient priority is: watchable video > music > file browsing > idle. Direct
    interactions and typing remain higher priority and temporarily interrupt the
    dance; the dance resumes automatically while music is still playing.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._music_monitor: MusicActivityMonitor | None = None
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        self._music_monitor = MusicActivityMonitor(
            on_music_started=self._on_music_started,
            on_music_stopped=self._on_music_stopped,
            logger=self._logger,
        )
        self._music_monitor.start()

    def shutdown_presence(self) -> None:
        if self._music_monitor is not None:
            self._music_monitor.stop()
            self._music_monitor = None
        super().shutdown_presence()

    def _build_developer_menu(self):
        """Expose a manual Dance action in Mochi Lab for animation testing."""
        popover = super()._build_developer_menu()
        dance_button, _ = self._make_menu_button(
            "Dance",
            "media-playback-start-symbolic",
            self._test_dance_emote,
        )
        self._developer_menu_content.append(dance_button)
        self._developer_menu_animated_rows = (
            *self._developer_menu_animated_rows,
            dance_button,
        )
        return popover

    def _test_dance_emote(self, _button) -> None:
        self._close_developer_menu_then(self._start_dancing_emote)

    def _on_user_idle(self) -> None:
        """Do not auto-sleep while music is actively playing."""
        self._user_idle = True
        if (
            self._music_monitor is not None
            and self._music_monitor.music_playing
        ):
            self._logger.debug("Presence idle deferred while music is playing")
            return
        super()._on_user_idle()

    def _generic_browser_watch_active(self) -> bool:
        """Return whether WATCHING came only from coarse focused-browser fallback."""
        monitor = self._media_monitor
        backend = getattr(monitor, "_backend", None) if monitor is not None else None
        return bool(
            monitor is not None
            and monitor.youtube_playing
            and getattr(backend, "watching_via_browser_focus", False)
        )

    def _on_music_started(self) -> None:
        """Start the low-priority dance when recognized music begins."""
        # Sparse Chromium MPRIS data can temporarily look like generic focused
        # browser media. Confident music detection is more specific, so music
        # may replace only that coarse fallback WATCHING state. Explicit
        # YouTube/video detection continues to outrank dancing.
        if (
            self.state.current is MochiState.WATCHING
            and self._generic_browser_watch_active()
        ):
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        self._start_dancing_emote()

    def _on_music_stopped(self) -> None:
        was_dancing = self.state.current is MochiState.DANCING
        if was_dancing:
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
            self._logger.debug("Music dance stopped")

        if self._user_idle:
            youtube_playing = bool(
                self._media_monitor is not None
                and self._media_monitor.youtube_playing
            )
            if not self._context_menu_open and not youtube_playing:
                self._begin_sleep()
            return

        if (
            was_dancing
            and not self._maybe_resume_watching()
            and not self._maybe_resume_vscode_coworking()
            and not self._maybe_resume_searching()
        ):
            self._schedule_computer_idle_emote()

    def _start_dancing_emote(self) -> bool:
        # Music should not wake an already-idle-away user or steal focus from
        # video, typing, direct reactions, sleep, pickup, drag, or drop.
        if (
            self._user_idle
            or self.state.current not in (MochiState.IDLE, MochiState.SEARCHING)
            or self._context_menu_open
            or (
                self.state.current is MochiState.IDLE
                and self.player.animation is not ANIMATIONS["idle"]
            )
        ):
            return False
        if not self._transition_to(MochiState.DANCING):
            return False
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._play_animation("dance", after=None)
        self._logger.debug("Music dance started")
        return True

    def _maybe_resume_dancing(self) -> bool:
        if (
            self._music_monitor is None
            or not self._music_monitor.music_playing
            or self._user_idle
            or self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        return self._start_dancing_emote()

    def _maybe_resume_watching(self) -> bool:
        # A confidently detected music source outranks only the intentionally
        # broad browser-focus fallback. Real/identified video still wins.
        if (
            self._music_monitor is not None
            and self._music_monitor.music_playing
            and self._generic_browser_watch_active()
        ):
            return False
        return super()._maybe_resume_watching()

    def _maybe_resume_ambient_activity(self) -> bool:
        # Preserve Buddy's established media/file priority and insert music in
        # the middle. This is called after direct reactions and typing finish.
        return (
            self._maybe_resume_watching()
            or self._maybe_resume_vscode_coworking()
            or self._maybe_resume_dancing()
            or self._maybe_resume_searching()
        )

    def _start_watching_emote(self) -> bool:
        # Explicit watchable video wins over music. A coarse focused-browser
        # fallback does not steal the state back from known music playback.
        if (
            self.state.current is MochiState.TYPING
            and getattr(self, "_vscode_coworking_active", False)
        ):
            # Explicit watchable video outranks contextual coworking. Skip the
            # outro here so the higher-priority reaction feels immediate.
            self._vscode_coworking_active = False
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        if self.state.current is MochiState.DANCING:
            if (
                self._music_monitor is not None
                and self._music_monitor.music_playing
                and self._generic_browser_watch_active()
            ):
                return False
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        return super()._start_watching_emote()

    def _on_youtube_stopped(self) -> None:
        if self.state.current is not MochiState.WATCHING:
            return

        self._transition_to(MochiState.IDLE)
        self._play_animation("idle")
        self._logger.debug("YouTube watch-along stopped")

        if self._user_idle:
            self._begin_sleep()
        elif (
            not self._maybe_resume_vscode_coworking()
            and not self._maybe_resume_dancing()
            and not self._maybe_resume_searching()
        ):
            self._schedule_computer_idle_emote()

    def _on_file_activity_stopped(self) -> None:
        if self.state.current is not MochiState.SEARCHING:
            return
        self._transition_to(MochiState.IDLE)
        self._play_animation("idle")
        self._logger.debug("File activity emote stopped")
        if (
            not self._maybe_resume_watching()
            and not self._maybe_resume_vscode_coworking()
            and not self._maybe_resume_dancing()
        ):
            self._schedule_computer_idle_emote()

    def _start_typing_emote(self) -> bool:
        # Typing is intentional user activity, so it temporarily outranks dance.
        if self.state.current is MochiState.DANCING:
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        return super()._start_typing_emote()

    def _cancel_active_emote(self) -> bool:
        if self.state.current is MochiState.DANCING:
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
            return True
        return super()._cancel_active_emote()
