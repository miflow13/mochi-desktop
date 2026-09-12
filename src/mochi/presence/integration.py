"""Thin integration layer between Buddy and AmbiSense ambient awareness."""

from __future__ import annotations

import random
import time

from gi.repository import GLib, Gtk

from mochi.buddy import Buddy
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState
from mochi.x11_buddy import X11Buddy

from .bubble import SpeechBubble
from .context import AmbientContext
from .engine import PresenceEngine, PresenceTuning, speech_display_seconds
from .signals import AppCategorySignalAdapter, SystemSignalMonitor


class PresenceBuddyMixin:
    """Add AmbiSense without changing Buddy's proven interaction code."""

    PRESENCE_EVALUATION_SECONDS = 5
    STARTUP_GREETING_DELAY_MS = 1_100
    VSCODE_COWORK_DEBOUNCE_MS = 700

    def __init__(self, *args, **kwargs) -> None:
        self._ambient_presence_engine = PresenceEngine()
        # AmbiSense is lively by default. Extra-chatty remains an optional
        # developer stress-test profile rather than defining normal behavior.
        self._presence_chatty_test_mode = False
        self._presence_chatty_switch: Gtk.Switch | None = None
        self._stay_put = False
        self._stay_put_switch: Gtk.Switch | None = None
        self._presence_started_at = time.monotonic()
        self._presence_active_session_started_at = self._presence_started_at
        self._presence_bubble: SpeechBubble | None = None
        self._system_signal_monitor: SystemSignalMonitor | None = None
        self._app_category_monitor: AppCategorySignalAdapter | None = None
        self._presence_app_category = "unknown"
        self._presence_source_id: int | None = None
        self._presence_startup_source_id: int | None = None
        self._presence_shutting_down = False
        self._vscode_cowork_source_id: int | None = None
        self._vscode_coworking_active = False
        super().__init__(*args, **kwargs)

        if self._preview_mode:
            return

        self._ambient_presence_engine._logger = self._logger
        self._presence_bubble = SpeechBubble(
            owner=self._window,
            anchor_widget=self,
            logger=self._logger,
        )
        self._system_signal_monitor = SystemSignalMonitor(
            on_battery_low=self._on_presence_battery_low,
            on_charging_started=self._on_presence_charging_started,
            on_network_lost=self._on_presence_network_lost,
            on_network_restored=self._on_presence_network_restored,
            logger=self._logger,
        )
        self._system_signal_monitor.start()
        self._app_category_monitor = AppCategorySignalAdapter(
            on_category_changed=self._on_presence_app_category_changed,
            logger=self._logger,
        )
        if self._app_category_monitor.start():
            self._logger.info("Ambient app-category awareness enabled via GNOME Shell")
        else:
            self._logger.debug(
                "Ambient app-category awareness unavailable: %s",
                self._app_category_monitor.last_error,
            )
        self._presence_source_id = GLib.timeout_add_seconds(
            self.PRESENCE_EVALUATION_SECONDS,
            self._evaluate_ambient_presence,
        )
        self._presence_startup_source_id = GLib.timeout_add(
            self.STARTUP_GREETING_DELAY_MS,
            self._show_startup_greeting,
        )

    @property
    def presence_engine(self) -> PresenceEngine:
        """Developer/test access to the AmbiSense decision engine."""
        return self._ambient_presence_engine

    def _build_context_menu(self):
        """Add one persistent movement preference to the tiny user menu."""
        popover = super()._build_context_menu()
        self._stay_put = self._config.load_stay_put()

        stay_row, self._stay_put_switch = self._make_stay_put_row()
        card = self._context_menu_content
        card.insert_child_after(stay_row, self._sleep_button)

        existing_rows = list(self._context_menu_animated_rows)
        if existing_rows:
            self._context_menu_animated_rows = (
                existing_rows[0],
                stay_row,
                *existing_rows[1:],
            )
        else:
            self._context_menu_animated_rows = (stay_row,)

        popover._preferred_height = max(popover._preferred_height, 224)
        popover.window.set_default_size(popover._preferred_width, popover._preferred_height)
        return popover

    def _make_stay_put_row(self) -> tuple[Gtk.Button, Gtk.Switch]:
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        button.set_tooltip_text("Prevent Mochi from wandering on his own")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("media-playback-pause-symbolic")
        icon.add_css_class("mochi-menu-icon")
        row.append(icon)

        text = Gtk.Label(label="Stay put")
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)

        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_active(self._stay_put)
        # Let the parent button own the pointer sequence. This mirrors the
        # reliable Extra-chatty row and avoids nested click targets in MenuWindow.
        switch.set_can_target(False)
        switch.set_focusable(False)
        row.append(switch)

        button.set_child(row)
        button.connect("clicked", self._toggle_stay_put)
        return button, switch

    def _toggle_stay_put(self, _button: Gtk.Button) -> None:
        self._stay_put = not self._stay_put
        self._config.save_stay_put(self._stay_put)
        if self._stay_put_switch is not None:
            self._stay_put_switch.set_active(self._stay_put)

        # Enabling Stay put while Mochi is already strolling should take effect
        # immediately. Manual dragging and developer-forced walks remain allowed.
        if self._stay_put and self.state.current is MochiState.WALKING:
            self._cancel_walk()
            if self._transition_to(MochiState.IDLE):
                self._play_animation("idle")

        self._logger.info("Stay put %s", "enabled" if self._stay_put else "disabled")

    def _choose_idle_action(self) -> bool:
        """Suppress only autonomous walking while Stay put is enabled."""
        if not self._stay_put or self._user_idle:
            return super()._choose_idle_action()

        self._idle_action_source_id = None
        try:
            if self.state.current is not MochiState.IDLE or self._context_menu_open:
                return GLib.SOURCE_REMOVE

            # Keep the same 25% squish chance as the normal idle pool; only the
            # autonomous walk slot is removed. Reading/other quiet emotes can be
            # added to this ambient pool later without changing movement logic.
            action = random.choice(("squish", None, None, None))
            if action == "squish":
                self._transition_to(MochiState.SQUISHING)
                self._play_animation("squish")
            return GLib.SOURCE_REMOVE
        finally:
            self._schedule_idle_action()

    def _build_developer_menu(self):
        """Extend Mochi Lab with isolated AmbiSense controls.

        Buddy still owns the developer surface and lifecycle. AmbiSense appends
        its widgets without changing the user menu lifecycle, then promotes the
        Lab surface into a conventional resizable, scrollable GTK window.
        """
        popover = super()._build_developer_menu()
        card = self._developer_menu_content
        animated_rows = list(self._developer_menu_animated_rows)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        presence_label = Gtk.Label(label="AmbiSense")
        presence_label.set_xalign(0)
        presence_label.add_css_class("mochi-menu-section")
        card.append(presence_label)

        speech_row = self._make_presence_switch_row(
            "Speech bubbles",
            self._ambient_presence_engine.tuning.speech_enabled,
            self._change_presence_speech_enabled,
        )
        card.append(speech_row)
        animated_rows.append(speech_row)

        reactions_row = self._make_presence_switch_row(
            "Ambient reactions",
            self._ambient_presence_engine.tuning.ambient_reactions_enabled,
            self._change_presence_reactions_enabled,
        )
        card.append(reactions_row)
        animated_rows.append(reactions_row)

        quiet_row = self._make_presence_switch_row(
            "Quiet mode",
            self._ambient_presence_engine.tuning.quiet_mode,
            self._change_presence_quiet_mode,
        )
        card.append(quiet_row)
        animated_rows.append(quiet_row)

        # Extra-chatty is intentionally button-backed. The normal AmbiSense
        # profile is already lively; this control exists only for stress testing.
        chatty_row, self._presence_chatty_switch = self._make_presence_chatty_row()
        card.append(chatty_row)
        animated_rows.append(chatty_row)

        ambient_button, _ = self._make_menu_button(
            "Say something now",
            "dialog-information-symbolic",
            self._test_presence_ambient,
        )
        card.append(ambient_button)
        animated_rows.append(ambient_button)

        contextual_button, _ = self._make_menu_button(
            "Say something contextual",
            "system-run-symbolic",
            self._test_presence_contextual,
        )
        card.append(contextual_button)
        animated_rows.append(contextual_button)

        typing_button, _ = self._make_menu_button(
            "Preview typing phrase",
            "input-keyboard-symbolic",
            self._test_presence_typing,
        )
        card.append(typing_button)
        animated_rows.append(typing_button)

        self._developer_menu_animated_rows = tuple(animated_rows)

        # Mochi Lab has outgrown a menu-sized surface. Keep the proven MenuWindow
        # lifecycle/callback plumbing, but present only this developer surface as
        # a conventional resizable window with a bounded viewport and scrolling.
        popover.window.set_decorated(True)
        popover.window.set_resizable(True)
        popover.window.set_title("Mochi Lab")
        popover._preferred_width = 560
        popover._preferred_height = 620
        popover.window.set_default_size(560, 620)
        popover.window.set_size_request(420, 360)

        # Buddy originally parented the card directly to the MenuWindow. Detach
        # it once, then put the same live controls inside a scroll container.
        popover.window.set_child(None)
        card.set_size_request(-1, -1)
        card.set_hexpand(True)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_min_content_width(420)
        scroller.set_min_content_height(360)
        scroller.add_css_class("mochi-dev-scroll")
        scroller.set_child(card)
        popover.set_child(scroller)
        return popover

    def _make_presence_switch_row(self, label: str, active: bool, callback):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("mochi-setting-row")
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)
        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_active(active)
        switch.connect("notify::active", callback)
        row.append(switch)
        return row

    def _make_presence_chatty_row(self) -> tuple[Gtk.Button, Gtk.Switch]:
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        button.set_tooltip_text(
            "Stress-test AmbiSense with much faster ambient speech"
        )

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        text = Gtk.Label(label="Extra chatty")
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)

        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_active(self._presence_chatty_test_mode)
        # The parent button owns pointer interaction so the whole row is one
        # predictable hit target instead of two competing GTK controls.
        switch.set_can_target(False)
        switch.set_focusable(False)
        row.append(switch)

        button.set_child(row)
        button.connect("clicked", self._toggle_presence_chatty_test_mode)
        return button, switch

    def _close_developer_menu_then(self, action) -> None:
        """Run developer actions without closing Mochi Lab.

        Buddy's test actions normally refuse to run while a menu is open. The
        Lab is a persistent debug surface, so temporarily relax only that guard
        for the dispatched action, then restore the real menu-open state.
        """
        GLib.idle_add(self._dispatch_presence_developer_action, action)

    def _dispatch_presence_developer_action(self, action) -> bool:
        self._context_menu_open = False
        try:
            action()
        finally:
            self._context_menu_open = bool(self._developer_menu.get_visible())
        return GLib.SOURCE_REMOVE

    def _change_presence_speech_enabled(self, switch: Gtk.Switch, _pspec=None) -> None:
        enabled = switch.get_active()
        self._ambient_presence_engine.set_speech_enabled(enabled)
        if not enabled:
            self._dismiss_presence_bubble(user_initiated=False)

    def _change_presence_reactions_enabled(
        self, switch: Gtk.Switch, _pspec=None
    ) -> None:
        enabled = switch.get_active()
        self._ambient_presence_engine.set_ambient_reactions_enabled(enabled)
        if not enabled:
            self._dismiss_presence_bubble(user_initiated=False)

    def _change_presence_quiet_mode(self, switch: Gtk.Switch, _pspec=None) -> None:
        self.set_presence_quiet_mode(switch.get_active())

    def _toggle_presence_chatty_test_mode(self, _button: Gtk.Button) -> None:
        enabled = not self._presence_chatty_test_mode
        self._apply_presence_chatty_test_mode(enabled)
        if self._presence_chatty_switch is not None:
            self._presence_chatty_switch.set_active(enabled)
        self._logger.info(
            "Mochi Lab extra-chatty mode toggled to %s",
            "ON" if enabled else "OFF",
        )

    def _apply_presence_chatty_test_mode(
        self, enabled: bool, *, clear_cooldowns: bool = True
    ) -> None:
        """Swap between normal AmbiSense and an aggressive stress-test profile."""
        self._presence_chatty_test_mode = bool(enabled)
        engine = self._ambient_presence_engine
        tuning = engine.tuning

        profile_fields = (
            "ambient_min_seconds",
            "ambient_max_seconds",
            "ambient_silence_probability",
            "global_cooldown_seconds",
            "same_category_min_seconds",
            "same_category_max_seconds",
            "max_phrases_per_hour",
            "typing_medium_sustain_seconds",
            "typing_high_sustain_seconds",
            "typing_comment_probability",
            "return_probability",
            "media_probability",
            "system_event_probability",
            "build_event_probability",
        )

        if enabled:
            tuning.ambient_min_seconds = 8.0
            tuning.ambient_max_seconds = 20.0
            tuning.ambient_silence_probability = 0.05
            tuning.global_cooldown_seconds = 10.0
            tuning.same_category_min_seconds = 30.0
            tuning.same_category_max_seconds = 75.0
            tuning.max_phrases_per_hour = 60
            tuning.typing_medium_sustain_seconds = 6.0
            tuning.typing_high_sustain_seconds = 4.0
            tuning.typing_comment_probability = 1.0
            tuning.return_probability = 1.0
            tuning.media_probability = 1.0
            tuning.system_event_probability = 1.0
            tuning.build_event_probability = 1.0
        else:
            defaults = PresenceTuning()
            for field_name in profile_fields:
                setattr(tuning, field_name, getattr(defaults, field_name))

        engine.cooldowns.global_gap_seconds = tuning.global_cooldown_seconds
        engine.cooldowns.max_per_hour = tuning.max_phrases_per_hour
        if clear_cooldowns:
            engine.cooldowns.clear()
        engine._next_ambient_at = time.monotonic() + engine._ambient_delay()

        logger = getattr(self, "_logger", None)
        if logger is not None:
            logger.info(
                "AmbiSense extra-chatty mode %s",
                "enabled" if enabled else "disabled",
            )

    def _test_presence_ambient(self, _button: Gtk.Button) -> None:
        self._preview_presence_category("ambient")

    def _test_presence_contextual(self, _button: Gtk.Button) -> None:
        category = {
            "vscode": "vscode",
            "editor": "developer",
            "terminal": "developer",
            "pixel_art": "creative",
            "media": "media",
            "browser": "focus",
        }.get(self._presence_app_category, "ambient")
        self._preview_presence_category(category)

    def _test_presence_typing(self, _button: Gtk.Button) -> None:
        self._preview_presence_category("typing")

    def _preview_presence_category(self, category: str) -> None:
        """Deterministically preview one phrase while Mochi Lab stays open.

        Developer previews intentionally bypass ambient cooldowns, silence
        probability, menu suppression, and recent-dismiss suppression. They do
        not count against production rate limits. If a preview bubble is still
        visible, replace it so every button press gives immediate feedback.
        """
        bubble = self._presence_bubble
        if bubble is None:
            self._logger.debug("[presence] developer preview unavailable: no bubble")
            return

        self._dismiss_presence_bubble(user_initiated=False)
        try:
            text = self._ambient_presence_engine.phrases.choose(
                category,
                exclude_recent=True,
            )
        except KeyError:
            category = "ambient"
            text = self._ambient_presence_engine.phrases.choose(
                category,
                exclude_recent=True,
            )

        if bubble.show(text, duration_seconds=speech_display_seconds(text)):
            # Remember only the text for variety. A developer preview must not
            # consume global/category cooldown budget used by ambient speech.
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug(
                "[presence] developer preview category=%s text=%r",
                category,
                text,
            )

    def _show_startup_greeting(self) -> bool:
        """Give Mochi one tiny hello shortly after the desktop buddy appears."""
        self._presence_startup_source_id = None
        if self._presence_shutting_down or self._preview_mode:
            return GLib.SOURCE_REMOVE
        tuning = self._ambient_presence_engine.tuning
        if (
            not tuning.speech_enabled
            or not tuning.ambient_reactions_enabled
            or tuning.quiet_mode
            or self._user_idle
            or self._presence_bubble is None
        ):
            return GLib.SOURCE_REMOVE

        text = self._ambient_presence_engine.phrases.choose(
            "startup",
            exclude_recent=True,
        )
        if self._presence_bubble.show(
            text,
            duration_seconds=speech_display_seconds(text),
        ):
            # Startup is a greeting, not an ambient interruption. Remember the
            # phrase for variety but do not spend the normal cooldown budget.
            self._ambient_presence_engine.phrases.remember(text)
            self._logger.debug("[presence] startup greeting text=%r", text)
        return GLib.SOURCE_REMOVE

    def set_presence_quiet_mode(self, enabled: bool) -> None:
        self._ambient_presence_engine.set_quiet_mode(enabled)
        if enabled:
            self._dismiss_presence_bubble(user_initiated=False)

    def _on_typing_activity(self) -> None:
        self._ambient_presence_engine.record_typing_activity()
        super()._on_typing_activity()

    def _on_typing_stopped(self) -> None:
        self._ambient_presence_engine.record_typing_stopped()
        # VS Code coworking intentionally holds the typing loop open even when
        # the user's current typing burst ends. Focus, not keystroke cadence,
        # owns this contextual companion mode.
        if (
            self._presence_app_category == "vscode"
            and self.state.current is MochiState.TYPING
        ):
            self._vscode_coworking_active = True
            return
        super()._on_typing_stopped()

    def _on_youtube_started(self) -> None:
        self._ambient_presence_engine.emit("media_started")
        super()._on_youtube_started()

    def _on_youtube_stopped(self) -> None:
        super()._on_youtube_stopped()

    def _on_user_idle(self) -> None:
        self._ambient_presence_engine.note_user_idle()
        super()._on_user_idle()

    def _on_user_active(self) -> None:
        self._ambient_presence_engine.note_user_active()
        self._presence_active_session_started_at = time.monotonic()
        super()._on_user_active()
        if self._presence_app_category == "vscode":
            self._schedule_vscode_coworking()

    def _on_pressed(self, *args) -> None:
        self._dismiss_presence_bubble(user_initiated=True)
        super()._on_pressed(*args)

    def _show_context_menu(self, *args) -> None:
        self._dismiss_presence_bubble(user_initiated=True)
        super()._show_context_menu(*args)

    def _show_developer_menu(self) -> None:
        self._dismiss_presence_bubble(user_initiated=True)
        super()._show_developer_menu()

    def _begin_sleep(self) -> None:
        self._dismiss_presence_bubble(user_initiated=False)
        super()._begin_sleep()

    def _quit_application(self) -> None:
        self._shutdown_presence()
        super()._quit_application()

    def _on_presence_battery_low(self, _percent: float) -> None:
        self._ambient_presence_engine.emit("battery_low")

    def _on_presence_charging_started(self, _percent: float | None) -> None:
        self._ambient_presence_engine.emit("charging_started")

    def _on_presence_network_lost(self) -> None:
        self._ambient_presence_engine.emit("network_lost")

    def _on_presence_network_restored(self) -> None:
        self._ambient_presence_engine.emit("network_restored")

    def _on_presence_app_category_changed(self, category: str) -> None:
        previous = self._presence_app_category
        self._presence_app_category = category
        if category != previous and category in ("terminal", "vscode"):
            self._on_user_active()
        if category == "vscode":
            self._schedule_vscode_coworking()
        elif previous == "vscode" or self._vscode_coworking_active:
            self._stop_vscode_coworking()

    def _cancel_vscode_cowork_source(self) -> None:
        source_id = self._vscode_cowork_source_id
        self._vscode_cowork_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

    def _schedule_vscode_coworking(self) -> None:
        """Debounce focused VS Code before entering the persistent work loop."""
        self._cancel_vscode_cowork_source()
        if (
            self._presence_shutting_down
            or self._presence_app_category != "vscode"
            or self._user_idle
        ):
            return
        self._vscode_cowork_source_id = GLib.timeout_add(
            self.VSCODE_COWORK_DEBOUNCE_MS,
            self._begin_vscode_coworking,
        )

    def _begin_vscode_coworking(self) -> bool:
        self._vscode_cowork_source_id = None
        if (
            self._presence_shutting_down
            or self._presence_app_category != "vscode"
            or self._user_idle
            or self._context_menu_open
        ):
            return GLib.SOURCE_REMOVE

        # Real watchable media keeps the higher ambient priority. Direct
        # interactions likewise finish first and later resume through the normal
        # ambient-resume path.
        if self.state.current is MochiState.WATCHING:
            return GLib.SOURCE_REMOVE
        if self.state.current is MochiState.TYPING:
            self._vscode_coworking_active = True
            return GLib.SOURCE_REMOVE

        if self._start_typing_emote():
            self._vscode_coworking_active = True
            self._logger.debug("VS Code coworking mode started")
        return GLib.SOURCE_REMOVE

    def _stop_vscode_coworking(self) -> None:
        self._cancel_vscode_cowork_source()
        was_active = self._vscode_coworking_active
        self._vscode_coworking_active = False
        if not was_active:
            return
        if self.state.current is MochiState.TYPING:
            # Call Buddy's typing-stop transition directly. The app category has
            # already changed, so the cowork hold no longer applies.
            super()._on_typing_stopped()
        self._logger.debug("VS Code coworking mode stopped")

    def _maybe_resume_vscode_coworking(self) -> bool:
        if (
            self._presence_app_category != "vscode"
            or self._user_idle
            or self.state.current is not MochiState.IDLE
            or self._context_menu_open
            or self.player.animation is not ANIMATIONS["idle"]
        ):
            return False
        if not self._start_typing_emote():
            return False
        self._vscode_coworking_active = True
        self._logger.debug("VS Code coworking mode resumed")
        return True

    def _evaluate_ambient_presence(self) -> bool:
        if self._presence_shutting_down:
            self._presence_source_id = None
            return GLib.SOURCE_REMOVE

        now = time.monotonic()
        typing_intensity, typing_sustained = self._ambient_presence_engine.typing_snapshot(
            now=now
        )
        media_playing = bool(
            self._media_monitor is not None and self._media_monitor.youtube_playing
        )
        battery_percent = None
        charging = None
        network_connected = None
        if self._system_signal_monitor is not None:
            battery_percent = self._system_signal_monitor.battery.percent
            charging = self._system_signal_monitor.battery.charging
            network_connected = self._system_signal_monitor.network.connected

        context = AmbientContext(
            user_active=not self._user_idle,
            typing_intensity=typing_intensity,
            typing_sustained_seconds=typing_sustained,
            idle_seconds=0.0,
            session_duration=max(0.0, now - self._presence_active_session_started_at),
            battery_percent=battery_percent,
            charging=charging,
            network_connected=network_connected,
            media_playing=media_playing,
            current_app_category=(
                "media" if media_playing else self._presence_app_category
            ),
            mochi_state=self.state.current.name.lower(),
            context_menu_open=self._context_menu_open,
            interaction_active=(self._press is not None or self._drag_started),
            transition_active=self.state.current
            in {
                MochiState.PICKUP,
                MochiState.DROPPING,
                MochiState.WAKING,
            },
            overlay_visible=bool(
                self._presence_bubble is not None and self._presence_bubble.visible
            ),
            application_shutting_down=self._presence_shutting_down,
        )
        action = self._ambient_presence_engine.evaluate(context, now=now)
        if action is None or self._presence_bubble is None:
            return GLib.SOURCE_CONTINUE
        if self._presence_bubble.show(
            action.text,
            duration_seconds=action.display_seconds,
        ):
            self._ambient_presence_engine.record_delivered(action, now=now)
        return GLib.SOURCE_CONTINUE

    def _dismiss_presence_bubble(self, *, user_initiated: bool) -> None:
        bubble = self._presence_bubble
        if bubble is None or not bubble.visible:
            return
        bubble.hide()
        if user_initiated:
            self._ambient_presence_engine.note_bubble_dismissed()

    def shutdown_presence(self) -> None:
        """Stop optional presence resources during application shutdown."""
        self._shutdown_presence()

    def _shutdown_presence(self) -> None:
        if self._presence_shutting_down:
            return
        self._presence_shutting_down = True
        source_id = self._presence_source_id
        self._presence_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        self._cancel_vscode_cowork_source()
        self._vscode_coworking_active = False
        startup_source_id = self._presence_startup_source_id
        self._presence_startup_source_id = None
        if startup_source_id is not None:
            try:
                GLib.source_remove(startup_source_id)
            except Exception:
                pass
        if self._system_signal_monitor is not None:
            self._system_signal_monitor.stop()
        if self._app_category_monitor is not None:
            self._app_category_monitor.stop()
        if self._presence_bubble is not None:
            self._presence_bubble.hide()


class PresenceBuddy(PresenceBuddyMixin, Buddy):
    """Wayland/layer-shell Buddy with AmbiSense."""


class PresenceX11Buddy(PresenceBuddyMixin, X11Buddy):
    """X11/XWayland Buddy with AmbiSense and unchanged drag behavior."""
