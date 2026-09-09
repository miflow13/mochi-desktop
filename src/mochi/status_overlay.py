"""GTK presentation component for Mochi's contextual status bubble."""

from __future__ import annotations

import cairo
import gi
import time

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.state import MochiState
from mochi.status import (
    OverlayMode,
    OverlayVisibility,
    clamp_status_value,
    friendly_state_label,
)


class StatusBar(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self._value = 1.0
        self.set_content_width(84)
        self.set_content_height(7)
        self.set_draw_func(self._draw)

    def set_value(self, value: float) -> None:
        self._value = clamp_status_value(value)
        self.queue_draw()

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int
    ) -> None:
        pip_count = 5
        gap = 3
        pip_width = (width - gap * (pip_count - 1)) / pip_count
        filled = round(self._value * pip_count)
        for index in range(pip_count):
            color = (
                (0.337, 0.718, 0.424)
                if index < filled
                else (0.776, 0.855, 0.792)
            )
            context.set_source_rgb(*color)
            x = index * (pip_width + gap)
            context.rectangle(round(x), 0, max(1, round(pip_width)), height)
            context.fill()


class BubbleTail(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self.set_content_width(14)
        self.set_content_height(8)
        self.set_draw_func(self._draw)

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, _width: int, _height: int
    ) -> None:
        context.move_to(2, 0)
        context.line_to(12, 0)
        context.line_to(9, 3)
        context.line_to(9, 5)
        context.line_to(5, 5)
        context.line_to(5, 3)
        context.close_path()
        context.set_source_rgb(0.173, 0.302, 0.224)
        context.fill()
        context.move_to(5, 0)
        context.line_to(9, 0)
        context.line_to(8, 2)
        context.line_to(8, 3)
        context.line_to(6, 3)
        context.line_to(6, 2)
        context.close_path()
        context.set_source_rgb(1.0, 0.973, 0.941)
        context.fill()


