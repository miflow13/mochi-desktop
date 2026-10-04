"""The "Talk to Mochi" control: a placeholder for the planned voice feature.

A 48 px circular button with a five-bar waveform that appears beside Mochi on
hover. Activating it opens an honest "coming soon" panel. Nothing here touches
a microphone, records, transcribes, or talks to any service.

Structure follows Mochi's existing overlays: a small undecorated transient
window moved in X11/XWayland root coordinates (like the nameplate and speech
bubble), shown with ``set_visible`` so hover never takes focus, and the
existing ``MenuWindow`` for the panel instead of a ``Gtk.Popover`` (an earlier
interactive popover overlay fought the context menu for grabs and froze).
Input is clipped to the visible circle so transparent margins stay
click-through.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import replace

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Graphene, Gtk  # noqa: E402

from mochi.menu_window import MenuWindow
from mochi.sprites import ANIMATIONS
from mochi.voice_control_model import (
    BAR_CENTERS_X,
    BAR_WIDTH,
    BUTTON_RADIUS,
    BUTTON_SIZE,
    IDLE_HEIGHTS,
    SETTLE_MS,
    Rect,
    VisibilityTracker,
    bar_heights_at,
    inside_button,
    place_control,
    place_panel,
    settle_heights,
)
from mochi.x11 import get_window_position, move_window, request_keep_above

try:
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11  # noqa: E402
except (ImportError, ValueError):  # pragma: no cover - non-X11 builds
    GdkX11 = None


TOOLTIP_TEXT = "Talk to Mochi"
DESCRIPTION_TEXT = "Voice chat is coming soon."
PANEL_BODY_TEXT = "Voice chat is coming soon. Mochi can’t hear you yet."

# Room around the circle for the 3 px gap + 2 px focus ring and the shadow.
MARGIN_PX = 14
LABEL_DELAY_SECONDS = 0.45
FADE_IN_SECONDS = 0.12
FADE_OUT_SECONDS = 0.14
COLOR_SECONDS = 0.12
PRESSED_SCALE = 0.96
FRAME_MS = 33  # ~30 fps is plenty for a 48 px effect

IDLE_FILL = (0xFF, 0xF8, 0xF0)
HOVER_FILL = (0xFF, 0xEB, 0xDD)
OPEN_FILL = (0xF8, 0xE6, 0xEF)
BORDER = (0xD8, 0xC5, 0xBA)
INK = (0x51, 0x3A, 0x45)
ACCENT = (0x98, 0x60, 0x78)
SHADOW = (0x39, 0x2A, 0x32)

_CSS = b"""
window.mochi-voice-window { background: transparent; }
.mochi-voice-label {
    background: #FFF8F0;
    color: #513A45;
    border: 1px solid #D8C5BA;
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 13px;
    font-weight: 500;
}
.mochi-voice-panel { background: #FFF8F0; border-radius: 16px; padding: 16px; }
.mochi-voice-panel-title { color: #513A45; font-weight: 700; }
.mochi-voice-panel-body { color: #765F6B; }
"""


def _rgb(color: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in color)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float):
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


class VoiceControl:
    def __init__(
        self,
        *,
        owner: Gtk.Window,
        anchor_widget: Gtk.Widget,
        on_activate: Callable[[], None],
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._anchor = anchor_widget
        self._on_activate = on_activate
        self._logger = logger or logging.getLogger(__name__)
        self._visibility = VisibilityTracker()
        self._side: str | None = None
        self._hovered = False
        self._focused = False
        self._engaged = False  # the user pressed or keyed the control itself
        self._pressed = False
        self._key_down: int | None = None
        self._hover_started: float | None = None
        self._settle_from: tuple[float, ...] | None = None
        self._settle_started: float | None = None
        self._heights = IDLE_HEIGHTS
        self._opacity = 0.0
        self._fill = IDLE_FILL
        self._fill_from = IDLE_FILL
        self._fill_changed: float | None = None
        self._frame_source_id: int | None = None
        self._input_region_key: tuple[int, int] | None = None
        self._destroyed = False

        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            owner.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.window = Gtk.Window()
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_modal(False)
        self.window.set_transient_for(owner)
        self.window.set_hide_on_close(True)
        self.window.add_css_class("mochi-voice-window")
        self.window.connect("realize", self._on_realize)
        # Like Mochi and his menus: stay above the focused app's windows.
        self.window.connect("map", lambda window: request_keep_above(window))

        area = BUTTON_SIZE + 2 * MARGIN_PX
        self.button = Gtk.DrawingArea(accessible_role=Gtk.AccessibleRole.BUTTON)
        self.button.set_content_width(area)
        self.button.set_content_height(area)
        self.button.set_halign(Gtk.Align.CENTER)
        self.button.set_focusable(True)
        self.button.set_draw_func(self._draw)
        self.button.update_property(
            [Gtk.AccessibleProperty.LABEL, Gtk.AccessibleProperty.DESCRIPTION],
            [TOOLTIP_TEXT, DESCRIPTION_TEXT],
        )
        self.button.update_state([Gtk.AccessibleState.EXPANDED], [0])

        self.label = Gtk.Label(label=TOOLTIP_TEXT)
        self.label.add_css_class("mochi-voice-label")
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_can_target(False)
        self.label.set_opacity(0.0)  # always allocated, so showing it never resizes

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self.button)
        box.append(self.label)
        self.window.set_child(box)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", lambda *_args: self._set_hovered(True))
        motion.connect("leave", lambda *_args: self._set_hovered(False))
        self.button.add_controller(motion)

        click = Gtk.GestureClick.new()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_pressed)
        click.connect("released", self._on_released)
        click.connect("cancel", lambda *_args: self._set_pressed(False))
        click.connect("stopped", lambda *_args: self._set_pressed(False))
        self.button.add_controller(click)

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        keys.connect("key-released", self._on_key_released)
        self.button.add_controller(keys)

        # GTK makes the only focusable widget its window's focus widget even
        # while that window is inactive, so "focused" also requires the window
        # to be active (i.e. the user clicked it).
        focus = Gtk.EventControllerFocus.new()
        focus.connect("enter", lambda *_args: self._sync_focus())
        focus.connect("leave", lambda *_args: self._sync_focus())
        self.button.add_controller(focus)
        self.window.connect("notify::is-active", lambda *_args: self._sync_focus())

        self._panel = self._build_panel()

    # Public API used by VoiceControlMixin -------------------------------

    def set_pet_hovered(self, hovered: bool) -> None:
        self._set_source("pet_hover", hovered)

    def set_suppressed(self, suppressed: bool) -> None:
        """Hide during drags and menus; come back if interaction remains."""
        self._visibility.set_dragging(suppressed)
        if suppressed:
            self._close_panel(restore_focus=False)
        else:
            self._side = None  # drag released: choose the side again
        self._ensure_frames()

    def follow(self) -> None:
        """Keep up with a walking Mochi without flipping sides."""
        if self.window.get_visible():
            self._reposition()

    def toggle_placeholder(self) -> None:
        """The single seam a real voice feature will later replace."""
        if self._panel.get_visible():
            self._close_panel(restore_focus=True)
        else:
            self._open_panel()

    def destroy(self) -> None:
        self._destroyed = True
        self._stop_frames()
        self._panel.popdown()
        self.window.destroy()

    # Visibility and motion ---------------------------------------------

    def _set_source(self, source: str, active: bool) -> None:
        self._visibility.set_source(source, active, now=time.monotonic())
        self._ensure_frames()

    def _set_hovered(self, hovered: bool) -> None:
        if hovered == self._hovered:
            return
        now = time.monotonic()
        self._hovered = hovered
        if hovered:
            self._hover_started = now
            self._settle_from = None
        else:
            self._hover_started = None
            self._settle_from = self._heights
            self._settle_started = now
        self._set_source("control_hover", hovered)
        self._update_fill()

    def _sync_focus(self) -> None:
        if not self.window.is_active():
            self._engaged = False
        focused = self._engaged and self.button.has_focus() and self.window.is_active()
        if focused == self._focused:
            return
        self._focused = focused
        self._set_source("control_focus", focused)
        self.button.queue_draw()

    def _set_pressed(self, pressed: bool) -> None:
        if pressed != self._pressed:
            self._pressed = pressed
            self.button.queue_draw()

    def _animations_enabled(self) -> bool:
        settings = Gtk.Settings.get_default()
        return settings is None or bool(settings.props.gtk_enable_animations)

    def _ensure_frames(self) -> None:
        if self._destroyed:
            return
        if self._frame_source_id is None:
            self._frame_source_id = GLib.timeout_add(FRAME_MS, self._frame)
        self._frame()

    def _stop_frames(self) -> None:
        if self._frame_source_id is not None:
            GLib.source_remove(self._frame_source_id)
            self._frame_source_id = None

    def _frame(self) -> bool:
        if self._destroyed:
            self._frame_source_id = None
            return GLib.SOURCE_REMOVE
        now = time.monotonic()
        animate = self._animations_enabled()
        visible = self._visibility.visible(now=now)
        busy = False

        if visible and not self.window.get_visible():
            self._side = None
            self.window.set_visible(True)
            self._reposition()

        target = 1.0 if visible else 0.0
        if not animate:
            self._opacity = target
        elif self._opacity != target:
            step = (FRAME_MS / 1000) / (FADE_IN_SECONDS if visible else FADE_OUT_SECONDS)
            self._opacity = (
                min(target, self._opacity + step)
                if visible
                else max(target, self._opacity - step)
            )
            busy = busy or self._opacity != target
        self.window.set_opacity(self._opacity)
        if not visible and self._opacity == 0.0 and self.window.get_visible():
            self._close_panel(restore_focus=False)
            self.window.set_visible(False)

        panel_open = self._panel.get_visible()
        heights = IDLE_HEIGHTS
        if animate and self._hovered and not panel_open and self._hover_started is not None:
            heights = bar_heights_at((now - self._hover_started) * 1000)
            busy = True
        elif animate and self._settle_from is not None and self._settle_started is not None:
            fraction = (now - self._settle_started) * 1000 / SETTLE_MS
            heights = settle_heights(self._settle_from, fraction)
            if fraction >= 1:
                self._settle_from = None
            else:
                busy = True
        if self._pressed:
            heights = self._heights  # hold the current pose while pressed

        if self._fill_changed is not None:
            amount = 1.0 if not animate else (now - self._fill_changed) / COLOR_SECONDS
            if amount >= 1:
                self._fill_changed = None
            else:
                busy = True

        label_wanted = not panel_open and (
            self._focused
            or (
                self._hover_started is not None
                and now - self._hover_started >= LABEL_DELAY_SECONDS
            )
        )
        self.label.set_opacity(1.0 if label_wanted else 0.0)
        if self._hovered and not label_wanted and not panel_open:
            busy = True  # still waiting out the label delay
        if visible and not self._visibility.visible(now=now + 1.0):
            busy = True  # inside the grace period; check again soon

        if heights != self._heights or busy:
            self._heights = heights
            self.button.queue_draw()

        if busy or (not visible and self.window.get_visible()):
            return GLib.SOURCE_CONTINUE
        self._frame_source_id = None
        return GLib.SOURCE_REMOVE

    def _update_fill(self) -> None:
        if self._panel.get_visible():
            target = OPEN_FILL
        elif self._hovered:
            target = HOVER_FILL
        else:
            target = IDLE_FILL
        if target != self._fill:
            self._fill_from = self._current_fill()
            self._fill = target
            self._fill_changed = time.monotonic()
            self._ensure_frames()

    def _current_fill(self) -> tuple[int, int, int]:
        if self._fill_changed is None or not self._animations_enabled():
            return self._fill
        amount = min(1.0, (time.monotonic() - self._fill_changed) / COLOR_SECONDS)
        return _mix(self._fill_from, self._fill, amount)

    # Drawing -------------------------------------------------------------

    def _draw(self, _area, context: cairo.Context, width: int, height: int) -> None:
        center_x = width / 2
        center_y = MARGIN_PX + BUTTON_RADIUS
        context.save()
        if self._pressed and self._animations_enabled():
            context.translate(center_x, center_y)
            context.scale(PRESSED_SCALE, PRESSED_SCALE)
            context.translate(-center_x, -center_y)

        # Soft shadow: a few widening translucent rings, offset 3 px down.
        for spread, alpha in ((6, 0.03), (4, 0.04), (2, 0.05), (0, 0.04)):
            context.arc(center_x, center_y + 3, BUTTON_RADIUS + spread, 0, 2 * math.pi)
            context.set_source_rgba(*_rgb(SHADOW), alpha)
            context.fill()

        context.arc(center_x, center_y, BUTTON_RADIUS - 0.5, 0, 2 * math.pi)
        context.set_source_rgb(*_rgb(self._current_fill()))
        context.fill_preserve()
        context.set_source_rgb(*_rgb(BORDER))
        context.set_line_width(1)
        context.stroke()

        origin_x = center_x - BUTTON_RADIUS
        context.set_source_rgb(*_rgb(INK))
        for bar_x, bar_height in zip(BAR_CENTERS_X, self._heights):
            _rounded_bar(context, origin_x + bar_x, center_y, BAR_WIDTH, bar_height)
        context.restore()

        if self._focused and self.window.get_focus_visible():
            context.arc(center_x, center_y, BUTTON_RADIUS + 3 + 1, 0, 2 * math.pi)
            context.set_source_rgb(*_rgb(ACCENT))
            context.set_line_width(2)
            context.stroke()

    def _on_realize(self, _window: Gtk.Window) -> None:
        surface = self.window.get_surface()
        if GdkX11 is not None and isinstance(surface, GdkX11.X11Surface):
            # EWMH: a zero user time asks the window manager not to focus the
            # window when it maps, so hover never takes focus from other apps.
            # Clicking it can still focus it for keyboard use.
            surface.set_user_time(0)
        self._clip_input_to_circle()

    def _clip_input_to_circle(self) -> None:
        """Only the visible circle takes clicks; margins stay click-through."""
        surface = self.window.get_surface()
        if surface is None:
            return
        found, origin = self.button.compute_point(
            self.window, Graphene.Point().init(0, MARGIN_PX)
        )
        if not found:
            return
        left = round(origin.x + (self.button.get_width() - BUTTON_SIZE) / 2)
        top = round(origin.y)
        if (left, top) == self._input_region_key:
            return
        self._input_region_key = (left, top)
        region = cairo.Region()
        for row in range(BUTTON_SIZE):
            dy = row + 0.5 - BUTTON_RADIUS
            half = math.sqrt(max(0.0, BUTTON_RADIUS**2 - dy * dy))
            start = math.floor(BUTTON_RADIUS - half)
            region.union(
                cairo.RectangleInt(left + start, top + row, BUTTON_SIZE - 2 * start, 1)
            )
        surface.set_input_region(region)

    # Placement -------------------------------------------------------------

    def _reposition(self) -> None:
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            return
        scale = _surface_scale(self._owner)
        owner_x, owner_y = owner_position[0] / scale, owner_position[1] / scale
        visible_x, visible_y, visible_w, visible_h = self._sprite_bounds()
        sprite = Rect(owner_x + visible_x, owner_y + visible_y, visible_w, visible_h)
        work_area = self._work_area(sprite)
        if work_area is None:
            return

        window_width = max(self.window.get_width(), self.button.get_width(), 1)
        label_height = max(self.label.get_height(), 0)
        placement = place_control(
            sprite, work_area, reserve_below=label_height, side=self._side
        )
        self._side = placement.side
        x = placement.x - (window_width - BUTTON_SIZE) / 2
        y = placement.y - MARGIN_PX
        move_window(self.window, round(x * scale), round(y * scale))
        self._clip_input_to_circle()

    def _sprite_bounds(self) -> tuple[float, float, float, float]:
        width = max(1, self._anchor.get_width())
        height = max(1, self._anchor.get_height())
        atlas = getattr(self._anchor, "atlas", None)
        if atlas is not None and hasattr(atlas, "visible_bounds"):
            # A fixed reference frame keeps the control steady while Mochi
            # animates (same approach as the nameplate).
            frame = replace(
                ANIMATIONS["idle"].frames[0], horizontal_offset=0.0, vertical_offset=0.0
            )
            try:
                return atlas.visible_bounds(frame, width, height)
            except Exception as error:  # noqa: BLE001 - fall back to the widget
                self._logger.debug("Voice control sprite bounds unavailable: %s", error)
        return (0.0, 0.0, float(width), float(height))

    def _work_area(self, sprite: Rect) -> Rect | None:
        display = self._owner.get_display()
        monitors = display.get_monitors()
        best = None
        center = (sprite.x + sprite.width / 2, sprite.y + sprite.height / 2)
        for index in range(monitors.get_n_items()):
            monitor = monitors.get_item(index)
            area = monitor.get_geometry()
            get_workarea = getattr(monitor, "get_workarea", None)
            if callable(get_workarea):  # GdkX11Monitor excludes panels
                area = get_workarea()
            rect = Rect(area.x, area.y, area.width, area.height)
            if rect.x <= center[0] < rect.right and rect.y <= center[1] < rect.bottom:
                return rect
            best = best or rect
        return best

    # Input -----------------------------------------------------------------

    def _on_pressed(self, _gesture, _presses: int, x: float, y: float) -> None:
        if inside_button(*self._to_button(x, y)):
            self._engaged = True
            self._set_pressed(True)

    def _on_released(self, _gesture, _presses: int, x: float, y: float) -> None:
        was_pressed = self._pressed
        self._set_pressed(False)
        if was_pressed and inside_button(*self._to_button(x, y)):
            self._on_activate()

    def _to_button(self, x: float, y: float) -> tuple[float, float]:
        # The area is center-aligned, so its width is always its content width;
        # using that also works before the first allocation.
        left = (self.button.get_content_width() - BUTTON_SIZE) / 2
        return x - left, y - MARGIN_PX

    def _on_key_pressed(self, _controller, keyval: int, _keycode, _state) -> bool:
        self._engaged = True
        self._sync_focus()
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._key_down = keyval
            self._set_pressed(True)
            return True
        if keyval == Gdk.KEY_Escape and self._panel.get_visible():
            self._close_panel(restore_focus=True)
            return True
        return False

    def _on_key_released(self, _controller, keyval: int, _keycode, _state) -> None:
        # Activate once per press, on release, like a native button; key
        # auto-repeat only re-sends key-pressed.
        if keyval == self._key_down:
            self._key_down = None
            self._set_pressed(False)
            self._on_activate()

    # Coming-soon panel -----------------------------------------------------

    def _button_on_screen(self) -> tuple[Rect, Rect, float] | None:
        """The circle's screen rectangle, its work area, and the X11 scale."""
        position = get_window_position(self.window)
        if position is None:
            return None
        scale = _surface_scale(self.window)
        found, origin = self.button.compute_point(
            self.window, Graphene.Point().init(0, MARGIN_PX)
        )
        if not found:
            return None
        left = origin.x + (self.button.get_width() - BUTTON_SIZE) / 2
        button = Rect(
            position[0] / scale + left,
            position[1] / scale + origin.y,
            BUTTON_SIZE,
            BUTTON_SIZE,
        )
        work_area = self._work_area(button)
        if work_area is None:
            return None
        return button, work_area, scale

    def _build_panel(self) -> MenuWindow:
        panel = _VoicePanelWindow(
            locate=self._button_on_screen,
            owner=self.window,
            anchor_widget=self.button,
            preferred_width=248,
            preferred_height=150,
            dismiss_on_focus_loss=True,
            logger=self._logger,
        )
        panel.add_css_class("mochi-voice-panel-window")

        title = Gtk.Label(label=TOOLTIP_TEXT, xalign=0)
        title.add_css_class("mochi-voice-panel-title")
        body = Gtk.Label(label=PANEL_BODY_TEXT, xalign=0, wrap=True)
        body.set_max_width_chars(28)
        body.add_css_class("mochi-voice-panel-body")
        done = Gtk.Button(label="Got it")
        done.set_halign(Gtk.Align.END)
        done.connect("clicked", lambda *_args: self._close_panel(restore_focus=True))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.add_css_class("mochi-voice-panel")
        content.set_size_request(248, -1)
        for child in (title, body, done):
            content.append(child)

        escape = Gtk.EventControllerKey.new()
        escape.connect("key-pressed", self._on_panel_key)
        content.add_controller(escape)

        panel.set_child(content)
        panel.connect("closed", self._on_panel_closed)
        return panel

    def _on_panel_key(self, _controller, keyval: int, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._close_panel(restore_focus=True)
            return True
        return False

    def _open_panel(self) -> None:
        self.label.set_opacity(0.0)
        self._set_source("panel_open", True)
        self._panel.popup()
        self.button.update_state([Gtk.AccessibleState.EXPANDED], [1])
        self._update_fill()

    def _close_panel(self, *, restore_focus: bool) -> None:
        if self._panel.get_visible():
            self._panel.popdown()
        if restore_focus and self.window.get_visible():
            self.button.grab_focus()
            self.window.present()

    def _on_panel_closed(self, _panel: MenuWindow) -> None:
        # Reached for every close path, including MenuWindow's own outside-click
        # dismissal, which must not take focus back from the other app.
        self.button.update_state([Gtk.AccessibleState.EXPANDED], [0])
        self._set_source("panel_open", False)
        self._update_fill()


class _VoicePanelWindow(MenuWindow):
    """MenuWindow behavior (outside-click dismissal, Escape, keep-above), but
    placed beside the button toward free space instead of centered on it."""

    def __init__(self, *, locate: Callable[[], tuple[Rect, Rect, float] | None], **kwargs):
        super().__init__(**kwargs)
        self._locate = locate

    def _position_if_current(self, serial: int, quiet: bool = False) -> bool:
        if serial != self._position_serial or not self.window.get_visible():
            return GLib.SOURCE_REMOVE
        located = self._locate()
        if located is None:
            return super()._position_if_current(serial, quiet)
        button, work_area, scale = located
        width = self.window.get_width()
        height = self.window.get_height()
        size = (
            width if width > 1 else self._preferred_width,
            height if height > 1 else self._preferred_height,
        )
        x, y = place_panel(button, size, work_area)
        move_window(self.window, round(x * scale), round(y * scale))
        return GLib.SOURCE_REMOVE


def _rounded_bar(context: cairo.Context, x: float, y: float, width: float, height: float) -> None:
    radius = width / 2
    top = y - height / 2
    bottom = y + height / 2
    context.new_sub_path()
    context.arc(x, top + radius, radius, math.pi, 0)
    context.arc(x, bottom - radius, radius, 0, math.pi)
    context.close_path()
    context.fill()


def _surface_scale(window: Gtk.Window) -> float:
    surface = window.get_surface()
    scale = getattr(surface, "get_scale", None) if surface is not None else None
    try:
        value = float(scale()) if callable(scale) else 1.0
    except (TypeError, ValueError):
        value = 1.0
    return value if value > 0 else 1.0
