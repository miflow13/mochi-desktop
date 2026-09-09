"""GTK application and transparent top-level buddy window."""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from mochi.buddy import Buddy
from mochi.config import ConfigStore
from mochi.sound import SoundManager
from mochi.status_overlay import MochiStatusOverlay
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
        status = MochiStatusOverlay()
        buddy = Buddy(
            window,
            placement,
            self.config,
            self.sound,
            preview_mode=self.preview_animations,
            on_click=status.dismiss_for_click,
            on_hover_enter=status.hover_enter,
            on_hover_leave=status.hover_leave,
        )
        status.set_parent(buddy)
        window.set_child(buddy)
        window.connect("close-request", self._cleanup_window, buddy, status)

        css = Gtk.CssProvider()
        css.load_from_string(
            """
            window.background {
                background: unset;
            }
            """
        )
        MochiStatusOverlay.install_css(window.get_display())
        Gtk.StyleContext.add_provider_for_display(
            window.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        window.present()

    def _cleanup_window(
        self,
        _window: Gtk.Window,
        buddy: Buddy,
        status: MochiStatusOverlay,
    ) -> bool:
        status.shutdown()
        buddy.shutdown()
        return False

    def _configure_mapped_window(
        self, window: Gtk.Window, placement: WindowPlacement
    ) -> None:
        placement.restore()
        if request_keep_above(window):
            self._logger.info("Requested always-on-top from the X11 window manager")
