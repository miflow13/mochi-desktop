"""Work with Mochi: lightweight Pomodoro-style focus sessions."""

from __future__ import annotations

from collections.abc import Callable
import logging
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.focus import FocusPhase, FocusPlan, FocusSession
from mochi.sound import FocusAmbienceManager
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState

from .engine import speech_display_seconds


FOCUS_TIMER_TICK_MS = 500
FOCUS_PRESENCE_PRIORITY_FLOOR = 40
FOCUS_BREAK_LINE = "break time 🌱"
FOCUS_RESUME_LINE = "back to it. i'm with you 🌱"
FOCUS_COMPLETE_LINE = "nice work. we did it 🌱"
FOCUS_CANCEL_LINE = "stopped. no worries 🌱"


FOCUS_CSS = """
window.mochi-focus-window {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}

.mochi-focus-kicker {
    color: #79c98b;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
}

.mochi-focus-title {
    font-size: 21px;
    font-weight: 800;
}

.mochi-focus-subtitle,
.mochi-focus-secondary {
    color: alpha(@theme_fg_color, 0.70);
}

.mochi-focus-timer {
    font-size: 38px;
    font-weight: 800;
}

.mochi-focus-card {
    background-color: alpha(@theme_fg_color, 0.045);
    border: 1px solid alpha(@theme_fg_color, 0.09);
    border-radius: 14px;
    padding: 14px;
}

button.mochi-focus-primary {
    min-height: 38px;
    border-radius: 10px;
    background-image: none;
    background-color: #79c98b;
    color: #16351f;
    font-weight: 700;
}

button.mochi-focus-secondary-button {
    min-height: 38px;
    border-radius: 10px;
}
"""


