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

from mochi.animation import AnimationPlayer
from mochi.behavior import (
    ClickReactionBuffer,
    WalkMotion,
    can_begin_sleep,
    can_begin_wake,
    choose_click_reaction,
    choose_walk_animation,
)
from mochi.config import ConfigStore
from mochi.developer_shortcut import DeveloperShortcutMonitor
from mochi.drag_motion import DragMotionModel, DragPoseSelector
from mochi.file_activity import FileActivityMonitor
from mochi.media_activity import MediaActivityMonitor
from mochi.buddy_menu import BuddyMenuController
from mochi.ambient_activity import AmbientActivityController
from mochi.interaction_tuning import (
    COMPUTER_IDLE_DELAY_SECONDS,
    DRAG_BODY_SWAY_PX,
    DRAG_SETTLE_DIRECTIONAL_MS,
    DRAG_SETTLE_NEUTRAL_MS,
    DRAG_SWAY_ENTER_DELAY_SECONDS,
    DRAG_SWAY_EXIT_INTENSITY,
    DRAG_VISUAL_IDLE_DELAY_SECONDS,
    InteractionTuning,
)
from mochi.sprites import ANIMATIONS, SpriteAtlas
from mochi.sound import SoundEvent, SoundManager
from mochi.state import MochiState, StateMachine
from mochi.state_controller import BehaviorStateController
from mochi.presence_activity import PresenceActivityMonitor
from mochi.typing_activity import TypingActivityMonitor
from mochi.windowing import WindowPlacement


def _menu_ui_for(owner):
    controller = getattr(owner, "_menu_ui", None)
    if controller is None:
        controller = BuddyMenuController(owner)
    return controller


def _ambient_activity_for(owner):
    controller = getattr(owner, "_ambient_activity", None)
    if controller is None:
        controller = AmbientActivityController(owner)
    return controller


def _state_controller_for(owner):
    controller = getattr(owner, "state_controller", None)
    if controller is None:
        controller = BehaviorStateController(
            owner.state,
            logger=getattr(owner, "_logger", None),
        )
    return controller


