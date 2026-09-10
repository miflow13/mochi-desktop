"""X11/XWayland-specific buddy interaction behavior."""

from __future__ import annotations

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

    def _on_motion(self, _controller, _x: float, _y: float) -> None:
        # Do not call Gdk.Toplevel.begin_move(). Gtk.GestureDrag still owns the
        # button sequence and _on_drag_update starts the normal pickup state.
        return

    def _on_drag_update(
        self, gesture, offset_x: float, offset_y: float
    ) -> None:
        # Reuse all normal pickup/state/animation behavior. On X11 the base
        # implementation intentionally does not move the window from offsets.
        super()._on_drag_update(gesture, offset_x, offset_y)
        self._move_with_x11_pointer()

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
