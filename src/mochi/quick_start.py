"""Friendly, user-facing Quick Start guide for Mochi."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402


@dataclass(frozen=True)
class QuickStartSection:
    """One compact section in Mochi's user-facing introduction."""

    title: str
    body: str
    bullets: tuple[str, ...] = ()


QUICK_START_SECTIONS = (
    QuickStartSection(
        "Meet Mochi",
        "Mochi quietly notices broad desktop activity and reacts in small ways "
        "while you work, play, and explore.",
    ),
    QuickStartSection(
        "Ambient Reactions",
        "AmbiSense uses broad, privacy-reduced activity signals rather than the "
        "content of what you type. Depending on what your desktop exposes, Mochi "
        "may respond with animations, behavior changes, or an occasional phrase.",
        (
            "Typing and sustained typing activity",
            "Coding and editor activity, including VS Code",
            "Terminal activity",
            "Music playback",
            "YouTube and supported video activity",
            "Idle/return periods, file browsing, and other supported desktop activity",
        ),
    ),
    QuickStartSection(
        "Play With Mochi",
        "You do not have to interact with Mochi, but he does notice when you do.",
        (
            "Hover over Mochi — he may answer with a little heart.",
            "Left-click — a tactile bounce or squish with a tiny chirp.",
            "Double-click — a heart emote.",
            "Drag — pick Mochi up and move him around the desktop.",
            "Right-click — open Mochi's user menu.",
        ),
    ),
    QuickStartSection(
        "Little Thoughts",
        "Mochi may occasionally show a short phrase connected to what is happening "
        "around the desktop. They are intentionally lightweight, paced out, and "
        "easy to ignore when you are busy.",
    ),
    QuickStartSection(
        "You’re in Control",
        "The right-click menu lets you sleep or wake Mochi, toggle Edge roam, use "
        "Stay put to stop autonomous wandering, and close Mochi. More granular "
        "AmbiSense controls for speech bubbles, ambient reactions, and quiet mode "
        "currently live in Mochi Lab, which is a developer/testing surface.",
    ),
    QuickStartSection(
        "Try This",
        "A few easy ways to see Mochi react:",
        (
            "Open VS Code and type for a bit.",
            "Focus a terminal and work there for a moment.",
            "Play some music.",
            "Pick Mochi up and move him around.",
            "Leave him alone for a while and see what he decides to do.",
        ),
    ),
)

QUICK_START_FOOTER = "That’s enough reading. Go bother Mochi. 🌱"

QUICK_START_CSS = """
window.mochi-quick-start {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}

.mochi-quick-start-kicker {
    color: #79c98b;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
}

.mochi-quick-start-title {
    font-size: 22px;
    font-weight: 800;
}

.mochi-quick-start-subtitle,
.mochi-quick-start-body,
.mochi-quick-start-bullet {
    color: alpha(@theme_fg_color, 0.72);
}

.mochi-quick-start-subtitle {
    font-size: 12px;
}

.mochi-quick-start-card {
    background-color: alpha(@theme_fg_color, 0.045);
    border: 1px solid alpha(@theme_fg_color, 0.09);
    border-radius: 14px;
    padding: 13px 14px;
}

.mochi-quick-start-section-title {
    font-size: 13px;
    font-weight: 700;
}

.mochi-quick-start-body,
.mochi-quick-start-bullet {
    font-size: 12px;
}

.mochi-quick-start-dot {
    color: #79c98b;
    font-weight: 800;
}

.mochi-quick-start-footer {
    font-size: 12px;
    font-weight: 600;
}

button.mochi-quick-start-close {
    min-height: 34px;
    padding: 4px 16px;
    border-radius: 10px;
    background-image: none;
    background-color: #79c98b;
    color: #16351f;
    font-weight: 700;
}

button.mochi-quick-start-close:hover {
    background-color: #8bd49b;
}
"""


