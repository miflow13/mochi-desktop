"""X11/XWayland-specific buddy interaction behavior."""

from __future__ import annotations

import time

from mochi.buddy import Buddy
from mochi.state import MochiState


class X11Buddy(Buddy):
    """Buddy variant whose drag is moved directly through X11.

    Gdk.Toplevel.begin_move() delegates the interaction to Mutter. Once Mutter
    owns that move, application-side XMoveWindow corrections can be visually
    ignored until the compositor catches up. For Mochi's hard desktop walls we
    instead keep ownership: read the root pointer, calculate the requested
    top-left, clamp it, and move the X11 window ourselves.
    """

    DRAG_SPEECH_COOLDOWN_SECONDS = 30.0
    DRAG_SPEECH_DURATION_SECONDS = 2.5

    def _on_motion(self, _controller, _x: float, _y: float) -> None:
        # Do not call Gdk.Toplevel.begin_move(). Gtk.GestureDrag still owns the
        # button sequence and _on_drag_update starts the normal pickup state.
        return

    def _on_drag_update(
        self, gesture, offset_x: float, offset_y: float
    ) -> None:
        # Reuse all normal pickup/state/animation behavior. On X11 the base
        # implementation intentionally does not move the window from offsets.
        was_drag_started = self._drag_started
        super()._on_drag_update(gesture, offset_x, offset_y)
        if not was_drag_started and self._drag_started:
            self._maybe_show_drag_speech()
        self._move_with_x11_pointer()

    def _maybe_show_drag_speech(self) -> None:
        """Show the playful drag line through the ambient branch's bubble system.

        Existing dialogue wins: if Mochi is already speaking (or visibly typing
        a pending line), keep that bubble alive and let the drag-following path
        carry it with him. `wheee!` is only used when the drag starts in silence.
        """
        bubble = getattr(self, "_presence_bubble", None)
        if bubble is None:
            return

        engine = getattr(self, "_ambient_presence_engine", None)
        if engine is not None:
            tuning = engine.tuning
            if not tuning.speech_enabled or tuning.quiet_mode:
                return

        if bubble.visible:
            logger = getattr(self, "_logger", None)
            if logger is not None:
                logger.debug("Drag dialogue skipped: existing bubble preserved")
            return

        now = time.monotonic()
        last_spoken_at = getattr(self, "_last_drag_speech_at", float("-inf"))
        if now - last_spoken_at < self.DRAG_SPEECH_COOLDOWN_SECONDS:
            return

        if bubble.show("wheee!", duration_seconds=self.DRAG_SPEECH_DURATION_SECONDS):
            self._last_drag_speech_at = now
            logger = getattr(self, "_logger", None)
            if logger is not None:
                logger.debug("Drag dialogue: wheee!")

    def _sample_x11_drag(self, render: bool = True) -> None:
        """Drive drag visuals from the pointer-owned target, not X11 readback.

        ``_move_with_x11_pointer`` updates ``WindowPlacement.position`` from the
        root pointer before every drag tick. Reading the X11 window position back
        immediately afterwards adds an avoidable compositor/server round trip and
        can leave the visual pose one or more samples behind a direction reversal.
        The target position is already the authoritative motion input while held,
        so use it directly for velocity and pose selection.
        """
        position = self._placement.position
        timestamp = time.monotonic()
        previous_position = self._drag_sample_position
        previous_time = self._drag_sample_time

        if previous_position is None or previous_time is None:
            self._drag_motion.begin(position.x, position.y, timestamp)
            elapsed = 0.0
        else:
            elapsed = timestamp - previous_time
            self._drag_motion.update(position.x, position.y, timestamp)

        self._drag_sample_position = (position.x, position.y)
        self._drag_sample_time = timestamp
        self._last_drag_update_time = timestamp

        if render:
            self._play_drag_pose()

        frame = self.player.frame
        self._logger.debug(
            "X11 drag target=(%d,%d) dt=%.3f filtered_velocity_x=%.1f intensity=%.3f frame_index=%d sprite=%s",
            position.x,
            position.y,
            elapsed,
            self._drag_motion.filtered_velocity_x,
            self._drag_motion.horizontal_intensity,
            self._drag_frame_index,
            frame.sprite if frame is not None else "none",
        )

    def _tick(self) -> bool:
        # Keep the window attached to the root pointer at Mochi's normal 60-ish
        # Hz tick rate as well as on gesture updates. This avoids event-coalescing
        # gaps and makes the edge stop feel solid rather than springy.
        self._move_with_x11_pointer()
        return super()._tick()

    def _move_with_x11_pointer(self) -> None:
        if (
            not self._drag_started
            or self._press is None
            or self.state.current not in (MochiState.PICKUP, MochiState.DRAGGED)
        ):
            return
        press_x, press_y = self._press
        self._placement.drag_to_pointer(press_x, press_y)
        self._update_pot_hide_target()

        # Bubble positioning uses the buddy window as its anchor. Resync it in
        # the same drag tick instead of waiting for the fallback follow timer so
        # dialogue feels physically attached to Mochi during fast pointer moves.
        bubble = getattr(self, "_presence_bubble", None)
        if bubble is not None and getattr(bubble, "visible", False):
            follow_now = getattr(bubble, "follow_owner_now", None)
            if callable(follow_now):
                follow_now()
