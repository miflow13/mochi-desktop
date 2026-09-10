"""Thin integration layer between Buddy and the ambient presence engine."""

from __future__ import annotations

import time

from gi.repository import GLib, Gtk

from mochi.buddy import Buddy
from mochi.state import MochiState
from mochi.x11_buddy import X11Buddy

from .bubble import SpeechBubble
from .context import AmbientContext
from .engine import PresenceEngine
from .signals import AppCategorySignalAdapter, SystemSignalMonitor


class PresenceBuddyMixin:
    """Add ambient presence without changing Buddy's proven interaction code."""

    PRESENCE_EVALUATION_SECONDS = 5

    def __init__(self, *args, **kwargs) -> None:
        self._ambient_presence_engine = PresenceEngine()
        self._presence_started_at = time.monotonic()
        self._presence_active_session_started_at = self._presence_started_at
        self._presence_bubble: SpeechBubble | None = None
        self._system_signal_monitor: SystemSignalMonitor | None = None
        self._app_category_monitor: AppCategorySignalAdapter | None = None
        self._presence_app_category = "unknown"
        self._presence_source_id: int | None = None
        self._presence_shutting_down = False
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

    @property
    def presence_engine(self) -> PresenceEngine:
        """Developer/test access without adding fragile menu controls."""
        return self._ambient_presence_engine

    def _build_developer_menu(self):
        """Extend Mochi Lab with isolated presence controls.

        Buddy still owns all menu behavior. Presence only appends widgets to the
        finished developer card, avoiding changes to the context-menu path.
        """
        popover = super()._build_developer_menu()
        card = self._developer_menu_content
        animated_rows = list(self._developer_menu_animated_rows)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        presence_label = Gtk.Label(label="Presence")
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

        self._developer_menu_animated_rows = tuple(animated_rows)

        # The presence rows extend Mochi Lab's natural height. Keep the menu
        # positioner aware of that size so it clamps correctly on each monitor.
        popover._preferred_height = 860
        popover.window.set_default_size(332, 860)
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

    def _test_presence_ambient(self, _button: Gtk.Button) -> None:
        self._close_developer_menu_then(self._force_presence_ambient_now)

    def _force_presence_ambient_now(self) -> None:
        self._ambient_presence_engine.force_ambient()
        self._evaluate_ambient_presence()

    def _test_presence_contextual(self, _button: Gtk.Button) -> None:
        self._close_developer_menu_then(self._force_presence_contextual_now)

    def _force_presence_contextual_now(self) -> None:
        category = {
            "editor": "developer",
            "terminal": "developer",
            "pixel_art": "creative",
            "media": "media",
            "browser": "focus",
        }.get(self._presence_app_category, "ambient")
        self._ambient_presence_engine.force_contextual(category)
        self._evaluate_ambient_presence()

    def set_presence_quiet_mode(self, enabled: bool) -> None:
        self._ambient_presence_engine.set_quiet_mode(enabled)
        if enabled:
            self._dismiss_presence_bubble(user_initiated=False)

    def _on_typing_activity(self) -> None:
        self._ambient_presence_engine.record_typing_activity()
        super()._on_typing_activity()

    def _on_typing_stopped(self) -> None:
        self._ambient_presence_engine.record_typing_stopped()
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
        self._presence_app_category = category

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
        if self._system_signal_monitor is not None:
            self._system_signal_monitor.stop()
        if self._app_category_monitor is not None:
            self._app_category_monitor.stop()
        if self._presence_bubble is not None:
            self._presence_bubble.hide()


class PresenceBuddy(PresenceBuddyMixin, Buddy):
    """Wayland/layer-shell Buddy with ambient presence."""


class PresenceX11Buddy(PresenceBuddyMixin, X11Buddy):
    """X11/XWayland Buddy with ambient presence and unchanged drag behavior."""
