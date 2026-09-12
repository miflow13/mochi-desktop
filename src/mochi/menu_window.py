"""Monitor-aware menu windows for Mochi's XWayland buddy.

Mochi is a freely moved XWayland toplevel. Gtk.Popover popup surfaces can keep
stale monitor/parent placement when that parent moves between monitors. These
menus use ordinary transient Gtk.Window surfaces positioned in X11 root
coordinates instead, so both user and developer menus follow the same reliable
multi-monitor path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.x11 import get_window_position, move_window, request_keep_above


def _distance_to_geometry(x: float, y: float, geometry) -> float:
    nearest_x = max(geometry.x, min(x, geometry.x + geometry.width))
    nearest_y = max(geometry.y, min(y, geometry.y + geometry.height))
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2


def menu_position_for_anchor(
    anchor_x: int,
    anchor_y: int,
    menu_width: int,
    menu_height: int,
    geometries: list,
    *,
    gap: int = 12,
    padding: int = 12,
) -> tuple[int, int]:
    """Place a menu beside its anchor and clamp it to the nearest monitor."""
    if not geometries:
        return (anchor_x + gap, anchor_y)

    monitor = min(
        geometries,
        key=lambda geometry: _distance_to_geometry(anchor_x, anchor_y, geometry),
    )
    left = monitor.x + padding
    top = monitor.y + padding
    right = monitor.x + monitor.width - padding
    bottom = monitor.y + monitor.height - padding

    preferred_right = anchor_x + gap
    preferred_left = anchor_x - gap - menu_width
    if preferred_right + menu_width <= right:
        x = preferred_right
    elif preferred_left >= left:
        x = preferred_left
    else:
        x = anchor_x - menu_width // 2

    max_x = max(left, right - menu_width)
    max_y = max(top, bottom - menu_height)
    x = max(left, min(round(x), max_x))
    y = max(top, min(round(anchor_y - 24), max_y))
    return (x, y)


class MenuWindow:
    """Small transient window exposing the subset of Gtk.Popover Buddy needs."""

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        anchor_widget: Gtk.Widget,
        preferred_width: int,
        preferred_height: int,
        follow_owner: bool = False,
        dismiss_on_focus_loss: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._preferred_width = preferred_width
        self._preferred_height = preferred_height
        self._follow_owner = follow_owner
        self._dismiss_on_focus_loss = dismiss_on_focus_loss
        self._dismiss_armed = False
        self._logger = logger or logging.getLogger(__name__)
        self._anchor_x = max(1, anchor_widget.get_width() // 2)
        self._anchor_y = max(1, anchor_widget.get_height() // 2)
        self._closed_callbacks: list[Callable[[MenuWindow], None]] = []
        self._position_serial = 0
        self._follow_source_id: int | None = None
        self._drag_handle: Gtk.Widget | None = None

        self.window = Gtk.Window()
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_transient_for(owner)
        self.window.set_default_size(preferred_width, preferred_height)
        self.window.add_css_class("mochi-menu-window")
        self.window.connect("map", self._on_map)
        self.window.connect("close-request", self._on_close_request)
        self.window.connect("notify::is-active", self._on_active_changed)
        self.window.connect("notify::is-active", self._on_active_changed)

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(keys)

    def add_css_class(self, css_class: str) -> None:
        self.window.add_css_class(css_class)

    def set_child(self, child: Gtk.Widget) -> None:
        self.window.set_child(child)

    def set_preferred_size(self, width: int, height: int) -> None:
        """Update the fallback size used before GTK allocation settles."""
        self._preferred_width = width
        self._preferred_height = height
        self.window.set_default_size(width, height)

    def set_drag_handle(self, widget: Gtk.Widget) -> None:
        """Use the compositor/window manager for a smooth titlebar-style move."""
        self._drag_handle = widget
        widget.set_cursor_from_name("grab")
        gesture = Gtk.GestureClick.new()
        gesture.set_button(Gdk.BUTTON_PRIMARY)
        gesture.connect("pressed", self._on_drag_pressed)
        widget.add_controller(gesture)

    def connect(self, signal_name: str, callback: Callable[[MenuWindow], None]) -> None:
        if signal_name != "closed":
            raise ValueError(
                f"MenuWindow only exposes the 'closed' signal, got {signal_name!r}"
            )
        self._closed_callbacks.append(callback)

    def set_pointing_to(self, rectangle: Gdk.Rectangle) -> None:
        self._anchor_x = round(rectangle.x + rectangle.width / 2)
        self._anchor_y = round(rectangle.y + rectangle.height / 2)

    def get_visible(self) -> bool:
        return bool(self.window.get_visible())

    def popup(self) -> None:
        self._position_serial += 1
        serial = self._position_serial
        self._dismiss_armed = False
        self.window.present()
        # Mapping/size allocation can settle after present(). Position twice
        # for this one request instead of requiring another user click.
        GLib.idle_add(self._position_if_current, serial)
        GLib.timeout_add(24, self._position_if_current, serial)
        if self._follow_owner and self._follow_source_id is None:
            self._follow_source_id = GLib.timeout_add(33, self._follow_owner_tick)
        if self._dismiss_on_focus_loss:
            # Let present()/focus settle before treating an inactive window as
            # an outside click. This avoids self-dismiss during mapping.
            GLib.timeout_add(90, self._arm_outside_dismiss)

    def popdown(self) -> None:
        if not self.window.get_visible():
            return
        self._position_serial += 1
        self._dismiss_armed = False
        self._dismiss_armed = False
        self._stop_following_owner()
        self.window.hide()
        for callback in tuple(self._closed_callbacks):
            callback(self)

    def _follow_owner_tick(self) -> bool:
        if not self._follow_owner or not self.window.get_visible():
            self._follow_source_id = None
            return GLib.SOURCE_REMOVE
        self._position_if_current(self._position_serial, quiet=True)
        return GLib.SOURCE_CONTINUE

    def _stop_following_owner(self) -> None:
        source_id = self._follow_source_id
        self._follow_source_id = None
        if source_id is not None:
            GLib.source_remove(source_id)

    def _on_drag_pressed(
        self,
        gesture: Gtk.GestureClick,
        _presses: int,
        _x: float,
        _y: float,
    ) -> None:
        """Hand window motion to the window manager instead of chasing pointer deltas."""
        event = gesture.get_current_event()
        surface = self.window.get_surface()
        if event is None or surface is None or not hasattr(surface, "begin_move"):
            self._logger.debug("Native developer-menu move unavailable")
            return

        positioned, surface_x, surface_y = event.get_position()
        if not positioned:
            return
        device = event.get_device()
        if device is None:
            return

        # Gdk.Toplevel.begin_move() is the GTK4 titlebar-style move path. The
        # compositor/WM owns the pointer grab and movement from this point, so
        # XWayland does not fight a stream of application-side XMoveWindow calls.
        surface.begin_move(
            device,
            Gdk.BUTTON_PRIMARY,
            surface_x,
            surface_y,
            event.get_time(),
        )
        self._logger.debug("Developer menu native move started")

    def _arm_outside_dismiss(self) -> bool:
        if self.window.get_visible():
            self._dismiss_armed = True
        return GLib.SOURCE_REMOVE

    def _on_active_changed(self, window: Gtk.Window, _pspec) -> None:
        if (
            self._dismiss_on_focus_loss
            and self._dismiss_armed
            and window.get_visible()
            and not window.is_active()
        ):
            # Defer one loop turn so focus can move between child controls
            # without being mistaken for a click outside the toplevel.
            GLib.idle_add(self._dismiss_if_still_inactive)

    def _dismiss_if_still_inactive(self) -> bool:
        if (
            self._dismiss_on_focus_loss
            and self._dismiss_armed
            and self.window.get_visible()
            and not self.window.is_active()
        ):
            self.popdown()
        return GLib.SOURCE_REMOVE

    def _on_map(self, _window: Gtk.Window) -> None:
        request_keep_above(self.window)
        serial = self._position_serial
        GLib.idle_add(self._position_if_current, serial)

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self.popdown()
        return True

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.popdown()
            return True
        return False

    def _position_if_current(self, serial: int, quiet: bool = False) -> bool:
        if serial != self._position_serial or not self.window.get_visible():
            return GLib.SOURCE_REMOVE

        owner_position = get_window_position(self._owner)
        if owner_position is None:
            self._logger.warning(
                "Menu position unavailable: owner has no X11 root position"
            )
            return GLib.SOURCE_REMOVE

        owner_x, owner_y = owner_position
        anchor_x = owner_x + self._anchor_x
        anchor_y = owner_y + self._anchor_y

        width = self.window.get_width()
        height = self.window.get_height()
        if width <= 1:
            width = self._preferred_width
        if height <= 1:
            height = self._preferred_height

        monitor_list = self._owner.get_display().get_monitors()
        geometries = [
            monitor_list.get_item(index).get_geometry()
            for index in range(monitor_list.get_n_items())
        ]
        x, y = menu_position_for_anchor(
            anchor_x,
            anchor_y,
            width,
            height,
            geometries,
        )
        moved = move_window(self.window, x, y)
        if not quiet:
            self._logger.debug(
                "Menu surface position anchor=(%d,%d) target=(%d,%d) "
                "size=(%d,%d) moved=%s",
                anchor_x,
                anchor_y,
                x,
                y,
                width,
                height,
                moved,
            )
        return GLib.SOURCE_REMOVE
