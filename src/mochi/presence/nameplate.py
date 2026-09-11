"""Non-interactive nameplate anchored above Mochi.

Modeled directly on the proven `SpeechBubble` presentation strategy in
`bubble.py`: a non-focusable, non-targetable surface (an X11/XWayland
transient window, or a Wayland `Gtk.Popover`) that is *purely visual* and
never participates in input handling. Mochi's own gestures/controllers
remain the single source of truth for clicks, drags, and the context menu.

A previous status-overlay experiment (`Gtk.Popover` with its own click/hover/
key controllers, focus grabs, and autohide) fought with Mochi's context menu
popover for input/focus grabs and caused freezes. This module intentionally
carries none of that: no gestures, no focus, no autohide, no keyboard
handling -- just position + text.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from mochi.x11 import get_window_position, move_window


class Nameplate:
    """Show Mochi's name (and later, short status text) above his sprite.

    Positioning follows the same pipeline everywhere in this codebase:

        Mochi position -> sprite dimensions/scale -> anchor point -> nameplate position

    `update_position()` is cheap and side-effect free when hidden, so it is
    safe to call from Mochi's existing per-tick/drag update paths without
    introducing a dedicated polling timer for the nameplate itself.
    """

    GAP_PX = 6
    MONITOR_PADDING_PX = 10

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        anchor_widget: Gtk.Widget,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._anchor = anchor_widget
        self._logger = logger or logging.getLogger(__name__)
        self._name = "Mochi"
        self._status: str | None = None
        self._mode: str | None = None

        self._label = self._make_label()
        self._content = self._make_content(self._label)

        # X11/XWayland path: a small, undecorated transient toplevel moved in
        # root coordinates -- the same strategy SpeechBubble/menus use, which
        # is already proven not to interfere with Mochi's own window.
        self._window = Gtk.Window()
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_modal(False)
        self._window.set_focusable(False)
        self._window.set_can_focus(False)
        self._window.set_hide_on_close(True)
        self._window.set_transient_for(owner)
        self._window.add_css_class("mochi-nameplate-window")
        self._window.set_child(self._content)

        # Wayland path: a non-autohiding, non-targetable Popover anchored to
        # the Buddy widget. `set_can_target(False)` is the key input-safety
        # property -- it makes the popover invisible to pointer hit-testing,
        # so it can never steal clicks, drags, hover, or the context menu.
        self._popover_label = self._make_label()
        self._popover_content = self._make_content(self._popover_label)
        self._popover = Gtk.Popover()
        self._popover.set_parent(anchor_widget)
        self._popover.set_autohide(False)
        self._popover.set_has_arrow(False)
        self._popover.set_position(Gtk.PositionType.TOP)
        self._popover.set_offset(0, -self.GAP_PX)
        self._popover.set_focusable(False)
        self._popover.set_can_focus(False)
        self._popover.set_can_target(False)
        self._popover.add_css_class("mochi-nameplate-popover")
        self._popover.set_child(self._popover_content)

        self._install_css(owner.get_display())
        self._refresh_label_text()

    @staticmethod
    def _make_label() -> Gtk.Label:
        label = Gtk.Label()
        label.set_justify(Gtk.Justification.CENTER)
        label.set_focusable(False)
        label.set_can_focus(False)
        label.set_can_target(False)
        label.add_css_class("mochi-nameplate-text")
        return label

    @staticmethod
    def _make_content(label: Gtk.Label) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        box.add_css_class("mochi-nameplate-shell")
        box.set_focusable(False)
        box.set_can_focus(False)
        box.set_can_target(False)
        box.set_halign(Gtk.Align.CENTER)
        box.append(label)
        return box

    @property
    def visible(self) -> bool:
        return bool(self._window.get_visible() or self._popover.get_visible())

    def show(self) -> None:
        """Present the nameplate using whichever mode is currently viable."""
        if get_window_position(self._owner) is not None:
            self._mode = "x11"
            if self._popover.get_visible():
                self._popover.popdown()
            self._window.set_visible(True)
            self.update_position()
        else:
            self._mode = "wayland"
            if self._window.get_visible():
                self._window.hide()
            self.update_position()
            if not self._popover.get_visible():
                self._popover.popup()

    def hide(self) -> None:
        if self._window.get_visible():
            self._window.hide()
        if self._popover.get_visible():
            self._popover.popdown()
        self._mode = None

    def set_name(self, name: str) -> None:
        self._name = name.strip() or "Mochi"
        self._refresh_label_text()

    def set_status(self, status: str | None) -> None:
        self._status = status.strip() if status else None
        self._refresh_label_text()

    def clear_status(self) -> None:
        self.set_status(None)

    def _refresh_label_text(self) -> None:
        text = self._name if not self._status else f"{self._name}\n{self._status}"
        self._label.set_text(text)
        self._popover_label.set_text(text)
        if self.visible:
            self.update_position()

    def update_position(self) -> None:
        """Resync the nameplate to Mochi's current position, size, and monitor.

        Cheap and safe to call every tick/drag-update; it is a no-op unless
        the nameplate is currently shown, and it never touches Mochi's own
        window, state, or input handling.
        """
        if not self.visible:
            return
        if self._mode == "x11":
            self._position_x11()
        elif self._mode == "wayland":
            self._position_wayland_anchor()

    def destroy(self) -> None:
        self.hide()
        self._window.destroy()
        self._popover.unparent()

    def _visible_anchor_bounds(
        self, owner_width: int, owner_height: int
    ) -> tuple[float, float, float, float]:
        """Return visible Mochi bounds, falling back to the full Buddy widget.

        Reuses the same sprite-aware bounds lookup as SpeechBubble so the
        nameplate sits just above the drawn character rather than above the
        transparent authoring canvas padding.
        """
        atlas = getattr(self._anchor, "atlas", None)
        player = getattr(self._anchor, "player", None)
        frame = getattr(player, "frame", None)
        if atlas is not None and frame is not None and hasattr(atlas, "visible_bounds"):
            try:
                return atlas.visible_bounds(frame, owner_width, owner_height)
            except Exception as exc:
                self._logger.debug(
                    "Nameplate visible-bounds lookup failed; using widget bounds: %s",
                    exc,
                )
        return (0.0, 0.0, float(owner_width), float(owner_height))

    @staticmethod
    def _x11_coordinate_scale(window: Gtk.Window) -> float:
        surface = window.get_surface()
        if surface is None:
            return 1.0

        get_scale = getattr(surface, "get_scale", None)
        if callable(get_scale):
            try:
                scale = float(get_scale())
            except (TypeError, ValueError):
                scale = 1.0
            if scale > 0:
                return scale

        get_scale_factor = getattr(surface, "get_scale_factor", None)
        if callable(get_scale_factor):
            try:
                scale = float(get_scale_factor())
            except (TypeError, ValueError):
                scale = 1.0
            if scale > 0:
                return scale

        return 1.0

    def _position_wayland_anchor(self) -> None:
        width = max(1, self._anchor.get_width())
        height = max(1, self._anchor.get_height())
        visible_x, visible_y, visible_width, _visible_height = self._visible_anchor_bounds(
            width, height
        )
        rectangle = Gdk.Rectangle()
        rectangle.x = round(visible_x + visible_width / 2)
        rectangle.y = round(visible_y)
        rectangle.width = 1
        rectangle.height = 1
        self._popover.set_pointing_to(rectangle)

    def _position_x11(self) -> None:
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            self._logger.debug("Nameplate X11 position unavailable; hiding")
            self.hide()
            return

        owner_x, owner_y = owner_position
        owner_width = max(1, self._owner.get_width())
        owner_height = max(1, self._owner.get_height())
        width = self._window.get_width()
        height = self._window.get_height()
        if width <= 1:
            width = 96
        if height <= 1:
            height = 24

        owner_scale = self._x11_coordinate_scale(self._owner)
        plate_scale = self._x11_coordinate_scale(self._window)
        visible_x, visible_y, visible_width, _visible_height = self._visible_anchor_bounds(
            owner_width, owner_height
        )

        # owner_x/owner_y come from X11 in device pixels; convert every GTK
        # allocation-derived value into that same coordinate space before any
        # anchor, monitor-clamp, or move calculation (matches SpeechBubble).
        visible_x *= owner_scale
        visible_y *= owner_scale
        visible_width *= owner_scale
        plate_width = width * plate_scale
        plate_height = height * plate_scale
        gap = self.GAP_PX * owner_scale
        monitor_padding = self.MONITOR_PADDING_PX * owner_scale

        center_x = owner_x + visible_x + visible_width / 2
        visible_top = owner_y + visible_y

        display = self._owner.get_display()
        monitors = display.get_monitors()
        geometries = [
            monitors.get_item(index).get_geometry()
            for index in range(monitors.get_n_items())
        ]
        if geometries:
            # GDK monitor geometry is in application pixels; scale to X11
            # coordinates first, so this stays correct for negative-origin
            # secondary monitors and mixed-scale setups.
            scaled_geometries = [
                (
                    geometry.x * owner_scale,
                    geometry.y * owner_scale,
                    geometry.width * owner_scale,
                    geometry.height * owner_scale,
                )
                for geometry in geometries
            ]
            monitor_x, monitor_y, monitor_width, monitor_height = min(
                scaled_geometries,
                key=lambda geometry: (
                    max(geometry[0], min(center_x, geometry[0] + geometry[2]))
                    - center_x
                )
                ** 2
                + (
                    max(geometry[1], min(visible_top, geometry[1] + geometry[3]))
                    - visible_top
                )
                ** 2,
            )
            left = monitor_x + monitor_padding
            top = monitor_y + monitor_padding
            right = monitor_x + monitor_width - monitor_padding
        else:
            left, top = 0.0, 0.0
            right = owner_x + owner_width * owner_scale + plate_width

        x = round(center_x - plate_width / 2)
        y = round(visible_top - plate_height - gap)
        x = max(round(left), min(x, max(round(left), round(right - plate_width))))
        y = max(round(top), y)
        move_window(self._window, x, y)

    @staticmethod
    def _install_css(display: Gdk.Display) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(
            """
            window.mochi-nameplate-window {
                background: transparent;
            }
            .mochi-nameplate-shell {
                background: alpha(black, 0.42);
                border-radius: 999px;
                padding: 2px 9px;
            }
            .mochi-nameplate-text {
                color: white;
                font-size: 11px;
                font-weight: 700;
            }
            popover.mochi-nameplate-popover > contents {
                background: transparent;
                border: none;
                box-shadow: none;
                padding: 0;
            }
            popover.mochi-nameplate-popover > arrow {
                background: transparent;
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
