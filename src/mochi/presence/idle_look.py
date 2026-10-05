"""Low-priority ambient look cycle for standing-idle Mochi."""

from __future__ import annotations

import random

from gi.repository import GLib

from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


def _active_idle_beat(buddy) -> str:
    """Name of the beat that owns standing-idle presentation.

    Read with getattr: some tests call these methods unbound on harnesses that
    never ran ``IdleLookMixin.__init__``.
    """
    return getattr(buddy, "_idle_beat_animation", None) or buddy.IDLE_LOOK_ANIMATION


class IdleLookMixin:
    """Own Mochi's short standing-idle beats.

    The timed glance-around (``look``) and curiosity's ``investigate`` beat both
    play while behavior state stays ``IDLE``. ``_idle_look_active`` is the single
    flag meaning "a standing-idle beat owns presentation"; ``_idle_beat_animation``
    names which beat. Any real state transition restores idle first.
    """

    IDLE_LOOK_INTERVAL_SECONDS = (5, 20)
    IDLE_LOOK_ANIMATION = "look"

    def __init__(self, *args, **kwargs) -> None:
        self._idle_look_source_id: int | None = None
        self._idle_look_active = False
        self._idle_beat_animation: str | None = None
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

    def _cancel_idle_look_timer(self) -> None:
        source_id = self._idle_look_source_id
        self._idle_look_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _reschedule_idle_look(self) -> None:
        self._cancel_idle_look_timer()
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
            and self._is_idle_visual_active()
        )

    def _play_idle_look(self) -> bool:
        return self._play_idle_beat(self.IDLE_LOOK_ANIMATION)

    def _play_idle_beat(self, name: str) -> bool:
        """Play one standing-idle beat, then resume idle where it left off."""
        if not self._can_start_idle_look():
            return False
        # Resolve first: an unknown name must raise before any state changes.
        animation = ANIMATIONS[name]
        # A beat can start outside the look timer (curiosity), so drop any armed
        # look; the restore then arms a fresh interval instead of a stale one.
        self._cancel_idle_look_timer()
        self._idle_look_resume_position = (
            self.player.frame_index,
            self.player.elapsed_ms,
        )
        self._idle_look_active = True
        self._idle_beat_animation = name
        self._current_animation = name
        self._active_animation = animation
        self._pending_animation = None
        self.player.play(animation)
        self._logger.debug("Animation: idle -> %s", name)
        self.queue_draw()
        return True

    def _restore_idle_after_look(self, *, resume_ambient: bool) -> None:
        beat = _active_idle_beat(self)
        frame_index, elapsed_ms = self._idle_look_resume_position or (0, 0)
        self._idle_look_resume_position = None
        self._idle_look_active = False
        self._idle_beat_animation = None
        idle_animation = self._animation_for("idle")
        frame_index = min(frame_index, len(idle_animation.frames) - 1)
        self._current_animation = "idle"
        self._active_animation = idle_animation
        self._pending_animation = None
        self.player.play(
            idle_animation,
            frame_index=frame_index,
            elapsed_ms=elapsed_ms,
        )
        self._logger.debug(
            "Animation: %s -> idle (resumed%s)",
            beat,
            "" if idle_animation.name == "idle" else f": {idle_animation.name}",
        )
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
            and self._current_animation == _active_idle_beat(self)
            and finished_animation is self._active_animation
        ):
            self._restore_idle_after_look(resume_ambient=True)
            return
        super()._finish_reaction(finished_animation)

    def _play_animation(self, name: str, after: str | None = None) -> None:
        if self._idle_look_active and name != _active_idle_beat(self):
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
        self._cancel_idle_look_timer()
        self._idle_look_active = False
        self._idle_beat_animation = None
        self._idle_look_resume_position = None
        super().shutdown_presence()
