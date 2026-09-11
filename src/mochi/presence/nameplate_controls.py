"""Wire the Nameplate into Buddy's existing update lifecycle.

No new timers are introduced. Position updates and temporary-feedback expiry
piggyback on hooks Mochi already calls every frame or on every meaningful
change:

- `_tick()` (already runs at TICK_MS ~60Hz for walking/animation/drag sampling)
- `_on_drag_update()` (already runs on every pointer drag delta)
- `_change_size()` (already runs when Mochi's size changes)
- `shutdown_presence()` (already runs on application shutdown)

This keeps the nameplate on Mochi's proven cadence instead of giving it an
independent movement or polling system.

The reusable surface has deterministic content priority:

    speech bubble > temporary feedback > persistent mood > name only

The speech bubble and nameplate remain mutually exclusive at the same anchor.
Temporary feedback lives on the nameplate itself, overrides the mood line for
a bounded amount of *visible* time, then restores the mood automatically. If
the speech bubble takes over, the feedback lifetime pauses so care feedback is
not silently consumed while hidden.
"""

from __future__ import annotations

import time

from .nameplate import Nameplate


class NameplateMixin:
    """Own Mochi's stable non-interactive UI surface above the sprite."""

    DEFAULT_FEEDBACK_SECONDS = 2.4

    def __init__(self, *args, **kwargs) -> None:
        self._nameplate: Nameplate | None = None
        self._nameplate_shown = False
        self._nameplate_name = "Mochi"
        self._nameplate_mood: str | None = None
        self._nameplate_feedback: str | None = None
        self._nameplate_feedback_remaining_seconds = 0.0
        self._nameplate_feedback_active_since: float | None = None
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        self._nameplate = Nameplate(
            owner=self._window,
            anchor_widget=self,
            logger=self._logger,
        )
        self._refresh_nameplate_content()

    @staticmethod
    def _normalize_nameplate_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def set_nameplate_name(self, name: str) -> None:
        """Set the persistent first line shown by the reusable surface."""
        self._nameplate_name = self._normalize_nameplate_text(name) or "Mochi"
        self._refresh_nameplate_content()

    def set_nameplate_mood(self, mood: str | None) -> None:
        """Set persistent mood/state text shown when no feedback overrides it."""
        self._nameplate_mood = self._normalize_nameplate_text(mood)
        self._refresh_nameplate_content()

    def clear_nameplate_mood(self) -> None:
        self.set_nameplate_mood(None)

    def show_nameplate_feedback(
        self,
        feedback: str,
        *,
        duration_seconds: float | None = None,
    ) -> None:
        """Temporarily override the mood line with short care feedback.

        The lifetime is counted only while the nameplate is allowed to own the
        shared surface. A speech bubble pauses the countdown and the feedback
        resumes once the bubble yields, so callers do not need to coordinate
        with presentation details.
        """
        text = self._normalize_nameplate_text(feedback)
        if text is None:
            self.clear_nameplate_feedback()
            return

        duration = (
            self.DEFAULT_FEEDBACK_SECONDS
            if duration_seconds is None
            else float(duration_seconds)
        )
        if duration <= 0:
            self.clear_nameplate_feedback()
            return

        self._nameplate_feedback = text
        self._nameplate_feedback_remaining_seconds = duration
        self._nameplate_feedback_active_since = None
        self._refresh_nameplate_content()

    def clear_nameplate_feedback(self) -> None:
        """Clear temporary feedback immediately and restore persistent mood."""
        self._nameplate_feedback = None
        self._nameplate_feedback_remaining_seconds = 0.0
        self._nameplate_feedback_active_since = None
        self._refresh_nameplate_content()

    def _refresh_nameplate_content(self) -> None:
        nameplate = self._nameplate
        if nameplate is None:
            return
        nameplate.set_name(self._nameplate_name)
        nameplate.set_status(self._nameplate_feedback or self._nameplate_mood)

    def _advance_nameplate_feedback_lifetime(self) -> None:
        """Advance temporary feedback using the existing tick, never a timer."""
        if self._nameplate_feedback is None:
            return

        bubble = getattr(self, "_presence_bubble", None)
        if bubble is not None and bubble.visible:
            # The speech bubble owns the shared surface. Pause the feedback
            # clock so temporary care text cannot expire unseen behind it.
            self._nameplate_feedback_active_since = None
            return

        now = time.monotonic()
        if self._nameplate_feedback_active_since is None:
            self._nameplate_feedback_active_since = now
            return

        elapsed = max(0.0, now - self._nameplate_feedback_active_since)
        self._nameplate_feedback_active_since = now
        self._nameplate_feedback_remaining_seconds = max(
            0.0,
            self._nameplate_feedback_remaining_seconds - elapsed,
        )
        if self._nameplate_feedback_remaining_seconds <= 0.0:
            self.clear_nameplate_feedback()

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
                self._advance_nameplate_feedback_lifetime()
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
        self._nameplate_feedback = None
        self._nameplate_feedback_remaining_seconds = 0.0
        self._nameplate_feedback_active_since = None
        super().shutdown_presence()
