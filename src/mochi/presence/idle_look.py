"""Low-priority ambient look cycle for standing-idle Mochi."""

from __future__ import annotations

import random

from gi.repository import GLib

from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class IdleLookMixin:
    """Let standing-idle Mochi glance around on an independent cycle."""

    IDLE_LOOK_INTERVAL_SECONDS = (5, 20)
    IDLE_LOOK_ANIMATION = "look"

    def __init__(self, *args, **kwargs) -> None:
        self._idle_look_source_id: int | None = None
        self._idle_look_active = False
        self._idle_look_resume_position: tuple[int, int] | None = None
        super().__init__(*args, **kwargs)

        if not self._preview_mode:
            self._schedule_idle_look()

    def _schedule_idle_look(self) -> None:
        if (
            self._idle_look_source_id is not None
            or getattr(self, "_presence_shutting_down", False)
            or self._preview_mode
        ):
            return
        delay = random.randint(*self.IDLE_LOOK_INTERVAL_SECONDS)
        self._idle_look_source_id = GLib.timeout_add_seconds(
            delay, self._try_idle_look
        )
        self._logger.debug("Idle look scheduled in %d seconds", delay)

    def _reschedule_idle_look(self) -> None:
        source_id = self._idle_look_source_id
        self._idle_look_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        if not self._idle_look_active:
            self._schedule_idle_look()

    def _try_idle_look(self) -> bool:
        self._idle_look_source_id = None
        if self._can_start_idle_look():
            self._play_idle_look()
        else:
            # Keep the cadence independent from mouse/keyboard activity. If
            # another Mochi state owns presentation, simply try again later.
            self._schedule_idle_look()
        return GLib.SOURCE_REMOVE

    def _can_start_idle_look(self) -> bool:
        return bool(
            not getattr(self, "_presence_shutting_down", False)
            and not self._user_idle
            and self.state.current is MochiState.IDLE
            and self._current_animation == "idle"
            and self.player.animation is ANIMATIONS["idle"]
        )

    def _play_idle_look(self) -> bool:
        if not self._can_start_idle_look():
            return False
        self._idle_look_resume_position = (
            self.player.frame_index,
            self.player.elapsed_ms,
        )
        self._idle_look_active = True
        self._current_animation = self.IDLE_LOOK_ANIMATION
        self._active_animation = ANIMATIONS[self.IDLE_LOOK_ANIMATION]
        self._pending_animation = None
        self.player.play(self._active_animation)
        self._logger.debug("Animation: idle -> %s", self.IDLE_LOOK_ANIMATION)
        self.queue_draw()
        return True

    def _restore_idle_after_look(self, *, resume_ambient: bool) -> None:
        frame_index, elapsed_ms = self._idle_look_resume_position or (0, 0)
        self._idle_look_resume_position = None
        self._idle_look_active = False
        self._current_animation = "idle"
        self._active_animation = ANIMATIONS["idle"]
        self._pending_animation = None
        self.player.play(
            ANIMATIONS["idle"],
            frame_index=frame_index,
            elapsed_ms=elapsed_ms,
        )
        self._logger.debug("Animation: %s -> idle (resumed)", self.IDLE_LOOK_ANIMATION)
        self.queue_draw()
        self._schedule_idle_look()
        if resume_ambient:
            self._maybe_resume_ambient_activity()

    def _cancel_idle_look(self) -> bool:
        if not self._idle_look_active:
            return False
        self._restore_idle_after_look(resume_ambient=False)
        return True

    def _finish_reaction(self, finished_animation) -> None:
        if (
            self._idle_look_active
            and self._current_animation == self.IDLE_LOOK_ANIMATION
            and finished_animation is self._active_animation
        ):
            self._restore_idle_after_look(resume_ambient=True)
            return
        super()._finish_reaction(finished_animation)

    def _play_animation(self, name: str, after: str | None = None) -> None:
        if self._idle_look_active and name != self.IDLE_LOOK_ANIMATION:
            self._restore_idle_after_look(resume_ambient=False)
        super()._play_animation(name, after=after)

    # Higher-priority Mochi states still own presentation. Ordinary pointer and
    # keyboard activity no longer cancel or restart the look timer; only an
    # actual state transition interrupts the visual cycle.
    def _start_typing_emote(self) -> bool:
        self._cancel_idle_look()
        return super()._start_typing_emote()

    def _start_watching_emote(self) -> bool:
        self._cancel_idle_look()
        return super()._start_watching_emote()

    def _start_searching_emote(self) -> bool:
        self._cancel_idle_look()
        return super()._start_searching_emote()

    def _start_dancing_emote(self) -> bool:
        self._cancel_idle_look()
        return super()._start_dancing_emote()

    def _start_computer_emote(self) -> bool:
        self._cancel_idle_look()
        return super()._start_computer_emote()

    def _start_heart_emote(self, ignore_cooldown: bool = False) -> bool:
        self._cancel_idle_look()
        return super()._start_heart_emote(ignore_cooldown=ignore_cooldown)

    def _begin_terminal_coworking(self) -> bool:
        self._cancel_idle_look()
        return super()._begin_terminal_coworking()

    def _begin_vscode_coworking(self) -> bool:
        self._cancel_idle_look()
        return super()._begin_vscode_coworking()

    def shutdown_presence(self) -> None:
        source_id = self._idle_look_source_id
        self._idle_look_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        self._idle_look_active = False
        self._idle_look_resume_position = None
        super().shutdown_presence()
