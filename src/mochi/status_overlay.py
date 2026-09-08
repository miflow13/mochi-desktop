"""Single stateful GTK nameplate and contextual control surface for Mochi."""

from __future__ import annotations

from collections.abc import Callable
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.config import ConfigStore
from mochi.state import MochiState
from mochi.status import (
    ContextActionDispatcher,
    NameplateMode,
    NameplateState,
    friendly_state_label,
    sleep_action_label,
)


class MochiStatusOverlay(Gtk.Popover):
    HOVER_EXPAND_MS = 110
    LEAVE_GRACE_MS = 180
    FADE_MS = 130
    CSS = """
    .mochi-plate-popover { background: transparent; box-shadow: none; padding: 0; }
    .mochi-plate { background: rgba(35, 39, 37, 0.94); border: 1px solid rgba(255,255,255,0.16);
        border-radius: 12px; padding: 7px 10px; box-shadow: 0 5px 16px rgba(0,0,0,0.28); }
    .mochi-plate-name { color: #F4F7F5; font-weight: 700; font-size: 12px; }
    .mochi-plate-state { color: #A9DDB6; font-size: 10px; }
    .mochi-plate button { border-radius: 8px; padding: 5px 8px; }
    .mochi-plate-separator { background: rgba(255,255,255,0.12); min-height: 1px; }
    """

    def __init__(self, size: int, volume: float, muted: bool) -> None:
        super().__init__()
        self.add_css_class("mochi-plate-popover")
        self.set_has_arrow(True)
        self.set_position(Gtk.PositionType.TOP)
        self.set_autohide(False)
        self._state = NameplateState()
        self._behavior = MochiState.IDLE
        self._hover_source = self._leave_source = self._fade_source = 0
        self._fade_generation = 0
        self._actions: dict[str, Callable] = {}
        self._action_dispatcher = ContextActionDispatcher()

        self._panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self._panel.add_css_class("mochi-plate")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self._name = Gtk.Label(label="Mochi")
        self._name.add_css_class("mochi-plate-name")
        header.append(self._name)
        self._label = Gtk.Label(label="")
        self._label.add_css_class("mochi-plate-state")
        header.append(self._label)
        self._panel.append(header)

        self._menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self._sleep = self._button("Sleep", "sleep")
        self._menu.append(self._sleep)
        self._menu.append(self._button("Take a walk", "walk"))
        separator = Gtk.Separator()
        separator.add_css_class("mochi-plate-separator")
        self._menu.append(separator)
        self._size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, ConfigStore.MIN_SIZE, ConfigStore.MAX_SIZE, 64)
        self._size.set_value(size)
        self._size.set_draw_value(True)
        self._size.connect("value-changed", lambda scale: self._invoke("size", scale.get_value()))
        self._menu.append(self._size)
        self._mute = Gtk.CheckButton(label="Mute sounds")
        self._mute.set_active(muted)
        self._mute.connect("toggled", lambda button: self._invoke("mute", button.get_active()))
        self._menu.append(self._mute)
        self._volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        self._volume.set_value(volume * 100)
        self._volume.connect("value-changed", lambda scale: self._invoke("volume", scale.get_value() / 100))
        self._menu.append(self._volume)
        self._menu.append(self._button("Reset position", "reset"))
        self._menu.append(self._button("Quit Mochi", "quit"))
        self._panel.append(self._menu)
        self.set_child(self._panel)

        click = Gtk.GestureClick.new()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", lambda *_: self.open_context(self._behavior))
        header.add_controller(click)
        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", lambda *_: self._plate_enter())
        motion.connect("leave", lambda *_: self._plate_leave())
        self._panel.add_controller(motion)
        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._key_pressed)
        self.add_controller(keys)
        self.connect("closed", lambda *_: self._closed())
        self._render(NameplateMode.HIDDEN)

    def _button(self, label: str, action: str) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.add_css_class("flat")
        button.connect("clicked", lambda *_: self._invoke(action))
        return button

    def bind_actions(self, **actions: Callable) -> None:
        self._actions = actions

    def _invoke(self, action: str, *args: object) -> None:
        callback = self._actions.get(action)
        if action in ("size", "volume", "mute"):
            if callback is not None:
                callback(*args)
            return
        self._action_dispatcher.begin(self._close_context, callback, *args)

    @classmethod
    def install_css(cls, display: object) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(cls.CSS)
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def hover_enter(self, state: MochiState) -> None:
        self._behavior = state
        self._cancel("_leave_source")
        self._state.anchor_enter()
        self._show(NameplateMode.COMPACT)
        self._cancel("_hover_source")
        self._hover_source = GLib.timeout_add(self.HOVER_EXPAND_MS, self._expand_hover)

    def hover_leave(self) -> None:
        self._state.anchor_leave()
        self._schedule_hide()

    def open_context(self, state: MochiState) -> None:
        self._behavior = state
        self._state.open_context()
        self._sleep.set_label(sleep_action_label(state))
        self._cancel("_hover_source")
        self._cancel("_leave_source")
        self.set_autohide(True)
        self.set_focusable(True)
        self._show(NameplateMode.CONTEXT)
        self.grab_focus()

    def dismiss_for_click(self) -> None:
        if self._state.mode is NameplateMode.CONTEXT:
            self.close()

    def begin_drag(self) -> None:
        self._state.begin_drag()
        self._cancel("_hover_source")
        self._cancel("_leave_source")
        self._hide()

    def end_drag(self) -> None:
        pass

    def close(self) -> None:
        if self._state.mode is NameplateMode.CONTEXT:
            self._close_context()
            return
        mode = self._state.close()
        if mode is NameplateMode.HIDDEN:
            self._hide()
        else:
            self.set_autohide(False)
            self.set_focusable(False)
            self._show(mode)

    def _close_context(self) -> None:
        """Synchronously release the popover and every context interaction flag."""
        self._state.close_context()
        self._cancel("_hover_source")
        self._cancel("_leave_source")
        self._cancel("_fade_source")
        self._fade_generation += 1
        self.set_autohide(False)
        self.set_focusable(False)
        self.set_opacity(0.0)
        self.popdown()

    def _expand_hover(self) -> bool:
        self._hover_source = 0
        self._show(self._state.expand_hover())
        return GLib.SOURCE_REMOVE

    def _plate_enter(self) -> None:
        self._state.plate_enter()
        self._cancel("_leave_source")

    def _plate_leave(self) -> None:
        self._state.plate_leave()
        self._schedule_hide()

    def _schedule_hide(self) -> None:
        self._cancel("_leave_source")
        generation = self._state.generation
        self._leave_source = GLib.timeout_add(self.LEAVE_GRACE_MS, self._hide_if_current, generation)

    def _hide_if_current(self, generation: int) -> bool:
        self._leave_source = 0
        if self._state.can_hide(generation) and not self._state.hovered:
            self.close()
        return GLib.SOURCE_REMOVE

    def _show(self, mode: NameplateMode) -> None:
        self._render(mode)
        self.set_opacity(0.0 if not self.get_visible() else self.get_opacity())
        self.popup()
        self._animate(1.0)

    def _render(self, mode: NameplateMode) -> None:
        self._menu.set_visible(mode is NameplateMode.CONTEXT)
        self._label.set_visible(mode in (NameplateMode.HOVER, NameplateMode.CONTEXT, NameplateMode.STATUS))
        self._label.set_label(f"· {friendly_state_label(self._behavior)}")
        self._panel.set_size_request(210 if mode is NameplateMode.CONTEXT else -1, -1)

    def _hide(self) -> None:
        self._animate(0.0, self.popdown)

    def _animate(self, target: float, finished: Callable[[], None] | None = None) -> None:
        self._cancel("_fade_source")
        self._fade_generation += 1
        generation, start, began = self._fade_generation, self.get_opacity(), time.monotonic()
        def step() -> bool:
            if generation != self._fade_generation:
                return GLib.SOURCE_REMOVE
            progress = min(1.0, (time.monotonic() - began) / (self.FADE_MS / 1000))
            self.set_opacity(start + (target - start) * progress)
            if progress < 1.0:
                return GLib.SOURCE_CONTINUE
            self._fade_source = 0
            if finished:
                finished()
            return GLib.SOURCE_REMOVE
        self._fade_source = GLib.timeout_add(16, step)

    def _key_pressed(self, _controller: Gtk.EventControllerKey, keyval: int, *_: object) -> bool:
        if keyval == Gdk.KEY_Escape and self._state.mode is NameplateMode.CONTEXT:
            self.close()
            return True
        return False

    def _closed(self) -> None:
        if self._state.mode is NameplateMode.CONTEXT:
            self._state.close()
        if self._action_dispatcher.pending:
            GLib.idle_add(self._complete_context_action)

    def _complete_context_action(self) -> bool:
        self._action_dispatcher.complete()
        return GLib.SOURCE_REMOVE

    def _cancel(self, attribute: str) -> None:
        source = getattr(self, attribute)
        if source:
            GLib.source_remove(source)
            setattr(self, attribute, 0)