class MochiStatusOverlay(Gtk.Popover):
    WIDTH = 164
    PANEL_HEIGHT = 36
    TOTAL_HEIGHT = 44
    HOVER_DELAY_MS = 2_000
    LEAVE_GRACE_MS = 250
    FADE_MS = 160

    CSS = """
    .mochi-status-panel {
        min-width: 164px;
        min-height: 36px;
        padding: 6px 8px;
        border: 2px solid #3D2B3A;
        border-radius: 8px;
        background: #E8F8E9;
        box-shadow: 0 2px 0 #3D2B3A;
    }
    .mochi-status-popover {
        background: transparent;
        box-shadow: none;
        padding: 0;
    }
    .mochi-status-name {
        color: #294936;
        font-family: Rubik, sans-serif;
        font-size: 13px;
        font-weight: 800;
    }
    .mochi-status-state {
        color: #587361;
        font-family: Rubik, sans-serif;
        font-size: 9px;
        font-weight: 700;
    }
    .mochi-status-heart {
        color: #E96D84;
        font-size: 11px;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.add_css_class("mochi-status-popover")
        self.set_autohide(False)
        self.set_has_arrow(True)
        self.set_position(Gtk.PositionType.TOP)
        self.set_can_focus(False)
        self.set_can_target(True)
        self._hover_delay_source = 0
        self._leave_source = 0
        self._fade_source = 0
        self._visibility = OverlayVisibility()
        self._fade_generation = 0
        self._mode = OverlayMode.HIDDEN
        self._anchor_hovered = False
        self._card_hovered = False
        self._hover_state = MochiState.IDLE
        self._status_value = 1.0

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        panel.add_css_class("mochi-status-panel")
        self._panel = panel

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        name = Gtk.Label(label="Mochi")
        name.add_css_class("mochi-status-name")
        name.set_xalign(0)
        header.append(name)
        self._state_label = Gtk.Label(label="Happy")
        self._state_label.add_css_class("mochi-status-state")
        self._state_label.set_hexpand(True)
        self._state_label.set_xalign(1)
        header.append(self._state_label)
        panel.append(header)

        health = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        heart = Gtk.Label(label="♥")
        heart.add_css_class("mochi-status-heart")
        health.append(heart)
        self._status_bar = StatusBar()
        self._status_bar.set_hexpand(True)
        health.append(self._status_bar)
        self._health_label = Gtk.Label(label="Health")
        self._health_label.add_css_class("mochi-status-state")
        self._health_label.set_visible(False)
        health.append(self._health_label)
        self._status_percent = Gtk.Label(label="100%")
        self._status_percent.add_css_class("mochi-status-state")
        self._status_percent.set_visible(False)
        health.append(self._status_percent)
        panel.append(health)
        self._health_row = health

        panel_motion = Gtk.EventControllerMotion.new()
        panel_motion.connect("enter", self._on_card_enter)
        panel_motion.connect("leave", self._on_card_leave)
        panel.add_controller(panel_motion)
        card_click = Gtk.GestureClick.new()
        card_click.set_button(Gdk.BUTTON_PRIMARY)
        card_click.connect("pressed", self._on_card_clicked)
        panel.add_controller(card_click)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)
        self.connect("closed", self._on_closed)

        self.set_child(panel)

    @classmethod
    def install_css(cls, display: object) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(cls.CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    def set_status_value(self, value: float) -> None:
        self._status_value = clamp_status_value(value)
        self._status_bar.set_value(self._status_value)
        self._status_percent.set_label(f"{round(self._status_value * 100)}%")

    def shutdown(self) -> None:
        """Cancel pending animations and detach the manually parented popover."""
        self._fade_generation += 1
        for attribute in (
            "_hover_delay_source",
            "_leave_source",
            "_fade_source",
        ):
            self._cancel_source(attribute)
        self.popdown()
        if self.get_parent() is not None:
            self.unparent()

    def dismiss_for_click(self) -> None:
        if self._mode is not OverlayMode.HIDDEN:
            self.hide_context()

    def hover_enter(self, state: MochiState) -> None:
        self._anchor_hovered = True
        self._hover_state = state
        self._cancel_source("_leave_source")
        self._cancel_source("_hover_delay_source")
        self._hover_delay_source = GLib.timeout_add(
            self.HOVER_DELAY_MS, self._show_hover_if_current
        )

    def hover_leave(self) -> None:
        self._anchor_hovered = False
        self._schedule_hover_hide()

    def _show_hover_if_current(self) -> bool:
        self._hover_delay_source = 0
        if not self._anchor_hovered:
            return GLib.SOURCE_REMOVE
        self._state_label.set_label(friendly_state_label(self._hover_state))
        self._show_mode(OverlayMode.PEEK)
        return GLib.SOURCE_REMOVE

    def _show_mode(self, mode: OverlayMode) -> int:
        generation = self._visibility.present(mode)
        self._mode = mode
        self._set_layout(mode)
        self.set_autohide(False)
        self.set_focusable(False)
        self.set_opacity(0.0)
        self.popup()
        self._animate_to(1.0)
        return generation

    def _schedule_hover_hide(self) -> None:
        self._cancel_source("_leave_source")
        self._leave_source = GLib.timeout_add(
            self.LEAVE_GRACE_MS, self._hide_hover_if_clear
        )

    def _hide_hover_if_clear(self) -> bool:
        self._leave_source = 0
        if self._anchor_hovered or self._card_hovered or self._mode is OverlayMode.EXPANDED:
            return GLib.SOURCE_REMOVE
        self._begin_hide()
        return GLib.SOURCE_REMOVE

    def _set_layout(self, mode: OverlayMode) -> None:
        expanded = mode is OverlayMode.EXPANDED
        self._panel.set_size_request(190 if expanded else 164, 58 if expanded else 36)
        self._health_row.set_visible(True)
        self._state_label.set_visible(True)
        self._health_label.set_visible(expanded)
        self._status_percent.set_visible(expanded)
        self._panel.set_spacing(5 if expanded else 2)

    def _on_card_clicked(
        self, _gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float
    ) -> None:
        if self._mode is not OverlayMode.EXPANDED:
            self._visibility.present(OverlayMode.EXPANDED)
            self._mode = OverlayMode.EXPANDED
            self._set_layout(OverlayMode.EXPANDED)
            self._cancel_source("_leave_source")
            self._cancel_source("_hover_delay_source")
            self.set_autohide(True)
            self.set_focusable(True)
            self.grab_focus()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if self._mode is OverlayMode.EXPANDED and keyval == Gdk.KEY_Escape:
            self._begin_hide()
            return True
        return False

    def _on_closed(self, _popover: Gtk.Popover) -> None:
        if self._mode is not OverlayMode.HIDDEN:
            self._visibility.hide()
            self._mode = OverlayMode.HIDDEN

    def _on_card_enter(self, _controller: Gtk.EventControllerMotion, _x: float, _y: float) -> None:
        self._card_hovered = True
        self._cancel_source("_leave_source")

    def _on_card_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        self._card_hovered = False
        self._schedule_hover_hide()

    def _begin_hide(self) -> None:
        self._visibility.hide()
        self._mode = OverlayMode.HIDDEN
        self._animate_to(0.0, self.popdown)

    def _animate_to(self, target: float, on_finished=None) -> None:
        self._cancel_source("_fade_source")
        self._fade_generation += 1
        generation = self._fade_generation
        start_opacity = self.get_opacity()
        start_time = time.monotonic()
        duration = self.FADE_MS / 1_000

        def step() -> bool:
            if generation != self._fade_generation:
                return GLib.SOURCE_REMOVE
            progress = min(1.0, (time.monotonic() - start_time) / duration)
            self.set_opacity(start_opacity + (target - start_opacity) * progress)
            if progress >= 1.0:
                self._fade_source = 0
                if on_finished is not None:
                    on_finished()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        self._fade_source = GLib.timeout_add(16, step)

    def _cancel_source(self, attribute: str) -> None:
        source = getattr(self, attribute)
        if source:
            GLib.source_remove(source)
            setattr(self, attribute, 0)

    def hide_context(self) -> None:
        self._visibility.hide()
        self._anchor_hovered = False
        self._card_hovered = False
        self._cancel_source("_hover_delay_source")
        self._cancel_source("_leave_source")
        self._begin_hide()
