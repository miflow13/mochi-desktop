"""GTK application and transparent top-level buddy window."""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from mochi.config import ConfigStore
from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
from mochi.sound import SoundEvent, SoundManager
from mochi.windowing import WindowPlacement
from mochi.x11 import request_keep_above


class MochiApplication(Gtk.Application):
    def __init__(
        self, config: ConfigStore, preview_animations: bool = False
    ) -> None:
        super().__init__(
            application_id=(
                "io.github.mochi_desktop.Mochi.Preview"
                if preview_animations
                else "io.github.mochi_desktop.Mochi"
            ),
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.config = config
        self.preview_animations = preview_animations
        self._logger = logging.getLogger(__name__)
        self._buddy: PresenceBuddy | PresenceX11Buddy | None = None
        self.sound = SoundManager(
            volume=config.load_volume(),
            muted=config.load_muted(),
        )

    def do_activate(self) -> None:
        existing = self.get_active_window()
        if existing is not None:
            existing.present()
            return

        window = Gtk.ApplicationWindow(application=self)
        window.set_title("Mochi Animation Preview" if self.preview_animations else "Mochi")
        window.set_decorated(False)
        window.set_resizable(False)
        window.set_focusable(False)
        size = self.config.load_size()
        window.set_default_size(size, size)

        placement = WindowPlacement(window, self.config.load_position())
        window.connect("map", self._configure_mapped_window, placement)
        buddy_class = PresenceBuddy if placement.layer_shell_enabled else PresenceX11Buddy
        buddy = buddy_class(
            window,
            placement,
            self.config,
            self.sound,
            preview_mode=self.preview_animations,
        )
        self._buddy = buddy
        window.set_child(buddy)

        css = Gtk.CssProvider()
        css.load_from_string(
            """
            window.background {
                background: unset;
            }

            window.mochi-menu-window {
                background: alpha(@window_bg_color, 0.97);
                color: @window_fg_color;
                border: 1px solid alpha(@window_fg_color, 0.10);
                border-radius: 18px;
                box-shadow: 0 12px 34px alpha(black, 0.28);
            }

            .mochi-menu-card {
                background: transparent;
            }

            .mochi-menu-title {
                font-size: 16px;
                font-weight: 700;
            }

            .mochi-menu-subtitle,
            .mochi-menu-hint,
            .mochi-menu-value,
            .mochi-menu-section {
                color: alpha(@window_fg_color, 0.58);
            }

            .mochi-menu-subtitle,
            .mochi-menu-hint {
                font-size: 11px;
            }

            .mochi-menu-section {
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.04em;
            }

            .mochi-menu-value {
                font-size: 11px;
            }

            .mochi-menu-sprout {
                font-size: 20px;
            }

            button.mochi-menu-row {
                min-height: 36px;
                padding: 4px 9px;
                border-radius: 10px;
                border: none;
                box-shadow: none;
                background: transparent;
            }

            button.mochi-menu-row:hover {
                background: alpha(@window_fg_color, 0.07);
            }

            button.mochi-menu-row:active {
                background: alpha(@window_fg_color, 0.12);
            }

            button.mochi-menu-danger {
                color: @destructive_color;
            }

            .mochi-setting-row {
                min-height: 30px;
                padding: 0 8px;
            }

            scale.mochi-menu-scale {
                margin: 0 6px 2px 6px;
            }

            .mochi-tuning-grid spinbutton {
                min-width: 92px;
            }

            separator {
                background: alpha(@window_fg_color, 0.09);
                min-height: 1px;
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            window.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        window.present()
        if not self.preview_animations:
            self.sound.play(SoundEvent.SPAWN)

    def do_shutdown(self) -> None:
        if self._buddy is not None:
            self._buddy.shutdown_presence()
            self._buddy = None
        if not self.preview_animations:
            self.sound.play(SoundEvent.EXIT)
        Gtk.Application.do_shutdown(self)

    def _configure_mapped_window(
        self, window: Gtk.Window, placement: WindowPlacement
    ) -> None:
        placement.restore()
        if request_keep_above(window):
            self._logger.info("Requested always-on-top from the X11 window manager")
