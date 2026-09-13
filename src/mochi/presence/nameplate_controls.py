"""Wire Mochi's reusable nameplate/status UI into the existing Buddy lifecycle.

No dedicated timers are introduced. Position updates, temporary-feedback expiry,
and nameplate fade timing piggyback on hooks Mochi already calls every frame or
on every meaningful change:

- `_tick()` (already runs at TICK_MS ~60Hz for walking/animation/drag sampling)
- `_on_drag_update()` (already runs on every pointer drag delta)
- `_change_size()` (already runs when Mochi's size changes)
- `_on_enter()` / `_on_leave()` (existing Buddy hover events)
- `shutdown_presence()` (already runs on application shutdown)

The persistent surface stays intentionally quiet and gives screen space back
when it is not useful:

    speech bubble > temporary feedback > hovered name > short-lived name

Mood is still derived from successful Mochi state transitions through
`MoodModel`, but persistent state/mood cues are shown only inside the existing
right-click menu. The status block is non-interactive and reuses the same menu
window; it creates no second popover/window, focus grab, gesture, controller, or
polling loop.

Temporary care feedback may still briefly use the nameplate's second line. If
the speech bubble takes over, the feedback lifetime pauses so care feedback is
not silently consumed while hidden.
"""

from __future__ import annotations

import time

from gi.repository import Gtk

from mochi.mood import MoodModel
from mochi.state import MochiState

from .nameplate import Nameplate


