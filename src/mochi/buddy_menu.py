"""Menu construction and menu-action orchestration for Mochi's buddy widget.

This mixin intentionally owns user/developer menu UI only. Core animation,
dragging, activity detection, and behavior state remain outside this module.
"""

from __future__ import annotations

from collections.abc import Callable
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.config import ConfigStore
from mochi.menu_window import MenuWindow
from mochi.sound import SoundEvent
from mochi.state import MochiState


class BuddyMenuMixin:
    """Build and coordinate Mochi's context and developer menus."""

    def _initialize_context_menu_layout(
        self,
        menu: MenuWindow,
        content: Gtk.Box,
    ) -> None:
        """Create the single owner for user-menu ordering and layout metadata."""
        self._context_menu_layout_window = menu
        self._context_menu_content = content
        self._context_menu_rows: dict[str, Gtk.Widget] = {}
        self._context_menu_row_order: list[str] = []
        self._context_menu_animated_row_ids: set[str] = set()
        self._context_menu_animated_rows: tuple[Gtk.Widget, ...] = ()

    def _register_context_menu_row(
        self,
        row_id: str,
        widget: Gtk.Widget,
        *,
        after: str | None = None,
        before: str | None = None,
        animated: bool = True,
    ) -> None:
        """Register and place one user-menu row through the shared layout seam."""
        if not row_id:
            raise ValueError("Context-menu row ID must not be empty")
        if row_id in self._context_menu_rows:
            raise ValueError(f"Context-menu row already registered: {row_id!r}")
        if after is not None and before is not None:
            raise ValueError(
                "Context-menu row cannot specify both 'after' and 'before'"
            )

        anchor_id = after if after is not None else before
        if anchor_id is not None and anchor_id not in self._context_menu_rows:
            raise KeyError(f"Unknown context-menu row: {anchor_id!r}")

        if after is not None:
            insert_at = self._context_menu_row_order.index(after) + 1
        elif before is not None:
            insert_at = self._context_menu_row_order.index(before)
        else:
            insert_at = len(self._context_menu_row_order)

        if insert_at == len(self._context_menu_row_order):
            self._context_menu_content.append(widget)
        elif insert_at == 0:
            self._context_menu_content.prepend(widget)
        else:
            previous_id = self._context_menu_row_order[insert_at - 1]
            previous_widget = self._context_menu_rows[previous_id]
            self._context_menu_content.insert_child_after(widget, previous_widget)

        self._context_menu_rows[row_id] = widget
        self._context_menu_row_order.insert(insert_at, row_id)
        if animated:
            self._context_menu_animated_row_ids.add(row_id)
        self._recalculate_context_menu_layout()

    def _get_context_menu_row(self, row_id: str) -> Gtk.Widget:
        """Return a registered user-menu row by its stable layout ID."""
        return self._context_menu_rows[row_id]

    def _recalculate_context_menu_layout(self) -> None:
        """Synchronize animation order and the menu's pre-allocation size."""
        self._context_menu_animated_rows = tuple(
            self._context_menu_rows[row_id]
            for row_id in self._context_menu_row_order
            if row_id in self._context_menu_animated_row_ids
        )

        preferred_height = max(
            (
                self.CONTEXT_MENU_MIN_HEIGHTS.get(
                    row_id,
                    self.CONTEXT_MENU_BASE_HEIGHT,
                )
                for row_id in self._context_menu_row_order
            ),
            default=self.CONTEXT_MENU_BASE_HEIGHT,
        )
        unknown_rows = set(self._context_menu_row_order).difference(
            self.CONTEXT_MENU_BASE_SIZED_ROWS,
            self.CONTEXT_MENU_MIN_HEIGHTS,
        )
        preferred_height += (
            len(unknown_rows) * self.CONTEXT_MENU_UNKNOWN_ROW_HEIGHT
        )
        self._context_menu_layout_window.set_preferred_size(
            self.CONTEXT_MENU_WIDTH,
            preferred_height,
        )

    def _build_context_menu(self) -> MenuWindow:
        """Build Mochi's intentionally tiny user-facing right-click menu."""
        popover = MenuWindow(
            owner=self._window,
            anchor_widget=self,
            preferred_width=self.CONTEXT_MENU_WIDTH,
            preferred_height=self.CONTEXT_MENU_BASE_HEIGHT,
            follow_owner=True,
            dismiss_on_focus_loss=True,
            logger=self._logger,
        )
        popover.add_css_class("mochi-user-menu")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("mochi-menu-card")
        card.set_margin_top(12)
        card.set_margin_bottom(12)
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_size_request(220, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sprout = Gtk.Label(label="🌱")
        sprout.add_css_class("mochi-menu-sprout")
        header.append(sprout)

        header_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label="Mochi")
        title.set_xalign(0)
        title.add_css_class("mochi-menu-title")
        subtitle = Gtk.Label(label="your tiny desktop buddy")
        subtitle.set_xalign(0)
        subtitle.add_css_class("mochi-menu-subtitle")
        header_text.append(title)
        header_text.append(subtitle)
        header.append(header_text)
        self._initialize_context_menu_layout(popover, card)
        self._register_context_menu_row("header", header, animated=False)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self._register_context_menu_row("separator", separator, animated=False)

        self._sleep_button, self._sleep_label = self._make_menu_button(
            "Sleep",
            "weather-clear-night-symbolic",
            self._toggle_sleep,
        )
        self._register_context_menu_row("sleep", self._sleep_button)

        close_button, _ = self._make_menu_button(
            "Close",
            "window-close-symbolic",
            self._quit_from_context_menu,
        )
        close_button.add_css_class("mochi-menu-secondary")
        self._register_context_menu_row("close", close_button)

        popover.set_child(card)
        return popover

    def _build_developer_menu(self) -> MenuWindow:
        """Developer-only controls opened by Mochi's private global shortcut."""
        popover = MenuWindow(
            owner=self._window,
            anchor_widget=self,
            preferred_width=332,
            preferred_height=680,
            follow_owner=False,
            logger=self._logger,
        )
        popover.add_css_class("mochi-dev-menu")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("mochi-menu-card")
        card.set_margin_top(12)
        card.set_margin_bottom(12)
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_size_request(308, -1)

        drag_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        drag_header.add_css_class("mochi-dev-drag-handle")

        title = Gtk.Label(label="Mochi Lab  ✦")
        title.set_xalign(0)
        title.add_css_class("mochi-menu-title")
        drag_header.append(title)

        subtitle = Gtk.Label(label="Developer controls  ·  drag here to move")
        subtitle.set_xalign(0)
        subtitle.add_css_class("mochi-menu-subtitle")
        drag_header.append(subtitle)
        card.append(drag_header)
        popover.set_drag_handle(drag_header)

        animated_rows: list[Gtk.Widget] = []
        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        actions_label = Gtk.Label(label="Actions")
        actions_label.set_xalign(0)
        actions_label.add_css_class("mochi-menu-section")
        card.append(actions_label)

        walk_button, _ = self._make_menu_button("Take a stroll", "go-next-symbolic", self._test_walk)
        card.append(walk_button)
        animated_rows.append(walk_button)

        heart_button, _ = self._make_menu_button("Say hi", "emblem-favorite-symbolic", self._test_heart_emote)
        card.append(heart_button)
        animated_rows.append(heart_button)

        computer_button, _ = self._make_menu_button("Laptop time", "computer-symbolic", self._test_computer_emote)
        card.append(computer_button)
        animated_rows.append(computer_button)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        appearance_label = Gtk.Label(label="Appearance")
        appearance_label.set_xalign(0)
        appearance_label.add_css_class("mochi-menu-section")
        card.append(appearance_label)

        size_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        size_row.add_css_class("mochi-setting-row")
        size_label = Gtk.Label(label="Size")
        size_label.set_xalign(0)
        size_label.set_hexpand(True)
        size_row.append(size_label)
        size_value = Gtk.Label(label=f"{self._size}px")
        size_value.add_css_class("mochi-menu-value")
        size_row.append(size_value)
        card.append(size_row)
        animated_rows.append(size_row)

        size_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            ConfigStore.MIN_SIZE,
            ConfigStore.MAX_SIZE,
            ConfigStore.SIZE_STEP,
        )
        size_scale.set_value(self._size)
        size_scale.set_draw_value(False)
        size_scale.set_hexpand(True)
        size_scale.add_css_class("mochi-menu-scale")
        size_scale.connect("value-changed", self._change_size)
        size_scale.connect("value-changed", lambda scale: size_value.set_text(
                f"{round(scale.get_value() / ConfigStore.SIZE_STEP) * ConfigStore.SIZE_STEP}px"
            ))
        card.append(size_scale)
        animated_rows.append(size_scale)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        audio_label = Gtk.Label(label="Audio")
        audio_label.set_xalign(0)
        audio_label.add_css_class("mochi-menu-section")
        card.append(audio_label)

        sound_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sound_row.add_css_class("mochi-setting-row")
        sound_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
        sound_row.append(sound_icon)
        sound_label = Gtk.Label(label="Sound")
        sound_label.set_xalign(0)
        sound_label.set_hexpand(True)
        sound_row.append(sound_label)
        sound_switch = Gtk.Switch()
        sound_switch.set_valign(Gtk.Align.CENTER)
        sound_switch.set_active(not self._sound.muted)
        sound_switch.connect("notify::active", self._change_sound_enabled)
        sound_row.append(sound_switch)
        card.append(sound_row)
        animated_rows.append(sound_row)

        volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        volume_scale.set_value(self._sound.volume * 100)
        volume_scale.set_draw_value(False)
        volume_scale.add_css_class("mochi-menu-scale")
        volume_scale.connect("value-changed", self._change_volume)
        card.append(volume_scale)
        animated_rows.append(volume_scale)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        tuning_label = Gtk.Label(label="Interaction tuning")
        tuning_label.set_xalign(0)
        tuning_label.add_css_class("mochi-menu-section")
        card.append(tuning_label)

        tuning_grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        tuning_grid.add_css_class("mochi-tuning-grid")
        tuning_values = (
            ("Start drag px", "drag_start_distance_px", 1.0, 12.0, 0.5, 1),
            ("Soft threshold", "drag_soft_enter_threshold", 0.0, 1.0, 0.01, 2),
            ("Medium enter", "drag_medium_enter_threshold", 0.0, 1.0, 0.01, 2),
            ("Medium exit", "drag_medium_exit_threshold", 0.0, 1.0, 0.01, 2),
            ("Full-sway px/s", "drag_heavy_velocity_px_per_second", 100.0, 2_000.0, 25.0, 0),
            ("Drag dwell ms", "drag_state_dwell_ms", 0.0, 250.0, 10.0, 0),
            ("Heart cooldown s", "hover_heart_cooldown_seconds", 0.0, 10.0, 0.25, 2),
            ("Pickup frame ms", "pickup_frame_duration_ms", 10.0, 100.0, 5.0, 0),
        )
        for row, values in enumerate(tuning_values):
            label, attribute, lower, upper, step, digits = values
            self._append_tuning_control(tuning_grid, row, label, attribute, lower, upper, step, digits)
        card.append(tuning_grid)
        animated_rows.append(tuning_grid)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        system_label = Gtk.Label(label="System")
        system_label.set_xalign(0)
        system_label.add_css_class("mochi-menu-section")
        card.append(system_label)

        reset_button, _ = self._make_menu_button("Reset position", "view-refresh-symbolic", self._reset_position)
        card.append(reset_button)
        animated_rows.append(reset_button)

        quit_button, _ = self._make_menu_button("Quit Mochi", "application-exit-symbolic", self._quit, destructive=True)
        card.append(quit_button)
        animated_rows.append(quit_button)

        hint = Gtk.Label(label="Ctrl + Alt + Shift + M")
        hint.set_xalign(0)
        hint.add_css_class("mochi-menu-hint")
        card.append(hint)
        animated_rows.append(hint)

        self._developer_menu_content = card
        self._developer_menu_animated_rows = tuple(animated_rows)
        popover.set_child(card)
        return popover

    def _make_menu_button(
        self,
        label: str,
        icon_name: str,
        callback,
        *,
        destructive: bool = False,
    ) -> tuple[Gtk.Button, Gtk.Label]:
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        if destructive:
            button.add_css_class("mochi-menu-danger")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class("mochi-menu-icon")
        row.append(icon)
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)
        button.set_child(row)
        button.connect("clicked", callback)
        return button, text

    def _append_tuning_control(
        self,
        grid: Gtk.Grid,
        row: int,
        label: str,
        attribute: str,
        lower: float,
        upper: float,
        step: float,
        digits: int,
    ) -> None:
        value_label = Gtk.Label(label=label)
        value_label.set_xalign(0)
        spin = Gtk.SpinButton.new_with_range(lower, upper, step)
        spin.set_digits(digits)
        spin.set_value(float(getattr(self._tuning, attribute)))
        spin.connect(
            "value-changed",
            lambda control, name=attribute: self._change_tuning(
                name, control.get_value()
            ),
        )
        self._tuning_controls[attribute] = spin
        grid.attach(value_label, 0, row, 1, 1)
        grid.attach(spin, 1, row, 1, 1)

    def _change_tuning(self, attribute: str, value: float) -> None:
        if attribute in ("drag_state_dwell_ms", "pickup_frame_duration_ms"):
            value = round(value)
        setattr(self._tuning, attribute, value)
        selector = self._drag_motion.pose_selector
        if attribute == "drag_soft_enter_threshold":
            selector.soft_enter_threshold = value
        elif attribute == "drag_medium_enter_threshold":
            selector.medium_enter_threshold = value
            self._tuning_controls[
                "drag_medium_exit_threshold"
            ].get_adjustment().set_upper(max(0.0, value - 0.01))
        elif attribute == "drag_medium_exit_threshold":
            selector.medium_exit_threshold = value
            self._tuning_controls[
                "drag_medium_enter_threshold"
            ].get_adjustment().set_lower(min(1.0, value + 0.01))
        elif attribute == "drag_heavy_velocity_px_per_second":
            self._drag_motion.max_velocity = value
        elif attribute == "drag_state_dwell_ms":
            selector.dwell_ms = value
        self._logger.debug("Tuning changed: %s=%s", attribute, value)

    def _change_size(self, scale: Gtk.Scale) -> None:
        size = (
            round(scale.get_value() / ConfigStore.SIZE_STEP)
            * ConfigStore.SIZE_STEP
        )
        if size == self._size:
            return
        self._size = size
        self.set_content_width(size)
        self.set_content_height(size)
        self._window.set_default_size(size, size)
        self._config.save_size(size)
        self._placement.move_to(self._placement.position.x, self._placement.position.y)
        self.queue_draw()

    def _change_volume(self, scale: Gtk.Scale) -> None:
        volume = scale.get_value() / 100
        self._sound.set_volume(volume)
        self._config.save_volume(volume)

    def _change_muted(self, toggle: Gtk.CheckButton) -> None:
        muted = toggle.get_active()
        self._sound.set_muted(muted)
        self._config.save_muted(muted)

    def _change_sound_enabled(self, switch: Gtk.Switch, _pspec=None) -> None:
        muted = not switch.get_active()
        self._sound.set_muted(muted)
        self._config.save_muted(muted)

    def _show_context_menu(
        self, _gesture: Gtk.GestureClick, _presses: int, x: float, y: float
    ) -> None:
        # Right-click is a true toggle: a second right-click on Mochi closes
        # the already-open user menu instead of re-presenting/repositioning it.
        if self._context_menu.get_visible():
            self._context_menu.popdown()
            return
        if self._developer_menu.get_visible():
            self._developer_menu.popdown()
        # Secondary-click is UI-only. It must never trigger/cancel a Mochi
        # emote, stop walking, force idle, or feed the primary-click reaction
        # pipeline. The popover may animate; Mochi himself does not.
        self._cancel_hover_heart()
        self._sleep_label.set_text(
            "Wake up" if self.state.current is MochiState.SLEEPING else "Sleep"
        )
        rectangle = Gdk.Rectangle()
        rectangle.x = round(x)
        rectangle.y = round(y)
        rectangle.width = 1
        rectangle.height = 1
        self._context_menu.set_pointing_to(rectangle)
        self._context_menu_open = True
        self._context_menu.popup()
        self._sound.play(SoundEvent.MENU_OPEN)
        self._animate_menu_open(
            self._context_menu_content, self._context_menu_animated_rows
        )
        self._logger.debug("Context menu opened at (%d, %d)", rectangle.x, rectangle.y)

    def _show_developer_menu(self) -> None:
        if self._preview_mode:
            return
        if self._developer_menu.get_visible():
            self._developer_menu.popdown()
            return
        if self._context_menu.get_visible():
            self._context_menu.popdown()
        self._mark_interaction()
        self._cancel_active_emote()
        if self.state.current is MochiState.WALKING:
            self._cancel_walk()
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")

        rectangle = Gdk.Rectangle()
        rectangle.x = max(1, self.get_width() // 2)
        rectangle.y = max(1, self.get_height() // 2)
        rectangle.width = 1
        rectangle.height = 1
        self._developer_menu.set_pointing_to(rectangle)
        self._context_menu_open = True
        self._developer_menu.popup()
        self._animate_menu_open(
            self._developer_menu_content, self._developer_menu_animated_rows
        )
        self._logger.debug("Developer menu opened from secret shortcut")

    def _animate_menu_open(
        self, content: Gtk.Widget, rows: tuple[Gtk.Widget, ...]
    ) -> None:
        """Quick ease-out lift + staggered fade without resizing the popover."""
        self._menu_animation_serial = getattr(self, "_menu_animation_serial", 0) + 1
        serial = self._menu_animation_serial
        started = time.monotonic()
        duration = 0.18
        start_margin = 20
        end_margin = 12
        content.set_opacity(0.0)
        content.set_margin_top(start_margin)
        for row in rows:
            row.set_opacity(0.0)

        def animate() -> bool:
            if serial != self._menu_animation_serial:
                return GLib.SOURCE_REMOVE
            progress = min(1.0, (time.monotonic() - started) / duration)
            eased = 1.0 - (1.0 - progress) ** 3
            content.set_opacity(eased)
            content.set_margin_top(round(start_margin + (end_margin - start_margin) * eased))
            for index, row in enumerate(rows):
                delay = min(0.45, index * 0.045)
                row_progress = max(0.0, min(1.0, (progress - delay) / max(0.01, 1.0 - delay)))
                row.set_opacity(1.0 - (1.0 - row_progress) ** 2)
            if progress >= 1.0:
                content.set_opacity(1.0)
                content.set_margin_top(end_margin)
                for row in rows:
                    row.set_opacity(1.0)
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(16, animate)

    def _quit_from_context_menu(self, _button: Gtk.Button) -> None:
        """Close the user menu first, then quit Mochi on the next idle turn."""
        self._close_context_menu_then(self._quit_application)

    def _toggle_sleep(self, _button: Gtk.Button) -> None:
        def toggle() -> None:
            if self.state.current is MochiState.SLEEPING:
                self._wake_up()
            else:
                self._begin_sleep()
            self.queue_draw()

        self._close_context_menu_then(toggle)

    def _test_walk(self, _button: Gtk.Button) -> None:
        def start_walk() -> None:
            if self.state.current is MochiState.IDLE:
                self._start_walk()

        self._close_developer_menu_then(start_walk)

    def _test_heart_emote(self, _button: Gtk.Button) -> None:
        self._close_developer_menu_then(
            lambda: self._start_heart_emote(ignore_cooldown=True)
        )

    def _test_computer_emote(self, _button: Gtk.Button) -> None:
        self._close_developer_menu_then(self._start_computer_emote)

    def _reset_position(self, _button: Gtk.Button) -> None:
        def reset_position() -> None:
            self._config.reset_position()
            default = WindowPlacement.DEFAULT_POSITION
            self._placement.move_to(default.x, default.y)

        self._close_developer_menu_then(reset_position)

    def _close_context_menu_then(self, action: Callable[[], None]) -> None:
        self._pending_context_action = action
        self._context_menu.popdown()

    def _close_developer_menu_then(self, action: Callable[[], None]) -> None:
        self._pending_developer_action = action
        self._developer_menu.popdown()

    def _on_context_menu_closed(self, _popover: MenuWindow) -> None:
        self._menu_animation_serial = getattr(self, "_menu_animation_serial", 0) + 1
        self._context_menu_open = False
        self._logger.debug("Context menu closed")
        action = self._pending_context_action
        self._pending_context_action = None
        if action is not None:
            GLib.idle_add(self._dispatch_context_action, action)

    def _on_developer_menu_closed(self, _popover: MenuWindow) -> None:
        self._menu_animation_serial = getattr(self, "_menu_animation_serial", 0) + 1
        self._context_menu_open = False
        self._logger.debug("Developer menu closed")
        action = self._pending_developer_action
        self._pending_developer_action = None
        if action is not None:
            GLib.idle_add(self._dispatch_context_action, action)

    def _dispatch_context_action(self, action: Callable[[], None]) -> bool:
        action()
        return GLib.SOURCE_REMOVE

    def _quit_application(self) -> None:
        application = self._window.get_application()
        if application is not None:
            application.quit()

    def _quit_from_context_menu(self, _button: Gtk.Button) -> None:
        """Close the user menu first, then quit Mochi on the next idle turn."""
        self._close_context_menu_then(self._quit_application)
