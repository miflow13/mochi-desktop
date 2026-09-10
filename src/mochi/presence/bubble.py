"""Non-focus-stealing speech bubble presentation for Mochi."""

from __future__ import annotations

import logging
import time

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.x11 import get_window_position, move_window, request_keep_above


class SpeechBubble:
    """Show one subtle bubble anchored to Mochi without stealing keyboard focus.

    X11/XWayland uses a transient toplevel positioned in root coordinates so it
    follows the same reliable multi-monitor strategy as Mochi's menus. Pure
    Wayland falls back to a Gtk.Popover anchored to the Buddy widget.
    """

    FOLLOW_INTERVAL_MS = 100
    FADE_IN_SECONDS = 0.20
    FADE_OUT_SECONDS = 0.26
    GAP_PX = 8
    MONITOR_PADDING_PX = 14

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
        self._hide_source_id: int | None = None
        self._follow_source_id: int | None = None
        self._animation_source_id: int | None = None
        self._animation_serial = 0
        self._mode: str | None = None

        self._label = self._make_label()
        self._bubble_box = self._make_bubble_content(self._label)

        self._window = Gtk.Window()
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_modal(False)
        self._window.set_focusable(False)
        self._window.set_hide_on_close(True)
        self._window.set_transient_for(owner)
        self._window.add_css_class("mochi-speech-window")
        self._window.set_child(self._bubble_box)
        self._window.connect("map", self._on_window_map)

        # A widget may only have one parent, so Wayland gets an equivalent copy.
        self._popover_label = self._make_label()
        self._popover_box = self._make_bubble_content(self._popover_label)

        self._popover = Gtk.Popover()
        self._popover.set_parent(anchor_widget)
        self._popover.set_autohide(False)
        self._popover.set_has_arrow(True)
        self._popover.set_position(Gtk.PositionType.TOP)
        self._popover.set_offset(0, -self.GAP_PX)
        self._popover.set_focusable(False)
        self._popover.set_can_target(False)
        self._popover.add_css_class("mochi-speech-popover")
        self._popover.set_child(self._popover_box)

        self._install_css(owner.get_display())

    @staticmethod
    def _make_label() -> Gtk.Label:
        label = Gtk.Label()
        label.set_wrap(True)
        label.set_max_width_chars(30)
        label.set_xalign(0.0)
        label.set_justify(Gtk.Justification.LEFT)
        label.set_focusable(False)
        label.set_can_target(False)
        label.add_css_class("mochi-speech-text")
        return label

    @staticmethod
    def _make_bubble_content(label: Gtk.Label) -> Gtk.Box:
        # Keep a little transparent breathing room outside the painted capsule
        # so GTK has room to render the soft shadow without clipping it.
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shell.add_css_class("mochi-speech-shell")
        shell.set_margin_top(7)
        shell.set_margin_bottom(7)
        shell.set_margin_start(7)
        shell.set_margin_end(7)
        shell.set_focusable(False)
        shell.set_can_target(False)

        capsule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        capsule.add_css_class("mochi-speech-bubble")
        capsule.set_focusable(False)
        capsule.set_can_target(False)

        dot = Gtk.Box()
        dot.set_size_request(6, 6)
        dot.set_valign(Gtk.Align.CENTER)
        dot.set_focusable(False)
        dot.set_can_target(False)
        dot.add_css_class("mochi-speech-dot")

        capsule.append(dot)
        capsule.append(label)
        shell.append(capsule)
        return shell

    @property
    def visible(self) -> bool:
        return bool(self._window.get_visible() or self._popover.get_visible())

    def show(self, text: str, *, duration_seconds: float) -> bool:
        if self.visible or not text.strip():
            return False
        self._cancel_sources()
        self._label.set_text(text)
        self._popover_label.set_text(text)

        if get_window_position(self._owner) is not None:
            self._mode = "x11"
            self._window.set_opacity(0.0)
            self._window.set_visible(True)
            serial = self._animation_serial
            GLib.idle_add(self._position_x11)
            GLib.timeout_add(24, self._position_x11)
            self._follow_source_id = GLib.timeout_add(
                self.FOLLOW_INTERVAL_MS,
                self._follow_x11,
            )
            self._fade(self._window, 0.0, 1.0, self.FADE_IN_SECONDS, serial)
        else:
            self._mode = "wayland"
            self._popover.set_opacity(0.0)
            self._popover.popup()
            serial = self._animation_serial
            self._fade(self._popover, 0.0, 1.0, self.FADE_IN_SECONDS, serial)

        self._hide_source_id = GLib.timeout_add(
            max(1, round(duration_seconds * 1000)),
            self._begin_hide,
        )
        return True

    def hide(self) -> None:
        """Hide immediately; used when direct user interaction takes priority."""
        self._animation_serial += 1
        self._cancel_sources()
        self._finish_hide()

    def _begin_hide(self) -> bool:
        self._hide_source_id = None
        if not self.visible:
            return GLib.SOURCE_REMOVE
        self._animation_serial += 1
        serial = self._animation_serial
        widget = self._window if self._mode == "x11" else self._popover
        start = float(widget.get_opacity())
        self._fade(
            widget,
            start,
            0.0,
            self.FADE_OUT_SECONDS,
            serial,
            on_finished=self._finish_hide,
        )
        return GLib.SOURCE_REMOVE

    def _finish_hide(self) -> None:
        if self._window.get_visible():
            self._window.hide()
        if self._popover.get_visible():
            self._popover.popdown()
        self._stop_following()
        self._mode = None

    def _fade(
        self,
        widget: Gtk.Widget,
        start_opacity: float,
        end_opacity: float,
        duration_seconds: float,
        serial: int,
        *,
        on_finished=None,
    ) -> None:
        if self._animation_source_id is not None:
            try:
                GLib.source_remove(self._animation_source_id)
            except Exception:
                pass
            self._animation_source_id = None
        started = time.monotonic()

        def animate() -> bool:
            if serial != self._animation_serial:
                self._animation_source_id = None
                return GLib.SOURCE_REMOVE
            elapsed = time.monotonic() - started
            progress = min(1.0, elapsed / max(0.001, duration_seconds))
            eased = 1.0 - (1.0 - progress) ** 3
            widget.set_opacity(
                start_opacity + (end_opacity - start_opacity) * eased
            )
            if progress >= 1.0:
                self._animation_source_id = None
                if on_finished is not None:
                    on_finished()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        self._animation_source_id = GLib.timeout_add(16, animate)

    def _on_window_map(self, _window: Gtk.Window) -> None:
        request_keep_above(self._window)
        GLib.idle_add(self._position_x11)

    def _follow_x11(self) -> bool:
        if self._mode != "x11" or not self._window.get_visible():
            self._follow_source_id = None
            return GLib.SOURCE_REMOVE
        self._position_x11()
        return GLib.SOURCE_CONTINUE

    def _position_x11(self) -> bool:
        if self._mode != "x11" or not self._window.get_visible():
            return GLib.SOURCE_REMOVE
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            self._logger.debug("Speech bubble X11 position unavailable; hiding")
            self._finish_hide()
            return GLib.SOURCE_REMOVE

        owner_x, owner_y = owner_position
        owner_width = max(1, self._owner.get_width())
        owner_height = max(1, self._owner.get_height())
        width = self._window.get_width()
        height = self._window.get_height()
        if width <= 1:
            width = 218
        if height <= 1:
            height = 46

        display = self._owner.get_display()
        monitors = display.get_monitors()
        geometries = [
            monitors.get_item(index).get_geometry()
            for index in range(monitors.get_n_items())
        ]
        center_x = owner_x + owner_width / 2
        center_y = owner_y + owner_height / 2
        if geometries:
            monitor = min(
                geometries,
                key=lambda geometry: (
                    max(geometry.x, min(center_x, geometry.x + geometry.width)) - center_x
                ) ** 2
                + (
                    max(geometry.y, min(center_y, geometry.y + geometry.height)) - center_y
                ) ** 2,
            )
            left = monitor.x + self.MONITOR_PADDING_PX
            top = monitor.y + self.MONITOR_PADDING_PX
            right = monitor.x + monitor.width - self.MONITOR_PADDING_PX
            bottom = monitor.y + monitor.height - self.MONITOR_PADDING_PX
        else:
            left, top = 0, 0
            right = owner_x + owner_width + width
            bottom = owner_y + owner_height + height

        x = round(owner_x + owner_width / 2 - width / 2)
        y_above = owner_y - height - self.GAP_PX
        y_below = owner_y + owner_height + self.GAP_PX
        y = y_above if y_above >= top else y_below
        x = max(left, min(x, max(left, right - width)))
        y = max(top, min(y, max(top, bottom - height)))
        move_window(self._window, x, y)
        return GLib.SOURCE_REMOVE

    def _cancel_sources(self) -> None:
        self._animation_serial += 1
        for attr in ("_hide_source_id", "_animation_source_id"):
            source_id = getattr(self, attr)
            setattr(self, attr, None)
            if source_id is not None:
                try:
                    GLib.source_remove(source_id)
                except Exception:
                    pass
        self._stop_following()

    def _stop_following(self) -> None:
        source_id = self._follow_source_id
        self._follow_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    @staticmethod
    def _install_css(display: Gdk.Display) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(
            """
            window.mochi-speech-window {
                background: transparent;
            }
            .mochi-speech-shell {
                background: transparent;
            }
            .mochi-speech-bubble {
                background: alpha(@window_bg_color, 0.96);
                color: @window_fg_color;
                border: 1px solid alpha(#79c98b, 0.30);
                border-radius: 999px;
                box-shadow: 0 5px 16px alpha(black, 0.14);
                padding: 8px 12px 8px 10px;
            }
            .mochi-speech-dot {
                background: #79c98b;
                border-radius: 999px;
                min-width: 6px;
                min-height: 6px;
            }
            .mochi-speech-text {
                font-size: 12px;
                font-weight: 500;
            }
            popover.mochi-speech-popover > contents {
                background: transparent;
                border: none;
                box-shadow: none;
                padding: 0;
            }
            popover.mochi-speech-popover > arrow {
                background: alpha(@window_bg_color, 0.96);
                border-color: alpha(#79c98b, 0.30);
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