class NameplateMixin:
    """Own Mochi's stable non-interactive UI surface above the sprite."""

    DEFAULT_FEEDBACK_SECONDS = 2.4
    NAMEPLATE_LINGER_SECONDS = 2.5
    NAMEPLATE_FADE_SECONDS = 0.35

    def __init__(self, *args, **kwargs) -> None:
        self._nameplate: Nameplate | None = None
        self._nameplate_shown = False
        self._nameplate_hide_at: float | None = None
        self._mood_model = MoodModel()
        self._nameplate_name = "Mochi"
        self._nameplate_mood: str | None = self._mood_model.label
        self._nameplate_feedback: str | None = None
        self._nameplate_feedback_remaining_seconds = 0.0
        self._nameplate_feedback_active_since: float | None = None
        self._context_state_value: Gtk.Label | None = None
        self._context_mood_value: Gtk.Label | None = None
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        # State normally starts at IDLE, but synchronize from the actual state
        # after the Buddy core has initialized so alternate startup paths remain
        # correct without special-casing them here.
        startup_mood = self._mood_model.observe_state(self.state.current)
        self._nameplate_mood = (
            startup_mood.value if startup_mood is not None else self._mood_model.label
        )
        self._nameplate = Nameplate(
            owner=self._window,
            anchor_widget=self,
            logger=self._logger,
        )
        self._refresh_nameplate_content()
        self._refresh_context_status()

    @staticmethod
    def _normalize_nameplate_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _build_context_menu(self):
        """Extend Buddy's existing user menu with a passive status snapshot.

        This intentionally does not create another popup surface. Reusing the
        existing MenuWindow avoids the historical focus/grab contention that
        made earlier status/nameplate experiments interfere with right-click.
        """
        popover = super()._build_context_menu()

        status_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        status_block.set_can_target(False)

        title = Gtk.Label(label="Mochi status")
        title.set_xalign(0)
        title.set_can_target(False)
        title.add_css_class("mochi-menu-section")
        status_block.append(title)

        state_row, self._context_state_value = self._make_context_status_row(
            "MochiState"
        )
        status_block.append(state_row)
        mood_row, self._context_mood_value = self._make_context_status_row("Mood")
        status_block.append(mood_row)

        self._register_context_menu_row(
            "status",
            status_block,
            before="sleep",
            animated=False,
        )

        self._refresh_context_status()
        return popover

    @staticmethod
    def _make_context_status_row(label: str) -> tuple[Gtk.Box, Gtk.Label]:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("mochi-setting-row")
        row.set_can_target(False)

        key = Gtk.Label(label=label)
        key.set_xalign(0)
        key.set_hexpand(True)
        key.set_can_target(False)
        row.append(key)

        value = Gtk.Label(label="—")
        value.set_xalign(1)
        value.set_can_target(False)
        value.add_css_class("mochi-menu-value")
        row.append(value)
        return row, value

    def _refresh_context_status(self) -> None:
        """Refresh the read-only state/mood snapshot displayed by right-click."""
        state = getattr(getattr(self, "state", None), "current", None)
        state_text = state.name if isinstance(state, MochiState) else "UNKNOWN"
        mood_text = self._nameplate_mood or "—"

        if self._context_state_value is not None:
            self._context_state_value.set_text(state_text)
        if self._context_mood_value is not None:
            self._context_mood_value.set_text(mood_text)

    def _show_context_menu(self, *args) -> None:
        """Refresh status once per open, then preserve Buddy's proven menu path."""
        context_menu = getattr(self, "_context_menu", None)
        if context_menu is None or not context_menu.get_visible():
            self._refresh_context_status()
        super()._show_context_menu(*args)

    def set_nameplate_name(self, name: str) -> None:
        """Set the persistent first line shown by the reusable surface."""
        self._nameplate_name = self._normalize_nameplate_text(name) or "Mochi"
        self._refresh_nameplate_content()

    def set_nameplate_mood(self, mood: str | None) -> None:
        """Update Mochi's tracked mood without making it always-visible.

        Normal runtime mood is owned by `MoodModel` and synchronizes on accepted
        MochiState transitions. The current value is surfaced when the user
        opens the right-click menu rather than living permanently below Mochi's
        name tag.
        """
        self._nameplate_mood = self._normalize_nameplate_text(mood)

    def clear_nameplate_mood(self) -> None:
        self.set_nameplate_mood(None)

    def show_nameplate_feedback(
        self,
        feedback: str,
        *,
        duration_seconds: float | None = None,
    ) -> None:
        """Temporarily show short care feedback below Mochi's name.

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
        # Feedback is intentional UI, so it gets a fresh visible window even if
        # the ordinary name-only plate had already faded away.
        self._nameplate_hide_at = None
        self._refresh_nameplate_content()

    def clear_nameplate_feedback(self) -> None:
        """Clear temporary feedback and return the nameplate to name-only."""
        self._nameplate_feedback = None
        self._nameplate_feedback_remaining_seconds = 0.0
        self._nameplate_feedback_active_since = None
        # Start a fresh linger period on the next visibility sync instead of
        # immediately disappearing at the end of useful feedback.
        self._nameplate_hide_at = None
        self._refresh_nameplate_content()

    def _refresh_nameplate_content(self) -> None:
        nameplate = self._nameplate
        if nameplate is None:
            return
        nameplate.set_name(self._nameplate_name)
        # Persistent state/mood belongs in the right-click menu. The second
        # line is reserved for short-lived care/interaction feedback only.
        nameplate.set_status(self._nameplate_feedback)

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

    def _transition_to(self, next_state: MochiState) -> bool:
        """Update mood only after the core state machine accepts a transition."""
        transitioned = super()._transition_to(next_state)
        if not transitioned:
            return False

        mood = self._mood_model.observe_state(next_state)
        if mood is not None:
            # The behavior state remains the source of truth. The menu samples
            # this tracked mood the next time it opens; no live menu polling is
            # necessary while the popup is on screen.
            self.set_nameplate_mood(mood.value)
        return True

    def _tick(self) -> bool:
        result = super()._tick()
        if self._nameplate is not None:
            if not self._nameplate_shown and self.get_root() is not None:
                # Defer the first presentation until Mochi's widget is actually
                # attached to a realized toplevel (after `window.set_child()` /
                # `window.present()` in app.py). Showing any child surface
                # earlier crashes GTK with "widget isn't inside a toplevel".
                self._nameplate_shown = True
                self._nameplate_hide_at = None
            if self._nameplate_shown:
                self._advance_nameplate_feedback_lifetime()
                self._sync_nameplate_with_speech()
        return result

    def _sync_nameplate_with_speech(self) -> None:
        """Arbitrate speech, feedback, hover, and nameplate auto-hide.

        The plate stays purely visual. Hover state comes from Buddy's existing
        motion controller; no controller is ever attached to the nameplate
        itself. Speech remains highest priority, temporary feedback and hover
        force a full-opacity reveal, and the idle name fades out after a short
        linger period to preserve desktop space.
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

        hovered = bool(getattr(self, "_hovered", False))
        feedback_visible = bool(getattr(self, "_nameplate_feedback", None))
        if hovered or feedback_visible:
            self._nameplate_hide_at = None
            nameplate.set_opacity(1.0)
            if not nameplate.visible:
                nameplate.show()
            else:
                nameplate.update_position()
            return

        now = time.monotonic()
        hide_at = getattr(self, "_nameplate_hide_at", None)
        if hide_at is None:
            hide_at = now + self.NAMEPLATE_LINGER_SECONDS
            self._nameplate_hide_at = hide_at

        if now < hide_at:
            opacity = 1.0
        else:
            fade_seconds = max(0.0, float(self.NAMEPLATE_FADE_SECONDS))
            elapsed = now - hide_at
            if fade_seconds <= 0.0 or elapsed >= fade_seconds:
                if nameplate.visible:
                    nameplate.hide()
                return
            opacity = max(0.0, min(1.0, 1.0 - elapsed / fade_seconds))

        nameplate.set_opacity(opacity)
        if not nameplate.visible:
            nameplate.show()
        else:
            nameplate.update_position()

    def _on_enter(self, controller, x: float, y: float) -> None:
        """Reveal the nameplate whenever the pointer returns to Mochi."""
        super()._on_enter(controller, x, y)
        self._nameplate_hide_at = None
        if self._nameplate_shown:
            self._sync_nameplate_with_speech()

    def _on_leave(self, controller) -> None:
        """Restart the short linger window after the pointer leaves Mochi."""
        super()._on_leave(controller)
        self._nameplate_hide_at = None
        if self._nameplate_shown:
            self._sync_nameplate_with_speech()

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
        self._nameplate_hide_at = None
        self._nameplate_feedback = None
        self._nameplate_feedback_remaining_seconds = 0.0
        self._nameplate_feedback_active_since = None
        super().shutdown_presence()
