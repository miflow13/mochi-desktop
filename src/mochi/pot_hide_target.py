"""Temporary drag-only pot target used to tuck Mochi out of the way."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.windowing import WindowPlacement
from mochi.x11 import get_pointer_position, get_window_position, move_window, request_keep_above

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell  # type: ignore[attr-defined]  # noqa: E402
except (ImportError, ValueError):
    Gtk4LayerShell = None


class PotHideTarget:
    """Small, non-interactive corner target that exists only during a drag."""

    WINDOW_SIZE = 80
    ART_SIZE = 64
    CORNER_MARGIN_PX = 12
    HIT_PADDING_PX = 12
    RESTING_OPACITY = 0.58
    HOVER_OPACITY = 1.0

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        placement: WindowPlacement,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._placement = placement
        self._logger = logger or logging.getLogger(__name__)
        self._hovered = False
        self._target_bounds_x11: tuple[float, float, float, float] | None = None

        self._surface: cairo.ImageSurface | None = None
        asset = self._find_asset()
        if asset is not None:
            try:
                self._surface = cairo.ImageSurface.create_from_png(str(asset))
            except Exception as exc:
                self._logger.warning("Could not load pot hide-target asset: %s", exc)

        self._window = Gtk.Window()
        self._window.set_title("Mochi hide target")
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_modal(False)
        self._window.set_focusable(False)
        self._window.set_hide_on_close(True)
        self._window.set_default_size(self.WINDOW_SIZE, self.WINDOW_SIZE)
        self._window.add_css_class("mochi-pot-hide-target")
        self._window.connect("map", self._on_map)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_content_width(self.WINDOW_SIZE)
        self._canvas.set_content_height(self.WINDOW_SIZE)
        self._canvas.set_can_target(False)
        self._canvas.set_focusable(False)
        self._canvas.set_draw_func(self._draw)
        self._window.set_child(self._canvas)

        self._layer_shell = bool(
            self._placement.layer_shell_enabled
            and Gtk4LayerShell is not None
            and Gtk4LayerShell.is_supported()
        )
        if self._layer_shell and Gtk4LayerShell is not None:
            Gtk4LayerShell.init_for_window(self._window)
            Gtk4LayerShell.set_namespace(self._window, "mochi-pot-hide-target")
            Gtk4LayerShell.set_layer(self._window, Gtk4LayerShell.Layer.TOP)
            Gtk4LayerShell.set_keyboard_mode(
                self._window, Gtk4LayerShell.KeyboardMode.NONE
            )
            Gtk4LayerShell.set_exclusive_zone(self._window, -1)
            Gtk4LayerShell.set_anchor(
                self._window, Gtk4LayerShell.Edge.RIGHT, True
            )
            Gtk4LayerShell.set_anchor(
                self._window, Gtk4LayerShell.Edge.BOTTOM, True
            )
            Gtk4LayerShell.set_margin(
                self._window,
                Gtk4LayerShell.Edge.RIGHT,
                self.CORNER_MARGIN_PX,
            )
            Gtk4LayerShell.set_margin(
                self._window,
                Gtk4LayerShell.Edge.BOTTOM,
                self.CORNER_MARGIN_PX,
            )
        else:
            self._window.set_transient_for(owner)

        self._install_css(owner.get_display())

    @property
    def visible(self) -> bool:
        return bool(self._window.get_visible())

    @property
    def hovered(self) -> bool:
        return self._hovered

    def show(self) -> bool:
        """Reveal the target only when its desktop positioning path is usable."""
        if self._surface is None:
            return False
        if not self._layer_shell and get_window_position(self._owner) is None:
            self._logger.debug("Pot hide target unavailable without X11 or layer-shell")
            return False

        self._set_hovered(False)
        self._window.set_opacity(self.RESTING_OPACITY)
        if self._layer_shell:
            self._position_layer_shell()
        self._window.set_visible(True)
        if not self._layer_shell:
            self._position_x11()
            GLib.idle_add(self._position_x11)
        return True

    def hide(self) -> None:
        self._set_hovered(False)
        self._target_bounds_x11 = None
        if self._window.get_visible():
            self._window.hide()

    def destroy(self) -> None:
        self.hide()
        self._window.destroy()

    def update_hover(self, anchor: tuple[float, float] | None) -> bool:
        if not self.visible:
            self._set_hovered(False)
            return False

        if self._layer_shell:
            hovered = self._layer_shell_hovered(anchor)
        else:
            pointer = get_pointer_position(self._owner)
            if pointer is None:
                hovered = False
            else:
                if self._target_bounds_x11 is None:
                    self._position_x11()
                hovered = self._point_in_padded_rect(
                    pointer,
                    self._target_bounds_x11,
                    self.HIT_PADDING_PX * self._x11_coordinate_scale(self._owner),
                )

        self._set_hovered(hovered)
        return hovered

    def _set_hovered(self, hovered: bool) -> None:
        hovered = bool(hovered)
        if hovered == self._hovered:
            return
        self._hovered = hovered
        self._window.set_opacity(
            self.HOVER_OPACITY if hovered else self.RESTING_OPACITY
        )
        self._canvas.queue_draw()

    def _on_map(self, _window: Gtk.Window) -> None:
        surface = self._window.get_surface()
        if surface is not None:
            try:
                # The pot is visual feedback, never a competing pointer target.
                surface.set_input_region(cairo.Region())
            except Exception as exc:
                self._logger.debug("Could not make pot target input-transparent: %s", exc)
        if not self._layer_shell:
            request_keep_above(self._window)
            GLib.idle_add(self._position_x11)

    def _draw(
        self,
        _area: Gtk.DrawingArea,
        context: cairo.Context,
        width: int,
        height: int,
    ) -> None:
        if self._surface is None:
            return

        center_x = width / 2.0
        center_y = height / 2.0
        if self._hovered:
            context.save()
            context.set_source_rgba(0.47, 0.79, 0.55, 0.20)
            context.arc(center_x, center_y, 36.0, 0.0, 6.283185307179586)
            context.fill()
            context.restore()

        x = round((width - self.ART_SIZE) / 2)
        y = round((height - self.ART_SIZE) / 2)
        context.save()
        context.set_source_surface(self._surface, x, y)
        pattern = context.get_source()
        if isinstance(pattern, cairo.SurfacePattern):
            pattern.set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()

    def _position_layer_shell(self) -> None:
        if not self._layer_shell or Gtk4LayerShell is None:
            return
        monitor = Gtk4LayerShell.get_monitor(self._owner)
        if monitor is not None:
            try:
                Gtk4LayerShell.set_monitor(self._window, monitor)
            except Exception:
                pass

    def _layer_shell_hovered(
        self, anchor: tuple[float, float] | None
    ) -> bool:
        if Gtk4LayerShell is None:
            return False
        monitor = Gtk4LayerShell.get_monitor(self._owner)
        if monitor is None:
            return False

        geometry = monitor.get_geometry()
        owner_width = max(1, self._owner.get_width())
        owner_height = max(1, self._owner.get_height())
        anchor_x, anchor_y = anchor or (owner_width / 2.0, owner_height / 2.0)

        pointer_x = self._placement.position.x + anchor_x
        pointer_from_bottom = (
            self._placement.position.y + owner_height - anchor_y
        )

        rect = (
            geometry.width - self.CORNER_MARGIN_PX - self.WINDOW_SIZE,
            self.CORNER_MARGIN_PX,
            self.WINDOW_SIZE,
            self.WINDOW_SIZE,
        )
        return self._point_in_padded_rect(
            (pointer_x, pointer_from_bottom),
            rect,
            self.HIT_PADDING_PX,
        )

    def _position_x11(self) -> bool:
        if self._layer_shell or not self.visible:
            return GLib.SOURCE_REMOVE
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            return GLib.SOURCE_REMOVE

        owner_scale = self._x11_coordinate_scale(self._owner)
        owner_width = max(1, self._owner.get_width()) * owner_scale
        owner_height = max(1, self._owner.get_height()) * owner_scale
        center_x = owner_position[0] + owner_width / 2.0
        center_y = owner_position[1] + owner_height / 2.0

        display = self._owner.get_display()
        monitors = display.get_monitors()
        geometries: list[tuple[float, float, float, float]] = []
        for index in range(monitors.get_n_items()):
            geometry = monitors.get_item(index).get_geometry()
            geometries.append(
                (
                    geometry.x * owner_scale,
                    geometry.y * owner_scale,
                    geometry.width * owner_scale,
                    geometry.height * owner_scale,
                )
            )
        if not geometries:
            return GLib.SOURCE_REMOVE

        monitor_x, monitor_y, monitor_width, monitor_height = min(
            geometries,
            key=lambda geometry: (
                max(geometry[0], min(center_x, geometry[0] + geometry[2]))
                - center_x
            )
            ** 2
            + (
                max(geometry[1], min(center_y, geometry[1] + geometry[3]))
                - center_y
            )
            ** 2,
        )

        size = self.WINDOW_SIZE * owner_scale
        margin = self.CORNER_MARGIN_PX * owner_scale
        x = round(monitor_x + monitor_width - margin - size)
        y = round(monitor_y + monitor_height - margin - size)
        self._target_bounds_x11 = (x, y, size, size)
        move_window(self._window, x, y)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _point_in_padded_rect(
        point: tuple[float, float],
        rect: tuple[float, float, float, float] | None,
        padding: float,
    ) -> bool:
        if rect is None:
            return False
        x, y = point
        left, top, width, height = rect
        return (
            left - padding <= x <= left + width + padding
            and top - padding <= y <= top + height + padding
        )

    @staticmethod
    def _x11_coordinate_scale(window: Gtk.Window) -> float:
        surface = window.get_surface()
        if surface is None:
            return 1.0
        get_scale = getattr(surface, "get_scale", None)
        if callable(get_scale):
            try:
                value = float(get_scale())
            except (TypeError, ValueError):
                value = 1.0
            if value > 0:
                return value
        get_scale_factor = getattr(surface, "get_scale_factor", None)
        if callable(get_scale_factor):
            try:
                value = float(get_scale_factor())
            except (TypeError, ValueError):
                value = 1.0
            if value > 0:
                return value
        return 1.0

    @staticmethod
    def _find_asset() -> Path | None:
        candidates = (
            Path(__file__).resolve().parents[2] / "assets" / "ui" / "pot.png",
            Path(sys.prefix) / "share" / "mochi" / "ui" / "pot.png",
        )
        return next((path for path in candidates if path.is_file()), None)

    @staticmethod
    def _install_css(display: Gdk.Display) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(
            """
            window.mochi-pot-hide-target {
                background: transparent;
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
