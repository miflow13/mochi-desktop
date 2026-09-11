"""User-facing movement controls layered onto Mochi's existing presence stack."""

from __future__ import annotations

import random

from gi.repository import Gtk

from mochi.behavior import choose_walk_animation
from mochi.edge_roam import build_edge_roam_motion
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class EdgeRoamMixin:
    """Keep autonomous wandering on the current monitor's safe perimeter."""

    def __init__(self, *args, **kwargs) -> None:
        self._edge_roam = False
        self._edge_roam_switch: Gtk.Switch | None = None
        self._edge_roam_clockwise = random.choice((True, False))
        super().__init__(*args, **kwargs)

    def _build_context_menu(self):
        popover = super()._build_context_menu()
        self._edge_roam = self._config.load_edge_roam()

        edge_row, self._edge_roam_switch = self._make_edge_roam_row()
        card = self._context_menu_content
        # PresenceBuddyMixin already places Stay put immediately after Sleep.
        # Insert Edge roam first so the movement controls read naturally:
        # Sleep -> Edge roam -> Stay put -> Close.
        card.insert_child_after(edge_row, self._sleep_button)

        existing_rows = list(self._context_menu_animated_rows)
        if existing_rows:
            self._context_menu_animated_rows = (
                existing_rows[0],
                edge_row,
                *existing_rows[1:],
            )
        else:
            self._context_menu_animated_rows = (edge_row,)

        popover._preferred_height = max(popover._preferred_height, 268)
        popover.window.set_default_size(popover._preferred_width, popover._preferred_height)
        return popover

    def _make_edge_roam_row(self) -> tuple[Gtk.Button, Gtk.Switch]:
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        button.set_tooltip_text("Keep Mochi's autonomous wandering along the screen edge")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("view-fullscreen-symbolic")
        icon.add_css_class("mochi-menu-icon")
        row.append(icon)

        text = Gtk.Label(label="Edge roam")
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)

        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_active(self._edge_roam)
        # Keep the whole row as one reliable target, matching Stay put.
        switch.set_can_target(False)
        switch.set_focusable(False)
        row.append(switch)

        button.set_child(row)
        button.connect("clicked", self._toggle_edge_roam)
        return button, switch

    def _toggle_edge_roam(self, _button: Gtk.Button) -> None:
        self._edge_roam = not self._edge_roam
        self._config.save_edge_roam(self._edge_roam)
        if self._edge_roam_switch is not None:
            self._edge_roam_switch.set_active(self._edge_roam)

        if self._edge_roam:
            # Choose one direction per activation so Mochi feels like he is
            # patrolling the perimeter instead of jittering back and forth.
            self._edge_roam_clockwise = random.choice((True, False))
            if self.state.current is MochiState.WALKING:
                self._cancel_walk()
                if self._transition_to(MochiState.IDLE):
                    self._play_animation("idle")

        self._logger.info(
            "Edge roam %s%s",
            "enabled" if self._edge_roam else "disabled",
            " (Stay put currently overrides wandering)"
            if self._edge_roam and getattr(self, "_stay_put", False)
            else "",
        )

    def _start_walk(self) -> None:
        # Autonomous walk timers can already be queued when a menu opens. Guard
        # at the final movement entry point too so Mochi stays still while the
        # user is interacting with either the context menu or Mochi Lab.
        if self._context_menu_open:
            self._logger.debug("Edge roam walk suppressed: menu open")
            return

        if not self._edge_roam:
            super()._start_walk()
            return

        origin = self._placement.sync_from_window()
        cycle_duration_ms = (
            len(ANIMATIONS["walk"].frames)
            * ANIMATIONS["walk"].frame_duration_ms
        )
        motion = build_edge_roam_motion(
            self._placement,
            origin,
            travel_distance=random.randint(80, 240),
            clockwise=self._edge_roam_clockwise,
            cycle_duration_ms=cycle_duration_ms,
            speed_px_per_second=self.WALK_SPEED_PX_PER_SECOND,
        )
        if motion is None or motion.distance <= 1.0:
            return

        self._walk_motion = motion
        self._walk_elapsed_ms = 0
        if not self._transition_to(MochiState.WALKING):
            self._walk_motion = None
            return
        self._play_animation(choose_walk_animation(motion.origin, motion.target))
        self._logger.debug(
            "Edge roam walk origin=%s target=%s perimeter=%s",
            motion.origin,
            motion.target,
            type(motion).__name__,
        )
