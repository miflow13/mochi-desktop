"""The buddy widget: sprite rendering, behavior, and pointer interaction."""

from __future__ import annotations

import math
import logging
import random
import time
from collections.abc import Callable
from dataclasses import replace

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.animation import Animation, AnimationPlayer
from mochi.behavior import (
    ClickReactionBuffer,
    WalkMotion,
    can_begin_sleep,
    can_begin_wake,
    can_transition,
    choose_click_reaction,
    choose_walk_animation,
)
from mochi.config import ConfigStore
from mochi.drag_motion import DragMotionModel, drag_pose_sprite, drag_settle_sprite
from mochi.sprites import ANIMATIONS, SpriteAtlas
from mochi.sound import SoundEvent, SoundManager
from mochi.state import MochiState, StateMachine
from mochi.windowing import WindowPlacement


class Buddy(Gtk.DrawingArea):
    SIZE = 128
    TICK_MS = 16
    WALK_SPEED_PX_PER_SECOND = 72.0
    BLINK_INTERVAL_SECONDS = (4.0, 12.0)
    DOUBLE_BLINK_CHANCE = 0.075
    DOUBLE_BLINK_PAUSE_MS = (120, 250)
    PREVIEW_ANIMATIONS = (
        "default",
        "idle",
        "blink",
        "dragged",
        "walk",
        "bounce",
        "squish",
        "excited",
        "sleep",
        "sleeping",
        "wake",
    )

    def __init__(
        self,
        window: Gtk.Window,
        placement: WindowPlacement,
        config: ConfigStore,
        sound: SoundManager,
        preview_mode: bool = False,
        on_click: Callable[[], None] | None = None,
        on_hover_enter: Callable[[MochiState], None] | None = None,
        on_hover_leave: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._window = window
        self._placement = placement
        self._config = config
        self._sound = sound
        self._on_click = on_click
        self._on_hover_enter = on_hover_enter
        self._on_hover_leave = on_hover_leave
        self._preview_mode = preview_mode
        self._preview_index = 0
        self._logger = logging.getLogger(__name__)
        self.state = StateMachine()
        self.atlas = SpriteAtlas()
        self.player = AnimationPlayer(on_finished=self._finish_reaction)
        self.player.play(ANIMATIONS["idle"])
        self._current_animation = "idle"
        self._active_animation = ANIMATIONS["idle"]
        self._pending_animation: str | None = None
        self._click_reactions = ClickReactionBuffer()
        self._idle_resume_position: tuple[int, int] | None = None
        self._recent_click_reactions: tuple[str, ...] = ()
        self._last_interaction = time.monotonic()
        self._walk_motion: WalkMotion | None = None
        self._walk_elapsed_ms = 0
        self._press: tuple[float, float] | None = None
        self._drag_origin = placement.position
        self._drag_started = False
        self._drag_move_started = False
        self._drag_motion = DragMotionModel()
        self._drag_frame_index = 1
        self._last_drag_update_time = 0.0
        self._drag_sample_position: tuple[int, int] | None = None
        self._drag_sample_time: float | None = None
        self._size = self._config.load_size()

        self.set_content_width(self._size)
        self.set_content_height(self._size)
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
        motion.connect("enter", self._on_pointer_enter)
        motion.connect("leave", self._on_pointer_leave)
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
            self._schedule_blink()

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

        walk_button = Gtk.Button(label="Test Walk")
        walk_button.add_css_class("flat")
        walk_button.connect("clicked", self._test_walk)
        menu_box.append(walk_button)

        options_label = Gtk.Label(label="Options")
        options_label.set_xalign(0)
        options_label.add_css_class("heading")
        options_label.set_margin_top(4)
        menu_box.append(options_label)

        size_label = Gtk.Label(label="Mochi size")
        size_label.set_xalign(0)
        menu_box.append(size_label)

        adjustment = Gtk.Adjustment(
            value=self._size,
            lower=ConfigStore.MIN_SIZE,
            upper=ConfigStore.MAX_SIZE,
            step_increment=64,
            page_increment=64,
        )
        size_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment
        )
        size_scale.set_digits(0)
        size_scale.set_draw_value(True)
        size_scale.set_value_pos(Gtk.PositionType.RIGHT)
        size_scale.set_size_request(180, -1)
        size_scale.connect("value-changed", self._change_size)
        menu_box.append(size_scale)

        mute_toggle = Gtk.CheckButton(label="Mute sounds")
        mute_toggle.set_active(self._sound.muted)
        mute_toggle.connect("toggled", self._change_muted)
        menu_box.append(mute_toggle)

        volume_label = Gtk.Label(label="Sound volume")
        volume_label.set_xalign(0)
        menu_box.append(volume_label)

        volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        volume_scale.set_value(self._sound.volume * 100)
        volume_scale.set_draw_value(True)
        volume_scale.set_value_pos(Gtk.PositionType.RIGHT)
        volume_scale.connect("value-changed", self._change_volume)
        menu_box.append(volume_scale)

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

    def _change_size(self, scale: Gtk.Scale) -> None:
        size = round(scale.get_value() / 64) * 64
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

    def _test_walk(self, _button: Gtk.Button) -> None:
        if self.state.current is MochiState.IDLE:
            self._start_walk()
        self._context_menu.popdown()

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
        self._drag_move_started = False

    def _on_drag_begin(self, _gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        self._drag_origin = self._placement.position

    def _on_drag_update(
        self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if math.hypot(offset_x, offset_y) < 6:
            return
        if not self._drag_started:
            self._drag_started = True
            self._cancel_walk()
            self._click_reactions.clear()
            self._transition_to(MochiState.DRAGGED)
            if self._placement.layer_shell_enabled:
                self._begin_drag_visual(
                    self._drag_origin.x + offset_x,
                    self._drag_origin.y + offset_y,
                )
            else:
                self._drag_motion.reset()
                self._drag_frame_index = 0
                self._play_drag_pose()
            self._sound.play(SoundEvent.PICKUP)
        if self._placement.layer_shell_enabled:
            # Y is stored as distance from the bottom edge, hence the subtraction.
            self._placement.move_to(
                self._drag_origin.x + round(offset_x),
                self._drag_origin.y - round(offset_y),
            )
        if self._placement.layer_shell_enabled:
            self._update_drag_visual(
                self._drag_origin.x + offset_x,
                self._drag_origin.y + offset_y,
            )

    def _on_drag_end(
        self, _gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float
    ) -> None:
        if not self._drag_started:
            return
        if not self._placement.layer_shell_enabled:
            self._placement.sync_from_window()
        self._config.save_position(self._placement.position)
        self._sound.play(SoundEvent.DROP)

    def _on_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        if self._placement.layer_shell_enabled:
            return
        if self._drag_started:
            event = controller.get_current_event()
            surface = self._window.get_surface()
            device = event.get_device() if event is not None else None
            if (
                not self._drag_move_started
                and isinstance(surface, Gdk.Toplevel)
                and device is not None
            ):
                press_x, press_y = self._press or (x, y)
                surface.begin_move(
                    device,
                    Gdk.BUTTON_PRIMARY,
                    press_x,
                    press_y,
                    event.get_time(),
                )
                self._drag_move_started = True
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
            self._cancel_walk()
            self._click_reactions.clear()
            self._transition_to(MochiState.DRAGGED)
            self._drag_motion.reset()
            self._drag_sample_position = None
            self._drag_sample_time = None
            self._drag_frame_index = 0
            self._play_drag_pose()
            self._sound.play(SoundEvent.PICKUP)
            # Wayland forbids applications from directly moving top-level windows.
            # begin_move asks the compositor to perform the user's active drag.
            surface.begin_move(
                device,
                Gdk.BUTTON_PRIMARY,
                press_x,
                press_y,
                event.get_time(),
            )
            self._drag_move_started = True

    def _on_released(
        self, _gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float
    ) -> None:
        self._press = None
        if self._drag_started:
            self._drag_started = False
            self._drag_move_started = False
            self._drag_sample_position = None
            self._drag_sample_time = None
            if self.state.current is MochiState.DRAGGED:
                self._drag_motion.reset()
                self._transition_to(MochiState.IDLE)
                self._play_drag_settle()
            return
        self.react_to_click()

    def react_to_click(self) -> None:
        if self._preview_mode:
            self._next_preview_animation()
            return
        if self._on_click is not None:
            self._on_click()
        if self.state.current is MochiState.SLEEPING:
            self._wake_up()
            return
        if self.state.current is MochiState.WALKING:
            self._cancel_walk()
            self._transition_to(MochiState.IDLE)
        if not self._click_reactions.request(self.state.current):
            if self.state.current in (MochiState.BOUNCING, MochiState.SQUISHING):
                self._logger.debug("Click reaction queued")
            return
        self._start_click_reaction()

    def _on_pointer_enter(
        self, _controller: Gtk.EventControllerMotion, _x: float, _y: float
    ) -> None:
        if self._on_hover_enter is not None:
            self._on_hover_enter(self.state.current)

    def _on_pointer_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        if self._on_hover_leave is not None:
            self._on_hover_leave()

    def _start_click_reaction(self) -> None:
        animation = choose_click_reaction(self._recent_click_reactions)
        self._sound.play(SoundEvent.PET)
        self._recent_click_reactions = (
            *self._recent_click_reactions[-1:],
            animation.name,
        )
        self._logger.debug("Click reaction selected: %s", animation.name)
        state = {
            "bounce": MochiState.BOUNCING,
            "squish": MochiState.SQUISHING,
        }[animation.name]
        self._transition_to(state)
        self._play_animation(animation.name)
        self.queue_draw()

    def _next_preview_animation(self) -> None:
        self._preview_index = (self._preview_index + 1) % len(
            self.PREVIEW_ANIMATIONS
        )
        name = self.PREVIEW_ANIMATIONS[self._preview_index]
        animation = ANIMATIONS[name]
        self._logger.info(
            "Preview animation: %s | frame 1/%d | duration=%dms | loop=%s | interruptible=%s",
            name,
            len(animation.frames),
            animation.frames[0].duration_ms or animation.frame_duration_ms,
            animation.looping,
            name not in ("bounce", "squish", "sleep", "wake"),
        )
        if name in ("default", "idle"):
            self._transition_to(MochiState.IDLE)
            self._play_animation(name)
        elif name == "sleep":
            self._begin_sleep()
        elif name == "sleeping":
            self._transition_to(MochiState.SLEEPING)
            self._play_animation("sleeping")
        elif name == "wake":
            self._transition_to(MochiState.WAKING)
            self._play_animation("wake")
        else:
            state = {
                "blink": MochiState.BLINKING,
                "dragged": MochiState.DRAGGED,
                "walk": MochiState.WALKING,
                "bounce": MochiState.BOUNCING,
                "squish": MochiState.SQUISHING,
                "excited": MochiState.EXCITED,
            }[name]
            self._transition_to(state)
            animation = replace(ANIMATIONS[name], looping=False)
            previous = self._current_animation
            self._current_animation = name
            self._active_animation = animation
            self._pending_animation = "idle"
            self.player.play(animation)
            self._logger.debug("Animation: %s -> %s", previous, name)
            self.queue_draw()

    def _finish_reaction(self, finished_animation) -> None:
        if finished_animation is not self._active_animation:
            self._logger.debug(
                "Ignoring stale animation completion: %s",
                finished_animation.name,
            )
            return
        next_animation = self._pending_animation
        self._pending_animation = None
        if next_animation == "sleeping":
            self._play_animation("sleeping")
        elif self._click_reactions.consume() and self._current_animation in (
            "bounce",
            "squish",
        ):
            self._transition_to(MochiState.IDLE)
            self._start_click_reaction()
        elif self._current_animation == "blink":
            self._resume_idle()
        else:
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")

    def _play_animation(self, name: str, after: str | None = None) -> None:
        previous = self._current_animation
        if name == "blink" and self.player.animation is ANIMATIONS["idle"]:
            self._idle_resume_position = (
                self.player.frame_index,
                self.player.elapsed_ms,
            )
        elif name != "blink":
            self._idle_resume_position = None
        self._current_animation = name
        animation = ANIMATIONS[name]
        self._active_animation = animation
        self._pending_animation = after if after is not None else animation.next_state
        self.player.play(animation)
        self._logger.debug("Animation: %s -> %s", previous, name)
        self.queue_draw()

    def _resume_idle(self) -> None:
        frame_index, elapsed_ms = self._idle_resume_position or (0, 0)
        self._idle_resume_position = None
        previous = self._current_animation
        self._current_animation = "idle"
        self._active_animation = ANIMATIONS["idle"]
        self.player.play(
            ANIMATIONS["idle"],
            frame_index=frame_index,
            elapsed_ms=elapsed_ms,
        )
        self._logger.debug("Animation: %s -> idle (resumed)", previous)
        self.queue_draw()

    def _begin_sleep(self) -> None:
        if not can_begin_sleep(self.state.current):
            return
        if not can_transition(self.state.current, MochiState.SLEEPING):
            return
        self._cancel_walk()
        self._click_reactions.clear()
        self._transition_to(MochiState.SLEEPING)
        self._play_animation("sleep")
        self._logger.debug("Mochi sleeping")

    def _wake_up(self) -> None:
        if not can_begin_wake(self.state.current):
            return
        self._mark_interaction()
        self._transition_to(MochiState.WAKING)
        self._play_animation("wake", after="idle")
        self._logger.debug("Mochi awakened")

    def _mark_interaction(self) -> None:
        self._last_interaction = time.monotonic()

    def _schedule_idle_action(self) -> None:
        GLib.timeout_add_seconds(random.randint(5, 15), self._choose_idle_action)

    def _schedule_blink(self) -> None:
        delay_seconds = random.uniform(*self.BLINK_INTERVAL_SECONDS)
        self._logger.debug("Blink scheduled in: %.1f seconds", delay_seconds)
        GLib.timeout_add(round(delay_seconds * 1_000), self._try_blink)

    def _try_blink(self) -> bool:
        try:
            if (
                self.state.current is MochiState.IDLE
                and self.player.animation is ANIMATIONS["idle"]
            ):
                self._play_blink()
            return GLib.SOURCE_REMOVE
        finally:
            self._schedule_blink()

    def _play_blink(self) -> None:
        self._idle_resume_position = (
            self.player.frame_index,
            self.player.elapsed_ms,
        )
        blink = ANIMATIONS["blink"]
        if random.random() < self.DOUBLE_BLINK_CHANCE:
            pause = replace(
                blink.frames[-1],
                duration_ms=random.randint(*self.DOUBLE_BLINK_PAUSE_MS),
            )
            blink = replace(
                blink,
                frames=blink.frames + (pause,) + blink.frames[1:],
            )
            self._logger.debug("Double blink triggered")
        previous = self._current_animation
        self._current_animation = "blink"
        self._active_animation = blink
        self._pending_animation = "idle"
        self.player.play(blink)
        self._logger.debug("Animation: %s -> blink", previous)
        self.queue_draw()

    def _choose_idle_action(self) -> bool:
        try:
            if self.state.current is not MochiState.IDLE:
                return GLib.SOURCE_REMOVE
            if time.monotonic() - self._last_interaction >= 120:
                self._begin_sleep()
                return GLib.SOURCE_REMOVE

            action = random.choice(("walk", "squish", None, None))
            if action == "squish":
                self._transition_to(MochiState.SQUISHING)
                self._play_animation("squish")
            elif action == "walk":
                self._start_walk()
            return GLib.SOURCE_REMOVE
        finally:
            self._schedule_idle_action()

    def _start_walk(self) -> None:
        origin = self._placement.sync_from_window()
        distance = random.randint(60, 240)
        angle = random.uniform(0, math.tau)
        target = self._placement.clamp_position(
            origin.x + round(math.cos(angle) * distance),
            origin.y + round(math.sin(angle) * distance),
        )
        actual_distance = math.hypot(target.x - origin.x, target.y - origin.y)
        if actual_distance < WalkMotion.MIN_DISTANCE:
            return
        cycle_duration_ms = (
            len(ANIMATIONS["walk"].frames)
            * ANIMATIONS["walk"].frame_duration_ms
        )
        self._walk_motion = WalkMotion(
            origin=(origin.x, origin.y),
            target=(target.x, target.y),
            cycle_duration_ms=cycle_duration_ms,
            speed_px_per_second=self.WALK_SPEED_PX_PER_SECOND,
        )
        self._walk_elapsed_ms = 0
        self._transition_to(MochiState.WALKING)
        self._play_animation(
            choose_walk_animation((origin.x, origin.y), (target.x, target.y))
        )

    def _advance_walk(self) -> None:
        if self._walk_motion is None:
            return
        self._walk_elapsed_ms += self.TICK_MS
        motion = self._walk_motion
        progress = motion.progress(self._walk_elapsed_ms)
        x, y = motion.position_at(self._walk_elapsed_ms)
        self._placement.move_to(x, y)
        if self.player.seek_progress(motion.animation_progress(self._walk_elapsed_ms)):
            self.queue_draw()
        if progress >= 1.0:
            self._walk_motion = None
            self._config.save_position(self._placement.position)
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")

    def _tick(self) -> bool:
        walking = self.state.current is MochiState.WALKING and not self._preview_mode
        if walking:
            self._advance_walk()
        dragging = self.state.current is MochiState.DRAGGED
        if dragging and not self._placement.layer_shell_enabled:
            self._sample_x11_drag()
        elif dragging and time.monotonic() - self._last_drag_update_time > 0.05:
            self._settle_drag_visual()
        if not walking and not dragging and self.player.tick(self.TICK_MS):
            self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _begin_drag_visual(self, x: float, y: float) -> None:
        self._last_drag_update_time = time.monotonic()
        self._drag_motion.begin(x, y, time.monotonic())
        self._drag_frame_index = 1
        self._play_drag_pose()

    def _update_drag_visual(self, x: float, y: float) -> None:
        if self.state.current is not MochiState.DRAGGED:
            return
        timestamp = time.monotonic()
        self._last_drag_update_time = timestamp
        self._drag_motion.update(x, y, timestamp)
        self._play_drag_pose()

    def _settle_drag_visual(self) -> None:
        self._drag_motion.settle()
        self._play_drag_pose()

    def _sample_x11_drag(self) -> None:
        position = self._placement.sync_from_window()
        timestamp = time.monotonic()
        previous_position = self._drag_sample_position
        previous_time = self._drag_sample_time
        if previous_position is None or previous_time is None:
            self._drag_motion.begin(position.x, position.y, timestamp)
            elapsed = 0.0
        else:
            elapsed = timestamp - previous_time
            self._drag_motion.update(position.x, position.y, timestamp)
        self._drag_sample_position = (position.x, position.y)
        self._drag_sample_time = timestamp
        self._last_drag_update_time = timestamp
        self._play_drag_pose()
        frame = self.player.frame
        self._logger.debug(
            "Drag sample position=(%d,%d) dt=%.3f filtered_velocity_x=%.1f intensity=%.3f frame_index=%d sprite=%s",
            position.x,
            position.y,
            elapsed,
            self._drag_motion.filtered_velocity_x,
            self._drag_motion.horizontal_intensity,
            self._drag_frame_index,
            frame.sprite if frame is not None else "none",
        )

    def _play_drag_pose(self) -> None:
        intensity = self._drag_motion.horizontal_intensity
        sprite = drag_pose_sprite(intensity)
        self._drag_frame_index = next(
            index
            for index, frame in enumerate(ANIMATIONS["dragged"].frames)
            if frame.sprite == sprite
        )
        body_offset = round(self._drag_motion.body_sway * 14)
        animation = replace(
            ANIMATIONS["dragged"],
            frames=tuple(
                replace(frame, horizontal_offset=body_offset)
                for frame in ANIMATIONS["dragged"].frames
            ),
        )
        self.player.play(
            animation, frame_index=self._drag_frame_index
        )
        self._current_animation = "dragged"
        self._active_animation = animation
        self._pending_animation = None
        self.queue_draw()

    def _play_drag_settle(self) -> None:
        dragged_frames = ANIMATIONS["dragged"].frames
        pose_sprite = dragged_frames[self._drag_frame_index].sprite
        settle_sprite = drag_settle_sprite(pose_sprite)
        current = next(
            frame for frame in dragged_frames if frame.sprite == settle_sprite
        )
        neutral = next(
            frame
            for frame in dragged_frames
            if frame.sprite == "drag/drag_settle_neutral.png"
        )
        settle = Animation(
            name="drag_settle",
            frames=(
                replace(current, duration_ms=70),
                replace(neutral, duration_ms=140),
            ),
            frame_duration_ms=140,
            next_state="idle",
        )
        self._current_animation = settle.name
        self._active_animation = settle
        self._pending_animation = "idle"
        self.player.play(settle)
        self.queue_draw()

    def _cancel_walk(self) -> None:
        self._walk_motion = None
        self._walk_elapsed_ms = 0

    def _transition_to(self, next_state: MochiState) -> bool:
        if not can_transition(self.state.current, next_state):
            self._logger.debug(
                "Rejected state transition: %s -> %s",
                self.state.current.name,
                next_state.name,
            )
            return False
        self.state.transition_to(next_state)
        return True

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int
    ) -> None:
        frame = self.player.frame
        if frame is None:
            frame = ANIMATIONS["default"].frames[0]
        self.atlas.draw(context, frame, width, height)