class FocusWindow:
    """Small setup/timer surface that can be hidden without ending a session."""

    DEFAULT_WIDTH = 420
    DEFAULT_HEIGHT = 455

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        on_start: Callable[[FocusPlan], None],
        on_pause: Callable[[], None],
        on_cancel: Callable[[], None],
        on_rain_enabled: Callable[[bool], None],
        on_rain_volume_changed: Callable[[float], None],
        rain_available: bool,
        rain_enabled: bool,
        rain_volume: float,
        logger: logging.Logger | None = None,
    ) -> None:
        self._on_start = on_start
        self._on_pause = on_pause
        self._on_cancel = on_cancel
        self._on_rain_enabled = on_rain_enabled
        self._on_rain_volume_change = on_rain_volume_changed
        self._rain_available = rain_available
        self._rain_enabled = rain_enabled
        self._rain_volume = rain_volume
        self._logger = logger or logging.getLogger(__name__)

        self.window = Gtk.Window()
        self.window.set_title("Focus with Mochi 🌱")
        self.window.set_transient_for(owner)
        self.window.set_destroy_with_parent(True)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_resizable(False)
        self.window.set_default_size(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.window.set_size_request(360, 330)
        self.window.add_css_class("mochi-focus-window")
        self.window.connect("close-request", self._on_close_request)

        css = Gtk.CssProvider()
        css.load_from_string(FOCUS_CSS)
        Gtk.StyleContext.add_provider_for_display(
            owner.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._css = css

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(keys)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)

        kicker = Gtk.Label(label="WORK WITH MOCHI")
        kicker.set_xalign(0)
        kicker.add_css_class("mochi-focus-kicker")
        root.append(kicker)

        title = Gtk.Label(label="Focus with Mochi")
        title.set_xalign(0)
        title.add_css_class("mochi-focus-title")
        root.append(title)

        subtitle = Gtk.Label(
            label="A gentle focus timer. No streaks, no punishment, just time together."
        )
        subtitle.set_xalign(0)
        subtitle.set_wrap(True)
        subtitle.add_css_class("mochi-focus-subtitle")
        root.append(subtitle)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(160)
        self._stack.set_vexpand(True)
        self._stack.add_named(self._build_setup_page(), "setup")
        self._stack.add_named(self._build_session_page(), "session")
        root.append(self._stack)

        self.window.set_child(root)

    def _build_setup_page(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("mochi-focus-card")
        card.set_margin_top(4)

        self._focus_minutes = self._spin_row(
            card,
            "Focus",
            minimum=5,
            maximum=120,
            value=25,
            suffix="min",
        )
        self._break_minutes = self._spin_row(
            card,
            "Break",
            minimum=1,
            maximum=30,
            value=5,
            suffix="min",
        )
        self._rounds = self._spin_row(
            card,
            "Rounds",
            minimum=1,
            maximum=8,
            value=4,
            suffix="",
        )

        encourage_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        encourage_label = Gtk.Label(label="Gentle encouragement")
        encourage_label.set_xalign(0)
        encourage_label.set_hexpand(True)
        encourage_row.append(encourage_label)
        self._encouragement = Gtk.Switch()
        self._encouragement.set_active(True)
        self._encouragement.set_valign(Gtk.Align.CENTER)
        encourage_row.append(self._encouragement)
        card.append(encourage_row)

        if self._rain_available:
            self._setup_rain_switch, self._setup_rain_volume = self._rain_controls()
            card.append(self._soundscape_row(
                self._setup_rain_switch,
                self._setup_rain_volume,
            ))

        note = Gtk.Label(
            label="Focus time earns bond XP. Breaks are yours — Mochi does not grade them."
        )
        note.set_xalign(0)
        note.set_wrap(True)
        note.add_css_class("mochi-focus-secondary")
        card.append(note)

        start = Gtk.Button(label="Start focusing")
        start.add_css_class("mochi-focus-primary")
        start.connect("clicked", self._on_start_clicked)
        card.append(start)
        return card

    def _build_session_page(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("mochi-focus-card")
        card.set_margin_top(4)

        self._phase_label = Gtk.Label(label="Focus 1 of 4")
        self._phase_label.set_xalign(0)
        self._phase_label.add_css_class("mochi-focus-secondary")
        card.append(self._phase_label)

        self._timer_label = Gtk.Label(label="25:00")
        self._timer_label.set_halign(Gtk.Align.CENTER)
        self._timer_label.add_css_class("mochi-focus-timer")
        card.append(self._timer_label)

        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(False)
        card.append(self._progress)

        self._earned_label = Gtk.Label(label="0 focused minutes together")
        self._earned_label.set_xalign(0)
        self._earned_label.add_css_class("mochi-focus-secondary")
        card.append(self._earned_label)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        actions.set_homogeneous(True)

        self._pause_button = Gtk.Button(label="Pause")
        self._pause_button.add_css_class("mochi-focus-secondary-button")
        self._pause_button.connect("clicked", self._on_pause_clicked)
        actions.append(self._pause_button)

        self._cancel_button = Gtk.Button(label="Stop session")
        self._cancel_button.add_css_class("mochi-focus-secondary-button")
        self._cancel_button.connect("clicked", self._on_cancel_clicked)
        actions.append(self._cancel_button)

        card.append(actions)

        if self._rain_available:
            self._session_rain_switch, self._session_rain_volume = self._rain_controls()
            card.append(self._soundscape_row(
                self._session_rain_switch,
                self._session_rain_volume,
            ))

        hint = Gtk.Label(
            label="You can close this window. The timer keeps going with Mochi."
        )
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("mochi-focus-secondary")
        card.append(hint)
        return card

    def _rain_controls(self) -> tuple[Gtk.Switch, Gtk.Scale]:
        toggle = Gtk.Switch()
        toggle.set_active(self._rain_enabled)
        toggle.set_valign(Gtk.Align.CENTER)
        toggle.connect("notify::active", self._on_rain_toggle_changed)

        volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.05)
        volume.set_value(self._rain_volume)
        volume.set_draw_value(False)
        volume.set_hexpand(True)
        volume.set_sensitive(self._rain_enabled)
        volume.connect("value-changed", self._handle_rain_volume_changed)
        return toggle, volume

    def _soundscape_row(self, toggle: Gtk.Switch, volume: Gtk.Scale) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        label = Gtk.Label(label="Rain sounds")
        label.set_xalign(0)
        label.set_hexpand(True)
        header.append(label)
        header.append(toggle)
        row.append(header)

        volume_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_label = Gtk.Label(label="Rain volume")
        volume_label.set_xalign(0)
        volume_label.add_css_class("mochi-focus-secondary")
        volume_row.append(volume_label)
        volume_row.append(volume)
        row.append(volume_row)
        return row

    def _spin_row(
        self,
        parent: Gtk.Box,
        label: str,
        *,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
    ) -> Gtk.SpinButton:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)

        spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        spin.set_value(value)
        spin.set_numeric(True)
        spin.set_size_request(78, -1)
        row.append(spin)

        if suffix:
            unit = Gtk.Label(label=suffix)
            unit.add_css_class("mochi-focus-secondary")
            row.append(unit)

        parent.append(row)
        return spin

    def present_setup(self, plan: FocusPlan | None = None) -> None:
        plan = plan or FocusPlan()
        self._focus_minutes.set_value(plan.focus_minutes)
        self._break_minutes.set_value(plan.break_minutes)
        self._rounds.set_value(plan.rounds)
        self._encouragement.set_active(plan.encouragement_enabled)
        self._sync_rain_controls()
        self._stack.set_visible_child_name("setup")
        self.window.present()

    def present_session(self, session: FocusSession) -> None:
        self._stack.set_visible_child_name("session")
        self.update_session(session)
        self.window.present()

    def update_session(self, session: FocusSession) -> None:
        self._phase_label.set_text(session.phase_label)
        self._timer_label.set_text(session.remaining_label)
        self._progress.set_fraction(session.progress_fraction)
        self._earned_label.set_text(
            f"{session.focus_minutes_completed} focused minutes together"
        )

        complete = session.phase is FocusPhase.COMPLETE
        self._pause_button.set_sensitive(not complete)
        self._pause_button.set_label("Resume" if session.paused else "Pause")
        self._cancel_button.set_label("Done" if complete else "Stop session")
        self._sync_rain_controls()

    def destroy(self) -> None:
        self.window.destroy()

    def _on_start_clicked(self, _button: Gtk.Button) -> None:
        plan = FocusPlan(
            focus_minutes=self._focus_minutes.get_value_as_int(),
            break_minutes=self._break_minutes.get_value_as_int(),
            rounds=self._rounds.get_value_as_int(),
            encouragement_enabled=self._encouragement.get_active(),
        )
        self._on_start(plan)

    def _on_pause_clicked(self, _button: Gtk.Button) -> None:
        self._on_pause()

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self._on_cancel()

    def _on_rain_toggle_changed(self, switch: Gtk.Switch, _detail) -> None:
        enabled = switch.get_active()
        if enabled == self._rain_enabled:
            return
        self._rain_enabled = enabled
        self._on_rain_enabled(enabled)
        self._sync_rain_controls()

    def _handle_rain_volume_changed(self, scale: Gtk.Scale) -> None:
        volume = scale.get_value()
        if abs(volume - self._rain_volume) < 0.001:
            return
        self._rain_volume = volume
        self._sync_rain_controls()
        self._on_rain_volume_change(self._rain_volume)

    def _sync_rain_controls(self) -> None:
        for name in ("_setup_rain_switch", "_session_rain_switch"):
            switch = getattr(self, name, None)
            if switch is not None and switch.get_active() != self._rain_enabled:
                switch.set_active(self._rain_enabled)
        for name in ("_setup_rain_volume", "_session_rain_volume"):
            scale = getattr(self, name, None)
            if scale is not None:
                scale.set_sensitive(self._rain_enabled)
                if abs(scale.get_value() - self._rain_volume) >= 0.001:
                    scale.set_value(self._rain_volume)

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self.window.hide()
        return True

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.window.hide()
            return True
        return False


class FocusSessionMixin:
    """Add a low-pressure Pomodoro loop without creating a second state machine."""

    FOCUS_WORK_ANIMATION = "computer_typing"
    FOCUS_EXIT_ANIMATION = "computer_outro"

    def __init__(self, *args, **kwargs) -> None:
        self._focus_window: FocusWindow | None = None
        self._focus_session: FocusSession | None = None
        self._focus_plan = FocusPlan()
        self._focus_source_id: int | None = None
        self._focus_last_tick: float | None = None
        self._focus_ambience = FocusAmbienceManager()
        self._focus_completion_heart_pending = False
        super().__init__(*args, **kwargs)

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        button, _ = self._make_menu_button(
            "Focus with Mochi",
            "alarm-symbolic",
            self._show_focus_from_context_menu,
        )
        button.set_tooltip_text("Start a gentle focus session with Mochi")
        self._register_context_menu_row(
            "focus",
            button,
            before="sleep",
        )
        return menu

    def _show_focus_from_context_menu(self, _button: Gtk.Button) -> None:
        self._close_context_menu_then(self._show_focus_window)

    def _show_focus_window(self) -> None:
        if self._focus_window is None:
            self._focus_window = FocusWindow(
                owner=self._window,
                on_start=self._start_focus_session,
                on_pause=self._toggle_focus_pause,
                on_cancel=self._cancel_focus_session,
                on_rain_enabled=self._set_focus_rain_enabled,
                on_rain_volume_changed=self._set_focus_rain_volume,
                rain_available="mochi_rain" in self._focus_ambience.available_soundscapes,
                rain_enabled=self._focus_ambience.selected_name == "mochi_rain",
                rain_volume=self._focus_ambience.volume,
                logger=self._logger,
            )

        session = self._focus_session
        if session is not None:
            self._focus_window.present_session(session)
            return

        # Reuse the ordinary computer emote as the setup "getting ready" beat.
        # The existing emote owns its own eligibility checks, so opening Focus
        # never force-interrupts a higher-priority interaction.
        self._start_computer_emote()
        self._focus_window.present_setup(self._focus_plan)

    def _start_focus_session(self, plan: FocusPlan) -> None:
        if self._focus_session is not None and self._focus_session.active:
            return

        self._focus_plan = plan
        self._focus_session = FocusSession(plan)
        self._focus_last_tick = time.monotonic()
        self._focus_completion_heart_pending = False
        self._dismiss_presence_bubble(user_initiated=False)

        if self.state.current is MochiState.SLEEPING:
            self._wake_up()
        self._ensure_focus_visual()
        self._resume_focus_ambience()

        if self._focus_source_id is not None:
            GLib.source_remove(self._focus_source_id)
        self._focus_source_id = GLib.timeout_add(
            FOCUS_TIMER_TICK_MS,
            self._focus_tick,
        )

        if self._focus_window is not None:
            self._focus_window.present_session(self._focus_session)

        self._logger.info(
            "Focus session started: %dm focus / %dm break / %d rounds",
            plan.focus_minutes,
            plan.break_minutes,
            plan.rounds,
        )

    def _set_focus_rain_enabled(self, enabled: bool) -> None:
        if enabled:
            if not self._focus_ambience.select("mochi_rain"):
                return
            session = self._focus_session
            if session is not None and session.active and not session.paused:
                self._focus_ambience.start_selected()
            return
        self._focus_ambience.select(None)

    def _set_focus_rain_volume(self, volume: float) -> None:
        self._focus_ambience.set_volume(volume)
        session = self._focus_session
        if (
            session is not None
            and session.active
            and not session.paused
            and self._focus_ambience.active_name is None
        ):
            self._focus_ambience.start_selected()

    def _focus_tick(self) -> bool:
        session = self._focus_session
        if session is None or not session.active:
            self._focus_source_id = None
            return GLib.SOURCE_REMOVE

        now = time.monotonic()
        previous = self._focus_last_tick or now
        self._focus_last_tick = now
        advance = session.advance(max(0.0, now - previous))
        resumed_focus_visual = False

        if advance.xp_earned:
            award = getattr(self, "_award_bond", None)
            if callable(award):
                award(
                    advance.xp_earned,
                    persist=advance.completed,
                )

        if advance.encouragements_due:
            self._show_focus_encouragement()

        if advance.transitions:
            if session.phase is FocusPhase.COMPLETE:
                self._complete_focus_session()
            elif session.phase is FocusPhase.BREAK:
                self._stop_focus_visual()
                self._show_focus_line(FOCUS_BREAK_LINE)
            elif session.phase is FocusPhase.FOCUS:
                self._show_focus_line(FOCUS_RESUME_LINE)
                self._ensure_focus_visual()
                self._resume_focus_ambience()
                resumed_focus_visual = True

        if (
            session.phase is FocusPhase.FOCUS
            and not session.paused
            and not resumed_focus_visual
        ):
            self._ensure_focus_visual()

        if self._focus_window is not None:
            self._focus_window.update_session(session)

        if session.phase is FocusPhase.COMPLETE:
            self._focus_source_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _toggle_focus_pause(self) -> None:
        session = self._focus_session
        if session is None or not session.active:
            return

        paused = session.toggle_paused()
        self._focus_last_tick = time.monotonic()
        if paused:
            self._stop_focus_visual()
            self._focus_ambience.pause()
        else:
            if session.phase is FocusPhase.FOCUS:
                self._ensure_focus_visual()
            self._resume_focus_ambience()

        if self._focus_window is not None:
            self._focus_window.update_session(session)
        self._logger.info("Focus session %s", "paused" if paused else "resumed")

    def _cancel_focus_session(self) -> None:
        session = self._focus_session
        if session is None:
            if self._focus_window is not None:
                self._focus_window.present_setup(self._focus_plan)
            return

        was_complete = session.phase is FocusPhase.COMPLETE
        self._stop_focus_timer()
        self._stop_focus_visual()
        self._focus_ambience.stop()
        self._persist_focus_xp_if_needed()
        self._focus_plan = session.plan
        self._focus_session = None
        self._focus_last_tick = None
        self._focus_completion_heart_pending = False

        if self._focus_window is not None:
            self._focus_window.present_setup(self._focus_plan)
        if not was_complete:
            self._show_focus_line(FOCUS_CANCEL_LINE)
            self._logger.info(
                "Focus session stopped after %d focused minutes",
                session.focus_minutes_completed,
            )

    def _complete_focus_session(self) -> None:
        session = self._focus_session
        if session is None:
            return

        self._focus_completion_heart_pending = bool(
            self.state.current is MochiState.COMPUTER
            and self._current_animation in (
                self.FOCUS_WORK_ANIMATION,
                self.FOCUS_EXIT_ANIMATION,
            )
        )
        self._stop_focus_visual()
        self._focus_ambience.stop()
        self._persist_focus_xp_if_needed()
        self._show_focus_line(FOCUS_COMPLETE_LINE)

        if (
            not self._focus_completion_heart_pending
            and self.state.dialogue_allowed
            and self.state.current is MochiState.IDLE
        ):
            self._start_heart_emote(ignore_cooldown=True)

        self._logger.info(
            "Focus session completed: %d focused minutes",
            session.focus_minutes_completed,
        )

    def _show_focus_encouragement(self) -> bool:
        session = self._focus_session
        if (
            session is None
            or not session.plan.encouragement_enabled
            or session.phase is not FocusPhase.FOCUS
            or session.paused
        ):
            return False

        engine = getattr(self, "_ambient_presence_engine", None)
        if engine is None:
            return False

        text = engine.phrases.choose("focus", exclude_recent=True)
        shown = self._show_focus_bubble(text)
        if shown:
            self._logger.debug("[focus] encouragement text=%r", text)
        return shown

    def _show_focus_line(self, text: str) -> bool:
        return self._show_focus_bubble(text)

    def _show_focus_bubble(self, text: str) -> bool:
        engine = getattr(self, "_ambient_presence_engine", None)
        bubble = getattr(self, "_presence_bubble", None)
        if engine is None or bubble is None or not self.state.dialogue_allowed:
            return False

        tuning = engine.tuning
        if not tuning.speech_enabled or tuning.quiet_mode:
            return False

        self._dismiss_presence_bubble(user_initiated=False)
        shown = bubble.show(
            text,
            duration_seconds=min(4.0, speech_display_seconds(text)),
        )
        if shown:
            engine.phrases.remember(text)
        return shown

    def _focus_should_work(self) -> bool:
        session = self._focus_session
        return bool(
            session is not None
            and session.active
            and session.phase is FocusPhase.FOCUS
            and not session.paused
        )

    def _focus_allows_presence_action(self, action) -> bool:
        """Keep focused work quiet without touching AmbiSense queues or tuning."""
        if not self._focus_should_work():
            return True
        return getattr(action, "priority", 0) >= FOCUS_PRESENCE_PRIORITY_FLOOR

    def _resume_focus_ambience(self) -> None:
        if self._focus_ambience.active_name is None:
            self._focus_ambience.start_selected()
        else:
            self._focus_ambience.resume()

    def _ensure_focus_visual(self) -> bool:
        if not self._focus_should_work() or self._context_menu_open:
            return False

        if self.state.current is MochiState.SLEEPING:
            self._wake_up()
            return False

        if self.state.current is MochiState.WALKING:
            self._cancel_walk()
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")

        if self.state.current is MochiState.COMPUTER:
            if self._current_animation == self.FOCUS_WORK_ANIMATION:
                return True
            self._play_animation(self.FOCUS_WORK_ANIMATION, after=None)
            return True

        if self.state.current is not MochiState.IDLE:
            self._cancel_active_emote()

        if (
            self.state.current is not MochiState.IDLE
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        if not self._transition_to(MochiState.COMPUTER):
            return False

        self._play_animation(self.FOCUS_WORK_ANIMATION, after=None)
        self._logger.debug("Focus coworking reused computer typing loop")
        return True

    def _stop_focus_visual(self) -> None:
        if self.state.current is not MochiState.COMPUTER:
            return
        if self._current_animation == self.FOCUS_EXIT_ANIMATION:
            return
        self._play_animation(self.FOCUS_EXIT_ANIMATION, after="idle")

    def _finish_reaction(self, finished_animation) -> None:
        finishing_focus_exit = bool(
            finished_animation is self._active_animation
            and self._current_animation == self.FOCUS_EXIT_ANIMATION
        )
        super()._finish_reaction(finished_animation)

        if (
            finishing_focus_exit
            and self._focus_completion_heart_pending
            and self.state.current is MochiState.IDLE
        ):
            self._focus_completion_heart_pending = False
            if self.state.dialogue_allowed:
                self._start_heart_emote(ignore_cooldown=True)

    def _stop_focus_timer(self) -> None:
        source_id = self._focus_source_id
        self._focus_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _persist_focus_xp_if_needed(self) -> None:
        if getattr(self, "_bond_unsaved_xp", 0) <= 0:
            return
        persist = getattr(self, "_persist_bond_state", None)
        if callable(persist):
            persist()

    def _start_typing_emote(self) -> bool:
        if self._focus_should_work():
            return self._ensure_focus_visual()
        return super()._start_typing_emote()

    def _maybe_resume_ambient_activity(self) -> bool:
        if self._focus_should_work():
            return self._ensure_focus_visual()
        return super()._maybe_resume_ambient_activity()

    def _begin_sleep(self) -> None:
        if self._focus_should_work():
            self._logger.debug("Automatic sleep deferred during focus session")
            return
        super()._begin_sleep()

    def _toggle_sleep(self, *args, **kwargs) -> None:
        session = self._focus_session
        choosing_sleep = self.state.current is not MochiState.SLEEPING
        if (
            choosing_sleep
            and session is not None
            and session.active
            and not session.paused
        ):
            session.set_paused(True)
            self._stop_focus_visual()
            self._focus_ambience.pause()
            if self._focus_window is not None:
                self._focus_window.update_session(session)
        super()._toggle_sleep(*args, **kwargs)

    def shutdown_presence(self) -> None:
        self._stop_focus_timer()
        self._focus_ambience.stop()
        self._persist_focus_xp_if_needed()
        if self._focus_window is not None:
            self._focus_window.destroy()
            self._focus_window = None
        self._focus_session = None
        self._focus_last_tick = None
        self._focus_completion_heart_pending = False
        super().shutdown_presence()
