"""Non-interactive popup showing live bond progress above Mochi."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.care import BondState
from mochi.emotes import EmoteDefinition
from mochi.sprites import ANIMATIONS
from mochi.x11 import get_window_position, move_window, request_keep_above


class BondProgressOverlay:
    """Tiny visual-only bond HUD that never participates in input handling."""

    GAP_PX = 7
    MONITOR_PADDING_PX = 12
    GAIN_FLASH_MS = 650
    LEVEL_UP_DISPLAY_MS = 3200
    EMOTE_UNLOCK_DISPLAY_MS = 3400
    LEVEL_UP_MIN_HOLD_SECONDS = 3.2

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        anchor_widget: Gtk.Widget,
        logger: logging.Logger | None = None,
        on_level_up_finished: Callable[[], None] | None = None,
    ) -> None:
        self._owner = owner
        self._anchor = anchor_widget
        self._logger = logger or logging.getLogger(__name__)
        self._on_level_up_finished = on_level_up_finished
        self._active = False
        self._mode: str | None = None
        self._hide_source_id: int | None = None
        self._gain_source_id: int | None = None
        self._level_up_source_id: int | None = None
        self._activity = "bonding"
        self._gain_text = ""
        self._level_up_active = False
        self._emote_unlock_active = False
        self._level_up_previous_level: int | None = None
        self._state = BondState()

        (
            self._content,
            self._card,
            self._normal_content,
            self._level_up_content,
            self._level_label,
            self._activity_label,
            self._bar,
            self._xp_label,
            self._gain_label,
            self._level_up_title,
            self._level_up_level,
            self._level_up_subtitle,
        ) = self._make_content()
        (
            self._popover_content,
            self._popover_card,
            self._popover_normal_content,
            self._popover_level_up_content,
            self._popover_level_label,
            self._popover_activity_label,
            self._popover_bar,
            self._popover_xp_label,
            self._popover_gain_label,
            self._popover_level_up_title,
            self._popover_level_up_level,
            self._popover_level_up_subtitle,
        ) = self._make_content()

        self._window = Gtk.Window()
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_modal(False)
        self._window.set_focusable(False)
        self._window.set_can_focus(False)
        self._window.set_hide_on_close(True)
        self._window.set_transient_for(owner)
        self._window.add_css_class("mochi-bond-window")
        self._window.set_child(self._content)
        self._window.connect("map", self._on_window_map)

        self._popover = Gtk.Popover()
        self._popover.set_parent(anchor_widget)
        self._popover.set_autohide(False)
        self._popover.set_has_arrow(True)
        self._popover.set_position(Gtk.PositionType.TOP)
        self._popover.set_offset(0, -self.GAP_PX)
        self._popover.set_focusable(False)
        self._popover.set_can_focus(False)
        self._popover.set_can_target(False)
        self._popover.add_css_class("mochi-bond-popover")
        self._popover.set_child(self._popover_content)

        self._install_css(owner.get_display())
        self.update(BondState())

    @staticmethod
    def _make_content() -> tuple[
        Gtk.Box,
        Gtk.Box,
        Gtk.Box,
        Gtk.Box,
        Gtk.Label,
        Gtk.Label,
        Gtk.ProgressBar,
        Gtk.Label,
        Gtk.Label,
        Gtk.Label,
        Gtk.Label,
        Gtk.Label,
    ]:
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shell.add_css_class("mochi-bond-shell")
        shell.set_margin_top(7)
        shell.set_margin_bottom(7)
        shell.set_margin_start(7)
        shell.set_margin_end(7)
        shell.set_focusable(False)
        shell.set_can_focus(False)
        shell.set_can_target(False)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("mochi-bond-card")
        card.set_focusable(False)
        card.set_can_focus(False)
        card.set_can_target(False)

        normal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        normal.set_can_target(False)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_can_target(False)

        level = Gtk.Label(label="Bond Lv. 1")
        level.set_xalign(0)
        level.set_hexpand(True)
        level.set_can_target(False)
        level.add_css_class("mochi-bond-level")
        header.append(level)

        activity = Gtk.Label(label="bonding")
        activity.set_xalign(1)
        activity.set_can_target(False)
        activity.add_css_class("mochi-bond-activity")
        header.append(activity)

        bar = Gtk.ProgressBar()
        bar.set_fraction(0.0)
        bar.set_show_text(False)
        bar.set_can_target(False)
        bar.set_focusable(False)
        bar.set_size_request(164, 7)
        bar.add_css_class("mochi-bond-progress")

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_can_target(False)

        xp = Gtk.Label(label="0 / 480 XP")
        xp.set_xalign(0)
        xp.set_hexpand(True)
        xp.set_can_target(False)
        xp.add_css_class("mochi-bond-xp")
        footer.append(xp)

        gain = Gtk.Label(label="")
        gain.set_xalign(1)
        gain.set_can_target(False)
        gain.add_css_class("mochi-bond-gain-text")
        footer.append(gain)

        normal.append(header)
        normal.append(bar)
        normal.append(footer)

        celebration = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        celebration.set_halign(Gtk.Align.CENTER)
        celebration.set_can_target(False)
        celebration.set_visible(False)
        celebration.add_css_class("mochi-level-up-content")

        level_up_title = Gtk.Label(label="✦  LEVEL UP!  ✦")
        level_up_title.set_halign(Gtk.Align.CENTER)
        level_up_title.set_can_target(False)
        level_up_title.add_css_class("mochi-level-up-title")
        celebration.append(level_up_title)

        level_up_level = Gtk.Label(label="Bond Level 2")
        level_up_level.set_halign(Gtk.Align.CENTER)
        level_up_level.set_can_target(False)
        level_up_level.add_css_class("mochi-level-up-level")
        celebration.append(level_up_level)

        level_up_subtitle = Gtk.Label(label="Your bond grew stronger")
        level_up_subtitle.set_halign(Gtk.Align.CENTER)
        level_up_subtitle.set_can_target(False)
        level_up_subtitle.add_css_class("mochi-level-up-subtitle")
        celebration.append(level_up_subtitle)

        card.append(normal)
        card.append(celebration)
        shell.append(card)
        return (
            shell,
            card,
            normal,
            celebration,
            level,
            activity,
            bar,
            xp,
            gain,
            level_up_title,
            level_up_level,
            level_up_subtitle,
        )

    @property
    def active(self) -> bool:
        return self._active

    @property
    def visible(self) -> bool:
        return bool(self._window.get_visible() or self._popover.get_visible())

    @property
    def level_up_active(self) -> bool:
        return self._level_up_active

    @property
    def emote_unlock_active(self) -> bool:
        return self._emote_unlock_active

    @property
    def presentation_active(self) -> bool:
        return self._level_up_active or self._emote_unlock_active

    def show_activity(self, state: BondState, activity: str) -> None:
        self._cancel_hide_timer()
        self._active = True
        self._activity = activity.strip() or "bonding"
        self.update(state)
        self.resume()

    def notify_xp_gain(self, state: BondState, amount: int) -> None:
        """Make a real XP award legible without creating another surface."""
        if amount <= 0:
            return

        self._cancel_hide_timer()
        self._active = True
        # The numeric award now floats beside Mochi in the sprite surface.
        # The HUD only pulses its bar/card so repeated +1 gains stay quiet.
        self._gain_text = ""
        self.update(state)

        if not self.presentation_active:
            self._set_gain_highlight(True)
            self._cancel_gain_timer()
            self._gain_source_id = GLib.timeout_add(
                self.GAIN_FLASH_MS,
                self._finish_gain_flash,
            )
        self.resume()

    def show_level_up(self, state: BondState, *, previous_level: int) -> None:
        """Present a distinct, unmistakable relationship-level milestone."""
        self._cancel_hide_timer()
        self._cancel_gain_timer()
        self._cancel_level_up_timer()
        self._set_gain_highlight(False)
        self._level_up_active = True
        self._emote_unlock_active = False
        self._level_up_previous_level = previous_level
        self._active = True
        for label in (self._level_up_title, self._popover_level_up_title):
            label.set_text("✦  LEVEL UP!  ✦")
        for label in (self._level_up_subtitle, self._popover_level_up_subtitle):
            label.set_text("Your bond grew stronger")
        self._set_level_up_content(True)
        self._set_level_up_highlight(True)
        self.update(state)
        self.resume()
        self._level_up_source_id = GLib.timeout_add(
            self.LEVEL_UP_DISPLAY_MS,
            self._finish_level_up,
        )

    def show_emote_unlock(self, emote: EmoteDefinition) -> None:
        """Reveal a newly learned idle emote after the level-up card."""
        self._cancel_hide_timer()
        self._cancel_gain_timer()
        self._cancel_level_up_timer()
        self._set_gain_highlight(False)
        self._level_up_active = False
        self._emote_unlock_active = True
        self._level_up_previous_level = None
        self._active = True
        self._set_level_up_content(True)
        self._set_level_up_highlight(True)

        for label in (self._level_up_title, self._popover_level_up_title):
            label.set_text("✦  NEW EMOTE UNLOCKED!  ✦")
        for label in (self._level_up_level, self._popover_level_up_level):
            label.set_text(emote.label)
        subtitle = f"{emote.rarity.upper()} · Mochi learned a new idle mood"
        for label in (self._level_up_subtitle, self._popover_level_up_subtitle):
            label.set_text(subtitle)

        self.resume()
        self._level_up_source_id = GLib.timeout_add(
            self.EMOTE_UNLOCK_DISPLAY_MS,
            self._finish_emote_unlock,
        )

    def update(self, state: BondState, activity: str | None = None) -> None:
        self._state = BondState(level=state.level, xp=state.xp)
        if activity is not None:
            self._activity = activity.strip() or "bonding"

        level_text = f"Bond Lv. {self._state.level}"
        activity_text = self._activity
        xp_text = f"{self._state.xp} / {self._state.xp_required} XP"
        gain_text = self._gain_text

        if not self._emote_unlock_active:
            level_up_level_text = f"Bond Level {self._state.level}"
            for label in (self._level_up_level, self._popover_level_up_level):
                label.set_text(level_up_level_text)

        for label in (self._level_label, self._popover_level_label):
            label.set_text(level_text)
        for label in (self._activity_label, self._popover_activity_label):
            label.set_text(activity_text)
        for label in (self._xp_label, self._popover_xp_label):
            label.set_text(xp_text)
        for label in (self._gain_label, self._popover_gain_label):
            label.set_text(gain_text)

        for bar in (self._bar, self._popover_bar):
            bar.set_fraction(self._state.progress_fraction)
            bar.set_tooltip_text(
                f"{self._state.xp}/{self._state.xp_required} bond XP "
                f"({self._state.progress_percent}%)"
            )

        if self.visible:
            self.update_position()

    def dismiss(self) -> None:
        """Immediately retire the HUD without changing bond progression."""
        was_presentation = self.presentation_active
        self._cancel_hide_timer()
        self._cancel_gain_timer()
        self._cancel_level_up_timer()
        self._active = False
        self._level_up_active = False
        self._emote_unlock_active = False
        self._level_up_previous_level = None
        self._gain_text = ""
        self._set_gain_highlight(False)
        self._set_level_up_highlight(False)
        self._set_level_up_content(False)
        self._hide_surfaces()
        if was_presentation:
            self._notify_level_up_finished()

    def finish_activity(self, delay_seconds: float = 1.6) -> None:
        if not self._active:
            return
        # The level-up timer already owns the celebration lifetime. Avoid a
        # second GLib hide timer racing the same presentation.
        if self.presentation_active:
            return
        self._cancel_hide_timer()
        delay = max(0.0, delay_seconds)
        delay_ms = max(1, round(delay * 1000))
        self._hide_source_id = GLib.timeout_add(delay_ms, self._finish_hide)

    def suspend(self) -> None:
        """Temporarily yield the shared anchor to a speech bubble."""
        self._hide_surfaces()

    def resume(self) -> None:
        if not self._active:
            return
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

    def update_position(self) -> None:
        if not self.visible:
            return
        if self._mode == "x11":
            self._position_x11()
        elif self._mode == "wayland":
            self._position_wayland_anchor()

    def destroy(self) -> None:
        was_presentation = self.presentation_active
        self._cancel_hide_timer()
        self._cancel_gain_timer()
        self._cancel_level_up_timer()
        self._active = False
        self._level_up_active = False
        self._hide_surfaces()
        if was_presentation:
            self._notify_level_up_finished()
        self._window.destroy()
        self._popover.unparent()

    def _finish_hide(self) -> bool:
        self._hide_source_id = None
        self._active = False
        self._hide_surfaces()
        return GLib.SOURCE_REMOVE

    def _finish_gain_flash(self) -> bool:
        self._gain_source_id = None
        self._set_gain_highlight(False)
        if not self.presentation_active:
            self._gain_text = ""
            self.update(self._state)
        return GLib.SOURCE_REMOVE

    def _finish_level_up(self) -> bool:
        self._level_up_source_id = None
        self._level_up_active = False
        self._emote_unlock_active = False
        self._level_up_previous_level = None
        self._set_level_up_highlight(False)
        self._set_level_up_content(False)
        self._gain_text = ""
        self._active = False
        self._hide_surfaces()
        self._notify_level_up_finished()
        return GLib.SOURCE_REMOVE

    def _finish_emote_unlock(self) -> bool:
        self._level_up_source_id = None
        self._emote_unlock_active = False
        self._set_level_up_highlight(False)
        self._set_level_up_content(False)
        self._gain_text = ""
        self._active = False
        self._hide_surfaces()
        self._notify_level_up_finished()
        return GLib.SOURCE_REMOVE

    def _notify_level_up_finished(self) -> None:
        callback = self._on_level_up_finished
        if callback is not None:
            callback()

    def _hide_surfaces(self) -> None:
        if self._window.get_visible():
            self._window.hide()
        if self._popover.get_visible():
            self._popover.popdown()
        self._mode = None

    def _cancel_hide_timer(self) -> None:
        self._remove_source("_hide_source_id")

    def _cancel_gain_timer(self) -> None:
        self._remove_source("_gain_source_id")

    def _cancel_level_up_timer(self) -> None:
        self._remove_source("_level_up_source_id")

    def _remove_source(self, attribute: str) -> None:
        source_id = getattr(self, attribute, None)
        setattr(self, attribute, None)
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _set_level_up_content(self, enabled: bool) -> None:
        for normal in (self._normal_content, self._popover_normal_content):
            normal.set_visible(not enabled)
        for celebration in (
            self._level_up_content,
            self._popover_level_up_content,
        ):
            celebration.set_visible(enabled)

    def _set_gain_highlight(self, enabled: bool) -> None:
        self._set_css_class(
            "mochi-bond-gain",
            enabled,
            self._card,
            self._popover_card,
            self._bar,
            self._popover_bar,
        )

    def _set_level_up_highlight(self, enabled: bool) -> None:
        self._set_css_class(
            "mochi-bond-level-up",
            enabled,
            self._card,
            self._popover_card,
            self._level_label,
            self._popover_level_label,
            self._activity_label,
            self._popover_activity_label,
            self._bar,
            self._popover_bar,
            self._gain_label,
            self._popover_gain_label,
            self._level_up_title,
            self._popover_level_up_title,
            self._level_up_level,
            self._popover_level_up_level,
            self._level_up_subtitle,
            self._popover_level_up_subtitle,
        )

    @staticmethod
    def _set_css_class(css_class: str, enabled: bool, *widgets: Gtk.Widget) -> None:
        for widget in widgets:
            if enabled:
                widget.add_css_class(css_class)
            else:
                widget.remove_css_class(css_class)

    def _visible_anchor_bounds(
        self, owner_width: int, owner_height: int
    ) -> tuple[float, float, float, float]:
        atlas = getattr(self._anchor, "atlas", None)
        if atlas is not None and hasattr(atlas, "visible_bounds"):
            reference_frame = replace(
                ANIMATIONS["idle"].frames[0],
                horizontal_offset=0.0,
                vertical_offset=0.0,
            )
            try:
                return atlas.visible_bounds(reference_frame, owner_width, owner_height)
            except Exception as exc:
                self._logger.debug(
                    "Bond overlay visible-bounds lookup failed; using widget bounds: %s",
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
        visible_x, visible_y, visible_width, _ = self._visible_anchor_bounds(
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
            self.suspend()
            return

        owner_x, owner_y = owner_position
        owner_width = max(1, self._owner.get_width())
        owner_height = max(1, self._owner.get_height())
        width = self._window.get_width()
        height = self._window.get_height()
        if width <= 1:
            width = 206
        if height <= 1:
            height = 76

        owner_scale = self._x11_coordinate_scale(self._owner)
        overlay_scale = self._x11_coordinate_scale(self._window)
        visible_x, visible_y, visible_width, _ = self._visible_anchor_bounds(
            owner_width, owner_height
        )
        visible_x *= owner_scale
        visible_y *= owner_scale
        visible_width *= owner_scale
        overlay_width = width * overlay_scale
        overlay_height = height * overlay_scale
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
            scaled = [
                (
                    geometry.x * owner_scale,
                    geometry.y * owner_scale,
                    geometry.width * owner_scale,
                    geometry.height * owner_scale,
                )
                for geometry in geometries
            ]
            monitor_x, monitor_y, monitor_width, _ = min(
                scaled,
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
            right = owner_x + owner_width * owner_scale + overlay_width

        x = round(center_x - overlay_width / 2)
        y = round(visible_top - overlay_height - gap)
        x = max(round(left), min(x, max(round(left), round(right - overlay_width))))
        y = max(round(top), y)
        move_window(self._window, x, y)

    def _on_window_map(self, _window: Gtk.Window) -> None:
        request_keep_above(self._window)
        GLib.idle_add(self._position_x11)

    @staticmethod
    def _install_css(display: Gdk.Display) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(
            """
            window.mochi-bond-window {
                background: transparent;
            }
            .mochi-bond-shell {
                background: transparent;
            }
            .mochi-bond-card {
                background: alpha(@window_bg_color, 0.97);
                color: @window_fg_color;
                border: 1px solid alpha(#79c98b, 0.44);
                border-radius: 11px;
                box-shadow: 0 5px 18px alpha(black, 0.16);
                padding: 8px 10px;
            }
            .mochi-bond-card.mochi-bond-gain {
                border-color: alpha(#8fe29e, 0.76);
                box-shadow: 0 4px 16px alpha(#79c98b, 0.18);
            }
            .mochi-bond-card.mochi-bond-level-up {
                background: alpha(@window_bg_color, 0.98);
                border: 2px solid alpha(#a8f2b4, 0.92);
                border-radius: 14px;
                box-shadow: 0 7px 24px alpha(#79c98b, 0.34);
                padding: 10px 14px;
            }
            .mochi-level-up-content {
                min-width: 172px;
            }
            .mochi-level-up-title {
                color: #79c98b;
                font-size: 10px;
                font-weight: 800;
            }
            .mochi-level-up-level {
                font-size: 17px;
                font-weight: 800;
            }
            .mochi-level-up-subtitle {
                color: alpha(@window_fg_color, 0.68);
                font-size: 9px;
            }
            .mochi-bond-level {
                font-size: 11px;
                font-weight: 700;
            }
            .mochi-bond-level.mochi-bond-level-up {
                font-weight: 800;
            }
            .mochi-bond-activity {
                color: alpha(@window_fg_color, 0.62);
                font-size: 9px;
            }
            .mochi-bond-activity.mochi-bond-level-up {
                color: #79c98b;
                font-weight: 800;
            }
            .mochi-bond-xp {
                color: alpha(@window_fg_color, 0.62);
                font-size: 9px;
            }
            .mochi-bond-gain-text {
                color: #79c98b;
                font-size: 9px;
                font-weight: 700;
            }
            .mochi-bond-gain-text.mochi-bond-level-up {
                font-weight: 800;
            }
            .mochi-level-up-title.mochi-bond-level-up {
                color: #8fe29e;
            }
            progressbar.mochi-bond-progress trough {
                min-height: 7px;
                border-radius: 999px;
                background: alpha(@window_fg_color, 0.12);
            }
            progressbar.mochi-bond-progress progress {
                min-height: 7px;
                border-radius: 999px;
                background: #79c98b;
            }
            progressbar.mochi-bond-progress.mochi-bond-gain progress {
                background: #95e5a2;
            }
            progressbar.mochi-bond-progress.mochi-bond-level-up progress {
                background: #a8f2b4;
            }
            popover.mochi-bond-popover > contents {
                background: transparent;
                border: none;
                box-shadow: none;
                padding: 0;
            }
            popover.mochi-bond-popover > arrow {
                background: alpha(@window_bg_color, 0.97);
                border-color: alpha(#79c98b, 0.44);
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
