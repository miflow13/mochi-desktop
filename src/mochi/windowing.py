"""Optional Wayland layer-shell integration kept out of the GTK application."""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

try:
    gi.require_version("GdkWayland", "4.0")
    from gi.repository import GdkWayland  # type: ignore[attr-defined]  # noqa: E402
except (ImportError, ValueError):
    GdkWayland = None

from mochi.config import Position
from mochi.x11 import get_window_position, move_window

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell  # type: ignore[attr-defined]  # noqa: E402
except (ImportError, ValueError):
    Gtk4LayerShell = None


class WindowPlacement:
    """Controls a layer surface, or reports that GTK must use its fallback."""

    DEFAULT_POSITION = Position(48, 48)

    # Small safety margin so Mochi can get close to screen edges without clipping.
    EDGE_PADDING_PX = 8
    BOTTOM_PADDING_PX = 12

    def __init__(self, window: Gtk.Window, saved_position: Position | None) -> None:
        self.window = window
        self.position = saved_position or self.DEFAULT_POSITION
        self._logger = logging.getLogger(__name__)
        self.layer_shell_enabled = self._enable_layer_shell()

    def _enable_layer_shell(self) -> bool:
        display = self.window.get_display()
        if GdkWayland is None or not isinstance(display, GdkWayland.WaylandDisplay):
            self._logger.info("Using the X11/XWayland GTK window path")
            return False
        if Gtk4LayerShell is None:
            self._logger.info(
                "gtk4-layer-shell is not installed; using compositor-managed GTK window"
            )
            return False
        if not Gtk4LayerShell.is_supported():
            self._logger.info(
                "The compositor does not support layer shell; using the GTK fallback"
            )
            return False

        Gtk4LayerShell.init_for_window(self.window)
        Gtk4LayerShell.set_namespace(self.window, "mochi")
        Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.TOP)
        Gtk4LayerShell.set_keyboard_mode(
            self.window, Gtk4LayerShell.KeyboardMode.NONE
        )
        Gtk4LayerShell.set_exclusive_zone(self.window, -1)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, True)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.BOTTOM, True)
        self.move_to(self.position.x, self.position.y)
        self._logger.info("Using gtk4-layer-shell Wayland overlay")
        return True

    def move_to(self, x: int, y: int) -> Position:
        self.position = self.clamp_position(x, y)
        x, y = self.position.x, self.position.y
        if getattr(self, "layer_shell_enabled", False) and Gtk4LayerShell is not None:
            Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.LEFT, x)
            Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.BOTTOM, y)
        else:
            move_window(self.window, x, y)
        return self.position

    def clamp_position(self, x: int, y: int) -> Position:
        monitor = self._monitor_for_position(x, y)
        edge_padding = self.EDGE_PADDING_PX
        bottom_padding = self.BOTTOM_PADDING_PX

        if monitor is None:
            return Position(
                max(edge_padding, round(x)),
                max(bottom_padding, round(y)),
            )

        geometry = monitor.get_geometry()
        width, height = self.window.get_default_size()

        min_x = geometry.x + edge_padding
        max_x = geometry.x + max(
            edge_padding,
            geometry.width - width - edge_padding,
        )

        if self.layer_shell_enabled:
            # Layer-shell Y is measured upward from the bottom edge.
            min_y = bottom_padding
            max_y = max(
                bottom_padding,
                geometry.height - height - edge_padding,
            )
        else:
            # X11/XWayland Y is a normal top-left screen coordinate.
            min_y = geometry.y + edge_padding
            max_y = geometry.y + max(
                edge_padding,
                geometry.height - height - bottom_padding,
            )

        return Position(
            max(min_x, min(round(x), max_x)),
            max(min_y, min(round(y), max_y)),
        )

    def restore(self) -> None:
        self.move_to(self.position.x, self.position.y)

    def sync_from_window(self) -> Position:
        coordinates = get_window_position(self.window)
        if coordinates is None:
            return self.position

        clamped = self.clamp_position(*coordinates)
        self.position = clamped

        # XWayland native drags are compositor-owned, so move_to() is bypassed
        # while the pointer is actively moving the window. Re-apply only the
        # out-of-bounds correction here. Buddy samples the native drag every
        # frame, which makes the monitor edge behave like an invisible wall.
        if coordinates != (clamped.x, clamped.y):
            move_window(self.window, clamped.x, clamped.y)

        return self.position

    def _monitor_for_position(self, x: int, y: int) -> Gdk.Monitor | None:
        if self.layer_shell_enabled and Gtk4LayerShell is not None:
            monitor = Gtk4LayerShell.get_monitor(self.window)
            if monitor is not None:
                return monitor
        display = self.window.get_display()
        monitors = display.get_monitors()
        if not monitors.get_n_items():
            return None

        width, height = self.window.get_default_size()
        center_x = x + width / 2
        center_y = y + height / 2
        nearest: tuple[float, Gdk.Monitor] | None = None
        for index in range(monitors.get_n_items()):
            monitor = monitors.get_item(index)
            geometry = monitor.get_geometry()
            if (
                geometry.x <= center_x < geometry.x + geometry.width
                and geometry.y <= center_y < geometry.y + geometry.height
            ):
                return monitor
            nearest_x = max(geometry.x, min(center_x, geometry.x + geometry.width))
            nearest_y = max(geometry.y, min(center_y, geometry.y + geometry.height))
            distance = (center_x - nearest_x) ** 2 + (center_y - nearest_y) ** 2
            if nearest is None or distance < nearest[0]:
                nearest = (distance, monitor)
        return nearest[1] if nearest is not None else None