class Buddy(Gtk.DrawingArea):
    SIZE = 112
    TICK_MS = 16
    CONTEXT_MENU_WIDTH = 244
    CONTEXT_MENU_BASE_HEIGHT = 176
    CONTEXT_MENU_UNKNOWN_ROW_HEIGHT = 44
    CONTEXT_MENU_MIN_HEIGHTS = {
        "sleep": 176,
        "stay-put": 224,
        "edge-roam": 268,
        "quick-start": 312,
    }
    CONTEXT_MENU_BASE_SIZED_ROWS = frozenset(
        ("header", "separator", "status", "sleep", "close")
    )
    WALK_SPEED_PX_PER_SECOND = 72.0
    BLINK_INTERVAL_SECONDS = (4.0, 12.0)
    DOUBLE_BLINK_CHANCE = 0.075
    DOUBLE_BLINK_PAUSE_MS = (120, 250)
    HOVER_HEART_DELAY_MS = 280
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
    ) -> None:
        super().__init__()
        self._window = window
        self._placement = placement
        self._config = config
        self._sound = sound
        self._on_click = on_click
        self._preview_mode = preview_mode
        self._preview_index = 0
        self._logger = logging.getLogger(__name__)
        self.state = StateMachine()
        self.state_controller = BehaviorStateController(
            self.state,
            logger=self._logger,
        )
        self._menu_ui = BuddyMenuController(self)
        self._ambient_activity = AmbientActivityController(self)
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
        self._tuning = InteractionTuning()
        self._tuning_controls: dict[str, Gtk.SpinButton] = {}
        self._walk_motion: WalkMotion | None = None
        self._walk_elapsed_ms = 0
        self._press: tuple[float, float] | None = None
        self._drag_origin = placement.position
        self._drag_started = False
        self._drag_move_started = False
        self._drag_release_handled = False
        self._drag_end_handled = False
        self._drag_motion = DragMotionModel(
            max_velocity=self._tuning.drag_heavy_velocity_px_per_second,
            pose_selector=DragPoseSelector(
                soft_enter_threshold=self._tuning.drag_soft_enter_threshold,
                medium_enter_threshold=self._tuning.drag_medium_enter_threshold,
                medium_exit_threshold=self._tuning.drag_medium_exit_threshold,
                dwell_ms=self._tuning.drag_state_dwell_ms,
            ),
        )
        self._drag_frame_index = 0
        self._drag_visual_key: tuple[str, int] | None = None
        self._last_drag_update_time = 0.0
        self._drag_neutral_since: float | None = None
        self._drag_sample_position: tuple[int, int] | None = None
        self._drag_sample_time: float | None = None
        self._hovered = False
        self._last_heart_started = float("-inf")
        self._hover_heart_source_id: int | None = None
        self._idle_action_source_id: int | None = None
        self._blink_source_id: int | None = None
        self._computer_idle_source_id: int | None = None
        self._typing_monitor: TypingActivityMonitor | None = None
        self._presence_monitor: PresenceActivityMonitor | None = None
        self._media_monitor: MediaActivityMonitor | None = None
        self._file_activity_monitor: FileActivityMonitor | None = None
        self._developer_shortcut_monitor: DeveloperShortcutMonitor | None = None
        self._context_menu_open = False
        self._menu_animation_serial = 0
        self._user_idle = False
        self._pending_context_action: Callable[[], None] | None = None
        self._pending_developer_action: Callable[[], None] | None = None
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
        context_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        context_click.connect("pressed", self._on_context_pressed)
        # A transient menu window has no popup grab for release to dismiss,
        # so secondary-click can open immediately on the first press.
        context_click.connect("pressed", self._show_context_menu)
        self.add_controller(context_click)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", self._on_enter)
        motion.connect("leave", self._on_leave)
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)

        drag = Gtk.GestureDrag.new()
        drag.set_button(Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

        self._context_menu = self._build_context_menu()
        self._context_menu.connect("closed", self._on_context_menu_closed)
        self._developer_menu = self._build_developer_menu()
        self._developer_menu.connect("closed", self._on_developer_menu_closed)

        GLib.timeout_add(self.TICK_MS, self._tick)
        if not self._preview_mode:
            self._typing_monitor = TypingActivityMonitor(
                on_typing_activity=self._on_typing_activity,
                on_typing_stopped=self._on_typing_stopped,
                logger=self._logger,
            )
            self._typing_monitor.start()
            self._presence_monitor = PresenceActivityMonitor(
                on_user_idle=self._on_user_idle,
                on_user_active=self._on_user_active,
                logger=self._logger,
            )
            self._presence_monitor.start()
            self._media_monitor = MediaActivityMonitor(
                on_youtube_started=self._on_youtube_started,
                on_youtube_stopped=self._on_youtube_stopped,
                logger=self._logger,
            )
            self._media_monitor.start()
            self._file_activity_monitor = FileActivityMonitor(
                on_file_activity_started=self._on_file_activity_started,
                on_file_activity_stopped=self._on_file_activity_stopped,
                logger=self._logger,
            )
            self._file_activity_monitor.start()
            self._developer_shortcut_monitor = DeveloperShortcutMonitor(
                on_requested=self._show_developer_menu,
                logger=self._logger,
            )
            self._developer_shortcut_monitor.start()
            self._schedule_idle_action()
            self._schedule_blink()
            self._schedule_computer_idle_emote()



    # Compatibility seams for feature mixins and GTK callbacks. The behavior
    # lives in composition-owned controllers rather than additional MRO layers.
    def _initialize_context_menu_layout(self, *args, **kwargs):
        return _menu_ui_for(self)._initialize_context_menu_layout(*args, **kwargs)

    def _register_context_menu_row(self, *args, **kwargs):
        return _menu_ui_for(self)._register_context_menu_row(*args, **kwargs)

    def _get_context_menu_row(self, *args, **kwargs):
        return _menu_ui_for(self)._get_context_menu_row(*args, **kwargs)

    def _recalculate_context_menu_layout(self, *args, **kwargs):
        return _menu_ui_for(self)._recalculate_context_menu_layout(*args, **kwargs)

    def _build_context_menu(self, *args, **kwargs):
        return _menu_ui_for(self)._build_context_menu(*args, **kwargs)

    def _build_developer_menu(self, *args, **kwargs):
        return _menu_ui_for(self)._build_developer_menu(*args, **kwargs)

    def _make_menu_button(self, *args, **kwargs):
        return _menu_ui_for(self)._make_menu_button(*args, **kwargs)

    def _append_tuning_control(self, *args, **kwargs):
        return _menu_ui_for(self)._append_tuning_control(*args, **kwargs)

    def _change_tuning(self, *args, **kwargs):
        return _menu_ui_for(self)._change_tuning(*args, **kwargs)

    def _change_size(self, *args, **kwargs):
        return _menu_ui_for(self)._change_size(*args, **kwargs)

    def _change_volume(self, *args, **kwargs):
        return _menu_ui_for(self)._change_volume(*args, **kwargs)

    def _change_muted(self, *args, **kwargs):
        return _menu_ui_for(self)._change_muted(*args, **kwargs)

    def _change_sound_enabled(self, *args, **kwargs):
        return _menu_ui_for(self)._change_sound_enabled(*args, **kwargs)

    def _show_context_menu(self, *args, **kwargs):
        return _menu_ui_for(self)._show_context_menu(*args, **kwargs)

    def _show_developer_menu(self, *args, **kwargs):
        return _menu_ui_for(self)._show_developer_menu(*args, **kwargs)

    def _animate_menu_open(self, *args, **kwargs):
        return _menu_ui_for(self)._animate_menu_open(*args, **kwargs)

    def _quit_from_context_menu(self, *args, **kwargs):
        return _menu_ui_for(self)._quit_from_context_menu(*args, **kwargs)

    def _toggle_sleep(self, *args, **kwargs):
        return _menu_ui_for(self)._toggle_sleep(*args, **kwargs)

    def _test_walk(self, *args, **kwargs):
        return _menu_ui_for(self)._test_walk(*args, **kwargs)

    def _test_heart_emote(self, *args, **kwargs):
        return _menu_ui_for(self)._test_heart_emote(*args, **kwargs)

    def _test_computer_emote(self, *args, **kwargs):
        return _menu_ui_for(self)._test_computer_emote(*args, **kwargs)

    def _reset_position(self, *args, **kwargs):
        return _menu_ui_for(self)._reset_position(*args, **kwargs)

    def _close_context_menu_then(self, *args, **kwargs):
        return _menu_ui_for(self)._close_context_menu_then(*args, **kwargs)

    def _close_developer_menu_then(self, *args, **kwargs):
        return _menu_ui_for(self)._close_developer_menu_then(*args, **kwargs)

    def _on_context_menu_closed(self, *args, **kwargs):
        return _menu_ui_for(self)._on_context_menu_closed(*args, **kwargs)

    def _on_developer_menu_closed(self, *args, **kwargs):
        return _menu_ui_for(self)._on_developer_menu_closed(*args, **kwargs)

    def _dispatch_context_action(self, *args, **kwargs):
        return _menu_ui_for(self)._dispatch_context_action(*args, **kwargs)

    def _quit_application(self, *args, **kwargs):
        return _menu_ui_for(self)._quit_application(*args, **kwargs)

    def _quit(self, *args, **kwargs):
        return _menu_ui_for(self)._quit(*args, **kwargs)

    def _on_typing_activity(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_typing_activity(*args, **kwargs)

    def _start_typing_emote(self, *args, **kwargs):
        return _ambient_activity_for(self)._start_typing_emote(*args, **kwargs)

    def _on_typing_stopped(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_typing_stopped(*args, **kwargs)

    def _on_youtube_started(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_youtube_started(*args, **kwargs)

    def _on_youtube_stopped(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_youtube_stopped(*args, **kwargs)

    def _start_watching_emote(self, *args, **kwargs):
        return _ambient_activity_for(self)._start_watching_emote(*args, **kwargs)

    def _maybe_resume_watching(self, *args, **kwargs):
        return _ambient_activity_for(self)._maybe_resume_watching(*args, **kwargs)

    def _on_file_activity_started(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_file_activity_started(*args, **kwargs)

    def _on_file_activity_stopped(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_file_activity_stopped(*args, **kwargs)

    def _start_searching_emote(self, *args, **kwargs):
        return _ambient_activity_for(self)._start_searching_emote(*args, **kwargs)

    def _maybe_resume_searching(self, *args, **kwargs):
        return _ambient_activity_for(self)._maybe_resume_searching(*args, **kwargs)

    def _maybe_resume_ambient_activity(self, *args, **kwargs):
        return _ambient_activity_for(self)._maybe_resume_ambient_activity(*args, **kwargs)

    def _on_user_idle(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_user_idle(*args, **kwargs)

    def _on_user_active(self, *args, **kwargs):
        return _ambient_activity_for(self)._on_user_active(*args, **kwargs)

    def _cancel_active_emote(self, *args, **kwargs):
        return _ambient_activity_for(self)._cancel_active_emote(*args, **kwargs)


    def _update_pointer_cursor(self) -> None:
        # Keep a visible hand cursor through hover, press, pickup, and drag.
        # Apply it to both the drawing area and the toplevel because XWayland
        # hands an active window move to the compositor, which can otherwise
        # override a child-widget cursor.
        held = (
            self._hovered
            or self._press is not None
            or self._drag_started
            or self.state.current in (MochiState.PICKUP, MochiState.DRAGGED)
        )
        cursor_name = "pointer" if held else None
        self.set_cursor_from_name(cursor_name)
        self._window.set_cursor_from_name(cursor_name)

    def _on_enter(
        self, _controller: Gtk.EventControllerMotion, _x: float, _y: float
    ) -> None:
        if self._hovered:
            return
        self._hovered = True
        self._update_pointer_cursor()
        self._mark_interaction()
        self._cancel_hover_heart()
        self._hover_heart_source_id = GLib.timeout_add(
            self.HOVER_HEART_DELAY_MS,
            self._fire_hover_heart,
        )

    def _on_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        self._hovered = False
        self._cancel_hover_heart()
        self._update_pointer_cursor()

    def _fire_hover_heart(self) -> bool:
        self._hover_heart_source_id = None
        if self._hovered and not self._context_menu_open:
            self._start_heart_emote()
        return GLib.SOURCE_REMOVE

    def _cancel_hover_heart(self) -> None:
        source_id = self._hover_heart_source_id
        self._hover_heart_source_id = None
        if source_id is not None:
            GLib.source_remove(source_id)

    def _on_context_pressed(
        self, _gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float
    ) -> None:
        # Secondary-click declares menu intent only. Cancel a not-yet-fired
        # hover reaction, but do not alter Mochi's current state/animation.
        self._cancel_hover_heart()

    def _start_heart_emote(self, ignore_cooldown: bool = False) -> bool:
        now = time.monotonic()
        if (
            self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        if (
            not ignore_cooldown
            and now - self._last_heart_started
            < self._tuning.hover_heart_cooldown_seconds
        ):
            return False
        if not self._transition_to(MochiState.HEART):
            return False
        self._last_heart_started = now
        self._play_animation("heart")
        return True

    def _start_computer_emote(self) -> bool:
        if (
            self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        if not self._transition_to(MochiState.COMPUTER):
            return False
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._play_animation("computer", after="idle")
        return True

    def _on_pressed(
        self, _gesture: Gtk.GestureClick, _presses: int, x: float, y: float
    ) -> None:
        self._mark_interaction()
        self._cancel_active_emote()
        self._press = (x, y)
        self._drag_started = False
        self._drag_move_started = False
        self._drag_release_handled = False
        self._drag_end_handled = False
        self._update_pointer_cursor()

    def _on_drag_begin(self, _gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        self._drag_origin = self._placement.position

    def _on_drag_update(
        self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if math.hypot(offset_x, offset_y) < self._tuning.drag_start_distance_px:
            return
        if not self._drag_started:
            self._drag_started = True
            self._cancel_walk()
            self._click_reactions.clear()
            if not self._begin_pickup():
                self._drag_started = False
                return
            if self._placement.layer_shell_enabled:
                self._begin_drag_visual(
                    self._drag_origin.x + offset_x,
                    self._drag_origin.y + offset_y,
                )
            else:
                self._drag_motion.reset()
                self._drag_frame_index = 0
            self._sound.play(SoundEvent.PICKUP)
        if self._placement.layer_shell_enabled and self.state.current in (
            MochiState.PICKUP,
            MochiState.DRAGGED,
        ):
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
        self._press = None
        if not self._drag_started and not self._drag_release_handled:
            self._update_pointer_cursor()
            return
        self._finish_drag_interaction()
        self._update_pointer_cursor()
        if self._drag_end_handled:
            return
        self._drag_end_handled = True
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
        if math.hypot(x - press_x, y - press_y) < self._tuning.drag_start_distance_px:
            return

        event = controller.get_current_event()
        surface = self._window.get_surface()
        device = event.get_device() if event is not None else None
        if isinstance(surface, Gdk.Toplevel) and device is not None:
            self._drag_started = True
            self._cancel_walk()
            self._click_reactions.clear()
            if not self._begin_pickup():
                self._drag_started = False
                return
            self._drag_motion.reset()
            self._drag_sample_position = None
            self._drag_sample_time = None
            self._drag_frame_index = 0
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
        self._update_pointer_cursor()
        if self._finish_drag_interaction() or self._drag_release_handled:
            return
        self.react_to_click()

    def _finish_drag_interaction(self) -> bool:
        if not self._drag_started:
            return False
        self._drag_started = False
        self._drag_release_handled = True
        self._drag_move_started = False
        self._drag_sample_position = None
        self._drag_sample_time = None
        if self.state.current in (MochiState.PICKUP, MochiState.DRAGGED):
            self._transition_to(MochiState.DROPPING)
            self._play_drag_settle()
            self._drag_motion.reset()
            self._drag_visual_key = None
        return True

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
        if self._current_animation == "pickup":
            if not self._drag_started or self.state.current is not MochiState.PICKUP:
                self._transition_to(MochiState.IDLE)
                self._play_animation("idle")
                return
            self._transition_to(MochiState.DRAGGED)
            self._play_drag_pose()
            return
        next_animation = self._pending_animation
        self._pending_animation = None
        if next_animation == "sleeping":
            self._play_animation("sleeping")
        elif next_animation == "typing_loop":
            self._play_animation("typing_loop", after=None)
        elif next_animation == "typing_outro":
            self._play_animation("typing_outro", after="idle")
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
            # A typing burst may have begun during the wake transition. Resolve
            # the live signal, so a burst that already ended is not replayed.
            if (
                finished_animation.name == "wake"
                and getattr(getattr(self, "_typing_monitor", None), "active", False)
                and self._start_typing_emote()
            ):
                return
            if not self._maybe_resume_ambient_activity() and finished_animation.name in (
                "computer",
                "typing_outro",
            ):
                self._schedule_computer_idle_emote()

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
        if name == "pickup":
            animation = replace(
                animation,
                frame_duration_ms=self._tuning.pickup_frame_duration_ms,
            )
        self._active_animation = animation
        self._pending_animation = after if after is not None else animation.next_state
        self.player.play(animation)
        self._logger.debug("Animation: %s -> %s", previous, name)
        self.queue_draw()

    def _begin_pickup(self) -> bool:
        self._cancel_active_emote()
        self._drag_neutral_since = None
        if not self._transition_to(MochiState.PICKUP):
            return False
        self._play_animation("pickup", after=None)
        return True

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
        self._maybe_resume_ambient_activity()

    def _begin_sleep(self) -> None:
        self._cancel_active_emote()
        if not can_begin_sleep(self.state.current):
            return
        self._cancel_walk()
        self._click_reactions.clear()
        if not self._transition_to(MochiState.SLEEPING):
            return
        self._play_animation("sleep")
        self._logger.debug("Mochi sleeping")

    def _wake_up(self) -> None:
        if not can_begin_wake(self.state.current):
            return
        self._transition_to(MochiState.WAKING)
        self._user_idle = False
        self._mark_interaction()
        self._play_animation("wake", after="idle")
        self._logger.debug("Mochi awakened")

    def _mark_interaction(self) -> None:
        self._last_interaction = time.monotonic()
        if getattr(self, "_user_idle", False) or self.state.current is MochiState.SLEEPING:
            self._on_user_active()
        if not self._preview_mode:
            self._reschedule_computer_idle_emote()

    def _schedule_idle_action(self) -> None:
        if self._idle_action_source_id is None:
            self._idle_action_source_id = GLib.timeout_add_seconds(
                random.randint(5, 15), self._choose_idle_action
            )

    def _schedule_blink(self) -> None:
        if self._blink_source_id is not None:
            return
        delay_seconds = random.uniform(*self.BLINK_INTERVAL_SECONDS)
        self._logger.debug("Blink scheduled in: %.1f seconds", delay_seconds)
        self._blink_source_id = GLib.timeout_add(
            round(delay_seconds * 1_000), self._try_blink
        )

    def _schedule_computer_idle_emote(self) -> None:
        if self._computer_idle_source_id is not None:
            return
        delay = random.randint(*COMPUTER_IDLE_DELAY_SECONDS)
        self._computer_idle_source_id = GLib.timeout_add_seconds(
            delay, self._try_computer_idle_emote
        )
        self._logger.debug("Computer idle emote scheduled in %d seconds", delay)

    def _reschedule_computer_idle_emote(self) -> None:
        if self._computer_idle_source_id is not None:
            GLib.source_remove(self._computer_idle_source_id)
            self._computer_idle_source_id = None
        self._schedule_computer_idle_emote()

    def _try_computer_idle_emote(self) -> bool:
        self._computer_idle_source_id = None
        if not self._start_computer_emote():
            self._schedule_computer_idle_emote()
        return GLib.SOURCE_REMOVE

    def _try_blink(self) -> bool:
        self._blink_source_id = None
        try:
            if (
                self.state.current is MochiState.IDLE
                and not self._context_menu_open
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
        self._idle_action_source_id = None
        try:
            if self.state.current is not MochiState.IDLE or self._context_menu_open:
                return GLib.SOURCE_REMOVE
            # The global idle signal is edge-triggered. Retry deferred sleep
            # through the existing ambient timer once the owning state ends.
            if self._user_idle:
                self._on_user_idle()
                return GLib.SOURCE_REMOVE
            # Automatic sleep is driven by the GNOME Shell presence monitor.
            # Local Mochi interaction timestamps are not a proxy for whether the
            # user is actually present at the computer.
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
            self._maybe_resume_ambient_activity()

    def _tick(self) -> bool:
        walking = self.state.current is MochiState.WALKING and not self._preview_mode
        if walking:
            self._advance_walk()
        picking_up = self.state.current is MochiState.PICKUP
        dragging = self.state.current is MochiState.DRAGGED

        # Reassert the hand cursor while the compositor owns the native
        # XWayland move so it stays visually consistent for the whole drag.
        if picking_up or dragging:
            self._update_pointer_cursor()

        if (picking_up or dragging) and not self._placement.layer_shell_enabled:
            self._sample_x11_drag(render=dragging)
        elif (
            dragging
            and time.monotonic() - self._last_drag_update_time
            > DRAG_VISUAL_IDLE_DELAY_SECONDS
        ):
            self._settle_drag_visual()
        held_sway = dragging and self._current_animation == "sway_idle"
        if (
            not walking
            and (not dragging or held_sway)
            and self.player.tick(self.TICK_MS)
        ):
            self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _begin_drag_visual(self, x: float, y: float) -> None:
        timestamp = time.monotonic()
        self._last_drag_update_time = timestamp
        self._drag_motion.begin(x, y, timestamp)
        self._drag_frame_index = 0
        self._drag_visual_key = None

    def _update_drag_visual(self, x: float, y: float) -> None:
        if self.state.current not in (MochiState.PICKUP, MochiState.DRAGGED):
            return
        timestamp = time.monotonic()
        self._last_drag_update_time = timestamp
        self._drag_motion.update(x, y, timestamp)
        if self.state.current is MochiState.DRAGGED:
            self._play_drag_pose()

    def _settle_drag_visual(self) -> None:
        self._drag_motion.settle()
        self._play_drag_pose()

    def _sample_x11_drag(self, render: bool = True) -> None:
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
        if render:
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
        sprite = self._drag_motion.pose_sprite()
        candidate_frame_index = next(
            index
            for index, frame in enumerate(ANIMATIONS["dragged"].frames)
            if frame.sprite == sprite
        )
        intensity = abs(self._drag_motion.horizontal_intensity)
        now = time.monotonic()

        # While the authored held sway is active, ignore tiny motion jitter.
        # A deliberate movement still interrupts sway immediately.
        if (
            self._current_animation == "sway_idle"
            and sprite != "drag/drag_neutral.png"
            and intensity < DRAG_SWAY_EXIT_INTENSITY
        ):
            self._drag_frame_index = 0
            return

        # A neutral held pose means Mochi is still picked up but the pointer has
        # settled. Require a short quiet window before entering sway so filtered
        # velocity can decay without the drag pose and sway loop fighting.
        if sprite == "drag/drag_neutral.png":
            self._drag_frame_index = 0
            if self._drag_neutral_since is None:
                self._drag_neutral_since = now
            if (
                self._current_animation != "sway_idle"
                and now - self._drag_neutral_since < DRAG_SWAY_ENTER_DELAY_SECONDS
            ):
                return
            visual_key = ("sway_idle", 0)
            if (
                self._current_animation == "sway_idle"
                and visual_key == self._drag_visual_key
            ):
                return
            self._drag_visual_key = visual_key
            self._current_animation = "sway_idle"
            self._active_animation = ANIMATIONS["sway_idle"]
            self._pending_animation = None
            self.player.play(ANIMATIONS["sway_idle"])
            self._logger.debug("Held drag settled -> sway_idle")
            self.queue_draw()
            return

        self._drag_neutral_since = None
        self._drag_frame_index = candidate_frame_index

        body_offset = round(self._drag_motion.body_sway * DRAG_BODY_SWAY_PX)
        visual_key = (sprite, body_offset)
        if visual_key == self._drag_visual_key:
            return
        self._drag_visual_key = visual_key
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
        self._play_animation("drop", after="idle")

    def _cancel_walk(self) -> None:
        self._walk_motion = None
        self._walk_elapsed_ms = 0

    def _transition_to(self, next_state: MochiState) -> bool:
        return _state_controller_for(self).request(next_state)

    def _draw(
        self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int
    ) -> None:
        frame = self.player.frame
        if frame is None:
            frame = ANIMATIONS["default"].frames[0]
        self.atlas.draw(context, frame, width, height)
