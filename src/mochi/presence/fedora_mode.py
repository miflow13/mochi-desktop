"""Hidden Fedora-hat easter egg mode for Mochi."""

from __future__ import annotations

from gi.repository import GLib

from mochi.sprites import ANIMATIONS
from mochi.state import MochiState

from .engine import speech_display_seconds


class FedoraModeMixin:
    """Hold Mochi in the Fedora-hat loop until the secret gesture toggles it off."""

    FEDORA_INTRO_ANIMATION = "fedora_intro"
    FEDORA_LOOP_ANIMATION = "fedora_loop"
    FEDORA_OUTRO_ANIMATION = "fedora_outro"
    FEDORA_ENGAGED_TEXT = "Fedora mode engaged"

    def __init__(self, *args, **kwargs) -> None:
        self._fedora_mode_active = False
        self._fedora_mode_exiting = False
        super().__init__(*args, **kwargs)

    @property
    def _fedora_mode_holding(self) -> bool:
        return self._fedora_mode_active or self._fedora_mode_exiting

    def _toggle_fedora_mode(self) -> bool:
        if self._fedora_mode_active:
            return self._stop_fedora_mode()
        if self._fedora_mode_exiting:
            return False
        return self._start_fedora_mode()

    def _start_fedora_mode(self) -> bool:
        if (
            self._preview_mode
            or self._context_menu_open
            or self.state.current
            in (
                MochiState.SLEEPING,
                MochiState.WAKING,
                MochiState.PICKUP,
                MochiState.DRAGGED,
                MochiState.DROPPING,
            )
        ):
            return False

        self._click_reactions.clear()
        self._pending_animation = None
        self._fedora_mode_active = True
        self._fedora_mode_exiting = False

        # Contextual coworking modes keep their detection state, but Fedora owns
        # the character presentation until it is explicitly toggled off.
        if hasattr(self, "_terminal_coworking_active"):
            self._terminal_coworking_active = False
        if hasattr(self, "_vscode_coworking_active"):
            self._vscode_coworking_active = False

        if not self._transition_to(MochiState.FEDORA):
            self._fedora_mode_active = False
            return False

        self._play_animation(self.FEDORA_INTRO_ANIMATION, after=None)
        self._show_fedora_engaged_dialogue()
        self._logger.info("Fedora mode engaged")
        return True

    def _stop_fedora_mode(self) -> bool:
        if not self._fedora_mode_active:
            return False

        self._fedora_mode_active = False
        self._fedora_mode_exiting = True
        self._pending_animation = None

        if self.state.current is not MochiState.FEDORA:
            # A direct pointer interaction may temporarily own the FSM. The
            # normal completion path will call _maybe_resume_ambient_activity,
            # where the Fedora outro is restored before other ambient states.
            return True

        if self._current_animation == self.FEDORA_INTRO_ANIMATION:
            # Let the authored hat-on transition finish cleanly; its completion
            # immediately advances into the authored hat-off transition.
            return True

        if self._current_animation != self.FEDORA_OUTRO_ANIMATION:
            self._play_animation(self.FEDORA_OUTRO_ANIMATION, after=None)
        self._logger.info("Fedora mode disengaging")
        return True

    def _show_fedora_engaged_dialogue(self) -> bool:
        bubble = getattr(self, "_presence_bubble", None)
        if bubble is None:
            return False
        self._dismiss_presence_bubble(user_initiated=False)
        text = self.FEDORA_ENGAGED_TEXT
        shown = bubble.show(
            text,
            duration_seconds=min(3.0, speech_display_seconds(text)),
        )
        if shown:
            self._ambient_presence_engine.phrases.remember(text)
        return shown

    def _finish_reaction(self, finished_animation) -> None:
        if finished_animation is self._active_animation:
            if self._current_animation == self.FEDORA_INTRO_ANIMATION:
                self._pending_animation = None
                if self._fedora_mode_active:
                    self._play_animation(self.FEDORA_LOOP_ANIMATION, after=None)
                else:
                    self._fedora_mode_exiting = True
                    self._play_animation(self.FEDORA_OUTRO_ANIMATION, after=None)
                return

            if self._current_animation == self.FEDORA_OUTRO_ANIMATION:
                self._pending_animation = None
                self._fedora_mode_exiting = False
                self._transition_to(MochiState.IDLE)
                self._play_animation("idle")
                if not self._maybe_resume_ambient_activity():
                    self._schedule_computer_idle_emote()
                self._logger.info("Fedora mode disengaged")
                return

        super()._finish_reaction(finished_animation)

        # Drag/pickup/drop may temporarily replace the Fedora art. As soon as
        # that direct interaction returns to idle, restore the held hat loop.
        if (
            self._fedora_mode_active
            and self.state.current is MochiState.IDLE
            and not self._context_menu_open
        ):
            self._resume_fedora_loop()

    def _resume_fedora_loop(self) -> bool:
        if (
            not self._fedora_mode_active
            or self.state.current is not MochiState.IDLE
            or self._context_menu_open
        ):
            return False
        if not self._transition_to(MochiState.FEDORA):
            return False
        self._play_animation(self.FEDORA_LOOP_ANIMATION, after=None)
        return True

    def _maybe_resume_ambient_activity(self) -> bool:
        if self._fedora_mode_active:
            if self.state.current is MochiState.FEDORA:
                return True
            if self._resume_fedora_loop():
                return True
        if self._fedora_mode_exiting:
            if self.state.current is MochiState.IDLE:
                if self._transition_to(MochiState.FEDORA):
                    self._play_animation(self.FEDORA_OUTRO_ANIMATION, after=None)
            return True
        return super()._maybe_resume_ambient_activity()

    def _begin_sleep(self) -> None:
        # Fedora mode is explicitly user-held. Do not auto-sleep and silently
        # remove the hat; the six-click gesture must end the mode first.
        if self._fedora_mode_holding:
            return
        super()._begin_sleep()

    def shutdown_presence(self) -> None:
        self._fedora_mode_active = False
        self._fedora_mode_exiting = False
        super().shutdown_presence()
