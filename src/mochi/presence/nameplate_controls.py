"""Wire the Nameplate into Buddy's existing update lifecycle.

No new timers are introduced. Position updates piggyback on hooks Mochi
already calls every frame or on every meaningful change:

- `_tick()` (already runs at TICK_MS ~60Hz for walking/animation/drag sampling)
- `_on_drag_update()` (already runs on every pointer drag delta)
- `_change_size()` (already runs when Mochi's size changes)
- `shutdown_presence()` (already runs on application shutdown)

This keeps the nameplate's position update on Mochi's proven cadence instead
of an independent movement/polling system.

The nameplate and the Mochi Sense speech bubble share the same anchor point
above Mochi's sprite, so they are mutually exclusive: whenever the speech
bubble has something to say, it replaces the nameplate; once the bubble
finishes (or is dismissed), the nameplate reappears. This is synced from the
same `_tick()` pass rather than a dedicated timer/signal.
"""

from __future__ import annotations

from .nameplate import Nameplate


class NameplateMixin:
    """Show and keep Mochi's nameplate positioned without touching input."""

    def __init__(self, *args, **kwargs) -> None:
        self._nameplate: Nameplate | None = None
        self._nameplate_shown = False
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        self._nameplate = Nameplate(
            owner=self._window,
            anchor_widget=self,
            logger=self._logger,
        )

    def _tick(self) -> bool:
        result = super()._tick()
        if self._nameplate is not None:
            if not self._nameplate_shown and self.get_root() is not None:
                # Defer the first presentation until Mochi's widget is actually
                # attached to a realized toplevel (after `window.set_child()` /
                # `window.present()` in app.py). Showing any child surface
                # earlier crashes GTK with "widget isn't inside a toplevel".
                self._nameplate_shown = True
            if self._nameplate_shown:
                self._sync_nameplate_with_speech()
        return result

    def _sync_nameplate_with_speech(self) -> None:
        """Keep the nameplate and speech bubble mutually exclusive.

        They occupy the same anchor point above Mochi, so only one is ever
        shown at a time: the speech bubble takes priority while it has
        something to say, and the nameplate returns as soon as the bubble
        hides. Checked every tick instead of via a dedicated timer/callback.
        """
        nameplate = self._nameplate
        if nameplate is None:
            return
        bubble = getattr(self, "_presence_bubble", None)
        bubble_visible = bool(bubble is not None and bubble.visible)
        if bubble_visible:
            if nameplate.visible:
                nameplate.hide()
            return
        if not nameplate.visible:
            nameplate.show()
        else:
            nameplate.update_position()

    def _on_drag_update(self, gesture, offset_x: float, offset_y: float) -> None:
        super()._on_drag_update(gesture, offset_x, offset_y)
        if self._nameplate is not None and self._nameplate.visible:
            self._nameplate.update_position()

    def _change_size(self, scale) -> None:
        super()._change_size(scale)
        if self._nameplate is not None and self._nameplate.visible:
            self._nameplate.update_position()

    def shutdown_presence(self) -> None:
        if self._nameplate is not None:
            self._nameplate.destroy()
            self._nameplate = None
        super().shutdown_presence()
