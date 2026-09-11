"""Terminal-focus coworking behavior for Mochi."""

from __future__ import annotations

from gi.repository import GLib

from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class TerminalCoworkMixin:
    """Keep Mochi at a terminal while a terminal window has active focus.

    The current asset is intentionally loop-only. Entry and exit are isolated in
    helpers so future terminal_intro / terminal_outro artwork can slot in without
    changing focus detection or the ambient priority rules.
    """

    TERMINAL_COWORK_DEBOUNCE_MS = 700
    TERMINAL_LOOP_ANIMATION = "terminal_loop"

    def __init__(self, *args, **kwargs) -> None:
        self._terminal_cowork_source_id: int | None = None
        self._terminal_coworking_active = False
        super().__init__(*args, **kwargs)

    def _on_presence_app_category_changed(self, category: str) -> None:
        previous = self._presence_app_category
        super()._on_presence_app_category_changed(category)

        if previous == "terminal" and category != "terminal":
            self._stop_terminal_coworking()
        if category == "terminal":
            self._schedule_terminal_coworking()

    def _on_user_active(self) -> None:
        super()._on_user_active()
        if self._presence_app_category == "terminal":
            self._schedule_terminal_coworking()

    def _on_typing_stopped(self) -> None:
        # A real typing burst ending must not put the laptop away while the
        # terminal itself is still focused. Focus owns this coworking state.
        if (
            self._presence_app_category == "terminal"
            and self.state.current is MochiState.TYPING
        ):
            self._ambient_presence_engine.record_typing_stopped()
            self._terminal_coworking_active = True
            return
        super()._on_typing_stopped()

    def _cancel_terminal_cowork_source(self) -> None:
        source_id = self._terminal_cowork_source_id
        self._terminal_cowork_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _schedule_terminal_coworking(self) -> None:
        """Debounce terminal focus so quick Alt-Tab passes stay visually quiet."""
        self._cancel_terminal_cowork_source()
        if (
            self._presence_shutting_down
            or self._presence_app_category != "terminal"
            or self._user_idle
        ):
            return
        self._terminal_cowork_source_id = GLib.timeout_add(
            self.TERMINAL_COWORK_DEBOUNCE_MS,
            self._begin_terminal_coworking,
        )

    def _begin_terminal_coworking(self) -> bool:
        self._terminal_cowork_source_id = None
        if (
            self._presence_shutting_down
            or self._presence_app_category != "terminal"
            or self._user_idle
            or self._context_menu_open
        ):
            return GLib.SOURCE_REMOVE

        # Real video remains the highest contextual ambient state.
        if (
            self.state.current is MochiState.WATCHING
            or (
                self._media_monitor is not None
                and self._media_monitor.youtube_playing
            )
        ):
            return GLib.SOURCE_REMOVE

        if self.state.current is MochiState.TYPING:
            self._play_terminal_loop()
            self._terminal_coworking_active = True
            self._logger.debug("Terminal coworking mode started")
            return GLib.SOURCE_REMOVE

        # Reuse the proven TYPING state for coworking lifecycle/interruptions,
        # then replace the normal typing art with the terminal-specific loop.
        if self._start_typing_emote():
            self._play_terminal_loop()
            self._terminal_coworking_active = True
            self._logger.debug("Terminal coworking mode started")
        return GLib.SOURCE_REMOVE

    def _play_terminal_loop(self) -> None:
        """Current entry hook; terminal_intro can replace this later."""
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._play_animation(self.TERMINAL_LOOP_ANIMATION, after=None)

    def _stop_terminal_coworking(self) -> None:
        """Current exit hook; terminal_outro can replace the idle jump later."""
        self._cancel_terminal_cowork_source()
        was_active = self._terminal_coworking_active
        self._terminal_coworking_active = False
        if not was_active:
            return

        if (
            self.state.current is MochiState.TYPING
            and self.player.animation is ANIMATIONS[self.TERMINAL_LOOP_ANIMATION]
        ):
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")

            # VS Code has its own debounce when focus moves there. For ordinary
            # destinations, restore any already-active music/file/video state.
            if self._presence_app_category not in {"terminal", "vscode"}:
                if not self._maybe_resume_ambient_activity():
                    self._schedule_computer_idle_emote()

        self._logger.debug("Terminal coworking mode stopped")

    def _maybe_resume_terminal_coworking(self) -> bool:
        if (
            self._presence_app_category != "terminal"
            or self._user_idle
            or self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
            or (
                self._media_monitor is not None
                and self._media_monitor.youtube_playing
            )
        ):
            return False

        if not self._start_typing_emote():
            return False
        self._play_terminal_loop()
        self._terminal_coworking_active = True
        self._logger.debug("Terminal coworking mode resumed")
        return True

    def _maybe_resume_vscode_coworking(self) -> bool:
        """Insert terminal focus immediately ahead of VS Code in cowork priority."""
        if self._maybe_resume_terminal_coworking():
            return True
        return super()._maybe_resume_vscode_coworking()

    def _start_watching_emote(self) -> bool:
        # Explicit watchable video can interrupt terminal coworking immediately.
        if (
            self.state.current is MochiState.TYPING
            and self._terminal_coworking_active
        ):
            self._terminal_coworking_active = False
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        return super()._start_watching_emote()

    def shutdown_presence(self) -> None:
        self._cancel_terminal_cowork_source()
        self._terminal_coworking_active = False
        super().shutdown_presence()