class QuickStartWindow:
    """Small reusable, non-modal introduction window."""

    DEFAULT_WIDTH = 520
    DEFAULT_HEIGHT = 620

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)

        self.window = Gtk.Window()
        self.window.set_title("Getting to know Mochi 🌱")
        self.window.set_transient_for(owner)
        self.window.set_destroy_with_parent(True)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_resizable(True)
        self.window.set_default_size(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.window.set_size_request(420, 420)
        self.window.add_css_class("mochi-quick-start")

        self._css = Gtk.CssProvider()
        self._css.load_from_string(QUICK_START_CSS)
        Gtk.StyleContext.add_provider_for_display(
            owner.get_display(),
            self._css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(keys)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_margin_top(20)
        root.set_margin_bottom(16)
        root.set_margin_start(20)
        root.set_margin_end(20)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        kicker = Gtk.Label(label="QUICK START")
        kicker.set_xalign(0)
        kicker.add_css_class("mochi-quick-start-kicker")
        hero.append(kicker)

        title = Gtk.Label(label="Getting to know Mochi")
        title.set_xalign(0)
        title.set_wrap(True)
        title.add_css_class("mochi-quick-start-title")
        hero.append(title)

        subtitle = Gtk.Label(
            label="A tiny guide to the tiny creature living on your desktop."
        )
        subtitle.set_xalign(0)
        subtitle.set_wrap(True)
        subtitle.add_css_class("mochi-quick-start-subtitle")
        hero.append(subtitle)
        root.append(hero)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_margin_top(16)
        scroller.set_margin_bottom(14)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_end(6)
        for section in QUICK_START_SECTIONS:
            content.append(self._build_section(section))
        scroller.set_child(content)
        root.append(scroller)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer_text = Gtk.Label(label=QUICK_START_FOOTER)
        footer_text.set_xalign(0)
        footer_text.set_wrap(True)
        footer_text.set_hexpand(True)
        footer_text.add_css_class("mochi-quick-start-footer")
        footer.append(footer_text)

        close_button = Gtk.Button(label="Close")
        close_button.set_valign(Gtk.Align.CENTER)
        close_button.add_css_class("mochi-quick-start-close")
        close_button.connect("clicked", self._on_close_clicked)
        footer.append(close_button)
        root.append(footer)

        self.window.set_child(root)

    def present(self) -> None:
        """Present the same reusable window every time the menu action is used."""
        self.window.present()
        self._logger.debug("Quick Start opened")

    def hide(self) -> None:
        self.window.hide()

    def destroy(self) -> None:
        self.window.destroy()

    def _build_section(self, section: QuickStartSection) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("mochi-quick-start-card")

        title = Gtk.Label(label=section.title)
        title.set_xalign(0)
        title.add_css_class("mochi-quick-start-section-title")
        card.append(title)

        body = Gtk.Label(label=section.body)
        body.set_xalign(0)
        body.set_wrap(True)
        body.set_max_width_chars(62)
        body.add_css_class("mochi-quick-start-body")
        card.append(body)

        for bullet_text in section.bullets:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_valign(Gtk.Align.START)

            dot = Gtk.Label(label="•")
            dot.set_valign(Gtk.Align.START)
            dot.add_css_class("mochi-quick-start-dot")
            row.append(dot)

            bullet = Gtk.Label(label=bullet_text)
            bullet.set_xalign(0)
            bullet.set_wrap(True)
            bullet.set_hexpand(True)
            bullet.set_max_width_chars(58)
            bullet.add_css_class("mochi-quick-start-bullet")
            row.append(bullet)
            card.append(row)

        return card

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.hide()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False


class QuickStartMixin:
    """Add Quick Start to the proven right-click menu without touching Buddy state."""

    def __init__(self, *args, **kwargs) -> None:
        self._quick_start_window: QuickStartWindow | None = None
        super().__init__(*args, **kwargs)

    def _build_context_menu(self):
        popover = super()._build_context_menu()

        help_button = self._make_quick_start_menu_button()
        self._register_context_menu_row(
            "quick-start",
            help_button,
            before="close",
        )
        return popover

    def _make_quick_start_menu_button(self) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        button.set_tooltip_text("A quick introduction to Mochi")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        badge = Gtk.Label(label="?")
        badge.set_width_chars(2)
        row.append(badge)

        text = Gtk.Label(label="What can Mochi do?")
        text.set_xalign(0)
        text.set_hexpand(True)
        row.append(text)

        button.set_child(row)
        button.connect("clicked", self._show_quick_start_from_context_menu)
        return button

    def _show_quick_start_from_context_menu(self, _button: Gtk.Button) -> None:
        self._close_context_menu_then(self._show_quick_start)

    def _show_quick_start(self) -> None:
        if self._quick_start_window is None:
            self._quick_start_window = QuickStartWindow(
                owner=self._window,
                logger=self._logger,
            )
        self._quick_start_window.present()

    def shutdown_presence(self) -> None:
        if self._quick_start_window is not None:
            self._quick_start_window.destroy()
            self._quick_start_window = None
        super().shutdown_presence()
