"""The buddy widget: sprite rendering, behavior, and pointer interaction."""

from __future__ import annotations

import math
import logging
import random
import time
from dataclasses import replace

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.animation import AnimationPlayer
from mochi.behavior import choose_click_reaction
from mochi.config import ConfigStore
from mochi.sprites import ANIMATIONS, SpriteAtlas
from mochi.state import MochiState, StateMachine
from mochi.windowing import WindowPlacement


class Buddy(Gtk.DrawingArea):
    SIZE = 128
    TICK_MS = 16
    PREVIEW_ANIMATIONS = (
        "idle",
        "blink",
        "walk",
        "bounce",
        "squish",
        "excited",
        "sleep",
        "wake",
    )

    def __init__(
        self,
        window: Gtk.Window,
        placement: WindowPlacement,
        config: ConfigStore,
        preview_mode: bool = False,
    ) -> None:
        super().__init__()
        self._window = window
        self._placement = placement
        self._config = config
        self._preview_mode = preview_mode
        self._preview_index = 0
        self._logger = logging.getLogger(__name__)
        self.state = StateMachine()
        self.atlas = SpriteAtlas()
        self.player = AnimationPlayer(on_finished=self._finish_reaction)
        self.player.play(ANIMATIONS["idle"])
        self._current_animation = "idle"
        self._pending_animation: str | None = None
        self._last_interaction = time.monotonic()
        self._walk_origin_x = 0
        self._walk_target_x = 0
        self._walk_elapsed_ms = 0
        self._press: tuple[float, float] | None = None
        self._drag_origin = placement.position
        self._drag_started = False

        self.set_content_width(self.SIZE)
        self.set_content_height(self.SIZE)
        self.set_draw_func(self._draw)

        click = Gtk.GestureClick.new()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_pressed)
        click.connect("released", self._on_released)
        self.add_controller(click)

        context_click = Gtk.GestureClick.new()
        context_click.set_button(Gdk.BUTTON_SECONDARY)
        context_click.connect("pressed", self._show_context_menu)
        self.add_controller(context_click)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)

        drag = Gtk.GestureDrag.new()
        drag.set_button(Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

        GLib.timeout_add(self.TICK_MS, self._tick)
        if not self._preview_mode:
            self._schedule_idle_action()

        self._context_menu = self._build_context_menu()

    def _build_context_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.set_parent(self)
        popover.add_css_class("menu")

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu_box.set_margin_top(6)
        menu_box.set_margin_bottom(6)
        menu_box.set_margin_start(6)
        menu_box.set_margin_end(6)

        title = Gtk.Label(label="Mochi")
        title.add_css_class("heading")
        menu_box.append(title)

        self._sleep_button = Gtk.Button(label="Sleep")
        self._sleep_button.add_css_class("flat")
        self._sleep_button.connect("clicked", self._toggle_sleep)
        menu_box.append(self._sleep_button)

        reset_button = Gtk.Button(label="Reset Position")
        reset_button.add_css_class("flat")
        reset_button.connect("clicked", self._reset_position)
        menu_box.append(reset_button)

        quit_button = Gtk.Button(label="Quit Mochi")
        quit_button.add_css_class("flat")
        quit_button.connect("clicked", self._quit)
        menu_box.append(quit_button)
        popover.set_child(menu_box)
        return popover

    def _show_context_menu(
        self, _gesture: Gtk.GestureClick, _presses: int, x: float, y: float
    ) -> None:
        self._mark_interaction()
        self._sleep_button.set_label(
            "Wake Up" if self.state.current is MochiState.SLEEPING else "Sleep"
        )
        rectangle = Gdk.Rectangle()
        rectangle.x = round(x)
        rectangle.y = round(y)
        rectangle.width = 1
        rectangle.height = 1
        self._context_menu.set_pointing_to(rectangle)
        self._context_menu.popup()

    def _toggle_sleep(self, _button: Gtk.Button) -> None:
        if self.state.current is MochiState.SLEEPING:
            self._wake_up()
        else:
            self._begin_sleep()
        self._context_menu.popdown()
        self.queue_draw()

    def _reset_position(self, _button: Gtk.Button) -> None:
        self._config.reset_position()
        default = WindowPlacement.DEFAULT_POSITION
        self._placement.move_to(default.x, default.y)
        self._context_menu.popdown()

    def _quit(self, _button: Gtk.Button) -> None:
        application = self._window.get_application()
        if application is not None:
            application.quit()

    def _on_pressed(
        self, _gesture: Gtk.GestureClick, _presses: int, x: float, y: float
    ) -> None:
        self._mark_interaction()
        self._press = (x, y)
        self._drag_started = False

    def _on_drag_begin(self, _gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        self._drag_origin = self._placement.position

    def _on_drag_update(
        self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if not self._placement.layer_shell_enabled:
            return
        if math.hypot(offset_x, offset_y) < 6:
            return
        self._drag_started = True
        self.state.transition_to(MochiState.DRAGGED)
        self._play_animation("dragged")
        # Y is stored as distance from the bottom edge, hence the subtraction.
        self._placement.move_to(
            self._drag_origin.x + round(offset_x),
            self._drag_origin.y - round(offset_y),
        )

    def _on_drag_end(
        self, _gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float
    ) -> None:
        if not self._drag_started:
            return
        if not self._placement.layer_shell_enabled:
            self._placement.sync_from_window()
        self._config.save_position(self._placement.position)
        self.state.transition_to(MochiState.IDLE)
        self._play_animation("idle")

    def _on_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        if self._placement.layer_shell_enabled:
            return
        if self._press is None or self._drag_started:
            return
        press_x, press_y = self._press
        if math.hypot(x - press_x, y - press_y) < 6:
            return

        event = controller.get_current_event()
        surface = self._window.get_surface()
        device = event.get_device() if event is not None else None
        if isinstance(surface, Gdk.Toplevel) and device is not None:
            self._drag_started = True
            self.state.transition_to(MochiState.DRAGGED)
            self._play_animation("dragged")
            # Wayland forbids applications from directly moving top-level windows.
            # begin_move asks the compositor to perform the user's active drag.
            surface.begin_move(
                device,
                Gdk.BUTTON_PRIMARY,
                press_x,
                press_y,
                event.get_time(),
            )

    def _on_released(
        self, _gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float
    ) -> None:
        self._press = None
        if self._drag_started:
            self._drag_started = False
            if self.state.current is MochiState.DRAGGED:
                self.state.transition_to(MochiState.IDLE)
                self._play_animation("idle")
            return
        self.react_to_click()

    def react_to_click(self) -> None:
        if self._preview_mode:
            self._next_preview_animation()
            return
        if self.state.current is MochiState.SLEEPING:
            self._wake_up(after="bounce")
            return
        animation = choose_click_reaction()
        state = {
            "bounce": MochiState.BOUNCING,
            "squish": MochiState.SQUISHING,
            "excited": MochiState.EXCITED,
        }[animation.name]
        self.state.transition_to(state)
        self._play_animation(animation.name)
        self.queue_draw()

    def _next_preview_animation(self) -> None:
        self._preview_index = (self._preview_index + 1) % len(
            self.PREVIEW_ANIMATIONS
        )
        name = self.PREVIEW_ANIMATIONS[self._preview_index]
        self._logger.info("Preview animation: %s", name)
        if name == "idle":
            self.state.transition_to(MochiState.IDLE)
            self._play_animation("idle")
        elif name == "sleep":
            self._begin_sleep()
        elif name == "wake":
            self.state.transition_to(MochiState.WAKING)
            self._play_animation("wake")
        else:
            state = {
                "blink": MochiState.BLINKING,
                "walk": MochiState.WALKING,
                "bounce": MochiState.BOUNCING,
                "squish": MochiState.SQUISHING,
                "excited": MochiState.EXCITED,
            }[name]
            self.state.transition_to(state)
            animation = replace(ANIMATIONS[name], looping=False)
            previous = self._current_animation
            self._current_animation = name
            self._pending_animation = "idle"
            self.player.play(animation)
            self._logger.debug("Animation: %s -> %s", previous, name)
            self.queue_draw()

    def _finish_reaction(self) -> None:
        next_animation = self._pending_animation
        self._pending_animation = None
        if next_animation == "sleeping":
            self._play_animation("sleeping")
        elif next_animation == "bounce":
            self.state.transition_to(MochiState.BOUNCING)
            self._play_animation("bounce", after="idle")
        else:
            self.state.transition_to(MochiState.IDLE)
            self._play_animation("idle")

    def _play_animation(self, name: str, after: str | None = None) -> None:
        previous = self._current_animation
        self._current_animation = name
        animation = ANIMATIONS[name]
        self._pending_animation = after if after is not None else animation.next_state
        self.player.play(animation)
        self._logger.debug("Animation: %s -> %s", previous, name)
        self.queue_draw()

    def _begin_sleep(self) -> None:
        self.state.transition_to(MochiState.SLEEPING)
        self._play_animation("sleep")
        self._logger.debug("Mochi sleeping")

    def _wake_up(self, after: str | None = None) -> None:
        self._mark_interaction()
        self.state.transition_to(MochiState.WAKING)
        self._play_animation("wake", after=after or "idle")
        self._logger.debug("Mochi awakened")

    def _mark_interaction(self) -> None:
        self._last_interaction = time.monotonic()

    def _schedule_idle_action(self) -> None:
        GLib.timeout_add_seconds(random.randint(5, 15), self._choose_idle_action)

    def _choose_idle_action(self) -> bool:
        try:
            if self.state.current is not MochiState.IDLE:
                return GLib.SOURCE_REMOVE
            if time.monotonic() - self._last_interaction >= 120:
                self._begin_sleep()
                return GLib.SOURCE_REMOVE

            action = random.choice(("blink", "walk", "squish", None, None))
            if action == "blink":
                self.state.transition_to(MochiState.BLINKING)
                self._play_animation("blink")
            elif action == "squish":
                self.state.transition_to(MochiState.SQUISHING)
                self._play_animation("squish")
            elif action == "walk":
                self._start_walk()
            return GLib.SOURCE_REMOVE
        finally:
            self._schedule_idle_action()

    def _start_walk(self) -> None:
        distance = random.randint(20, 100)
        direction = random.choice((-1, 1))
        origin = self._placement.sync_from_window()
        target = self._placement.clamp_position(origin.x + direction * distance, origin.y)
        if target.x == origin.x:
            target = self._placement.clamp_position(origin.x - direction * distance, origin.y)
        if target.x == origin.x:
            return
        self._walk_origin_x = origin.x
        self._walk_target_x = target.x
        self._walk_elapsed_ms = 0
        self.state.transition_to(MochiState.WALKING)
        self._play_animation("walk")

    def _advance_walk(self) -> None:
        self._walk_elapsed_ms += self.TICK_MS
        duration_ms = len(ANIMATIONS["walk"].frames) * ANIMATIONS["walk"].frame_duration_ms
        progress = min(1.0, self._walk_elapsed_ms / duration_ms)
        x = round(
            self._walk_origin_x
            + (self._walk_target_x - self._walk_origin_x) * progress
        )
        self._placement.move_to(x, self._placement.position.y)
        if progress >= 1.0:
            self._config.save_position(self._placement.position)
            self.state.transition_to(MochiState.IDLE)
            self._play_animation("idle")

    def _tick(self) -> bool:
        if self.state.current is MochiState.WALKING and not self._preview_mode:
            self._advance_walk()
        if self.player.tick(self.TICK_MS):
            self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int
    ) -> None:
        frame = self.player.frame
        if frame is not None:
            self.atlas.draw(context, frame, width, height)
