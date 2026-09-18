"""User-facing manual emote picker for Mochi."""

from __future__ import annotations

from dataclasses import replace

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.menu_window import MenuWindow
from mochi.sprites import ANIMATIONS
from mochi.sound import SoundEvent
from mochi.state import MochiState


EMOTE_CHOICES = (
    ("Heart", "emblem-favorite-symbolic", "heart"),
    ("Bounce", "go-up-symbolic", "bounce"),
    ("Squish", "object-select-symbolic", "squish"),
    ("Look around", "view-reveal-symbolic", "look"),
    ("Dance", "media-playback-start-symbolic", "dance"),
)

_CRITICAL_STATES = frozenset(
    (
        MochiState.SLEEPING,
        MochiState.WAKING,
        MochiState.EATING,
        MochiState.PICKUP,
        MochiState.DRAGGED,
        MochiState.DROPPING,
        MochiState.FEDORA,
    )
)
_MANUAL_REACTION_STATES = frozenset(
    (
        MochiState.BOUNCING,
        MochiState.SQUISHING,
        MochiState.EXCITED,
    )
)


class EmotesMenuMixin:
    """Add a small manual-emote picker without bypassing Mochi's state ownership."""

    EMOTES_MENU_WIDTH = 244
    EMOTES_MENU_HEIGHT = 330

    def __init__(self, *args, **kwargs) -> None:
        self._emotes_menu: MenuWindow | None = None
        self._pending_manual_emote: str | None = None
        self._emotes_menu_content: Gtk.Box | None = None
        self._emotes_menu_animated_rows: tuple[Gtk.Widget, ...] = ()
        super().__init__(*args, **kwargs)

        if not self._preview_mode:
            self._emotes_menu = self._build_emotes_menu()
            self._emotes_menu.connect("closed", self._on_emotes_menu_closed)

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        button, _ = self._make_menu_button(
            "Emotes",
            "face-smile-symbolic",
            self._open_emotes_from_context_menu,
        )
        button.set_tooltip_text("Choose something playful for Mochi to do")
        self._register_context_menu_row(
            "emotes",
            button,
            before="sleep",
        )
        return menu

    def _build_emotes_menu(self) -> MenuWindow:
        menu = MenuWindow(
            owner=self._window,
            anchor_widget=self,
            preferred_width=self.EMOTES_MENU_WIDTH,
            preferred_height=self.EMOTES_MENU_HEIGHT,
            follow_owner=True,
            dismiss_on_focus_loss=True,
            logger=self._logger,
        )
        menu.add_css_class("mochi-user-menu")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("mochi-menu-card")
        card.set_margin_top(12)
        card.set_margin_bottom(12)
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_size_request(220, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(label="Emotes  ✦")
        title.set_xalign(0)
        title.add_css_class("mochi-menu-title")
        header.append(title)

        subtitle = Gtk.Label(label="pick a little mood")
        subtitle.set_xalign(0)
        subtitle.add_css_class("mochi-menu-subtitle")
        header.append(subtitle)
        card.append(header)
        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        animated_rows: list[Gtk.Widget] = []
        for label, icon_name, emote_name in EMOTE_CHOICES:
            button, _ = self._make_menu_button(
                label,
                icon_name,
                lambda _button, name=emote_name: self._choose_manual_emote(name),
            )
            card.append(button)
            animated_rows.append(button)

        menu.set_child(card)
        self._emotes_menu_content = card
        self._emotes_menu_animated_rows = tuple(animated_rows)
        return menu

    def _open_emotes_from_context_menu(self, _button=None) -> None:
        self._close_context_menu_then(self._show_emotes_menu)

    def _show_emotes_menu(self) -> None:
        menu = self._emotes_menu
        if menu is None or self._preview_mode:
            return
        if menu.get_visible():
            menu.popdown()
            return

        rectangle = Gdk.Rectangle()
        rectangle.x = max(1, self.get_width() // 2)
        rectangle.y = max(1, self.get_height() // 2)
        rectangle.width = 1
        rectangle.height = 1
        menu.set_pointing_to(rectangle)

        self._context_menu_open = True
        menu.popup()
        if self._emotes_menu_content is not None:
            self._animate_menu_open(
                self._emotes_menu_content,
                self._emotes_menu_animated_rows,
            )
        self._logger.debug("Emotes menu opened")

    def _choose_manual_emote(self, emote_name: str) -> None:
        if emote_name not in {choice[2] for choice in EMOTE_CHOICES}:
            return
        self._pending_manual_emote = emote_name
        if self._emotes_menu is not None:
            self._emotes_menu.popdown()

    def _on_emotes_menu_closed(self, _menu: MenuWindow) -> None:
        self._context_menu_open = False
        emote_name = self._pending_manual_emote
        self._pending_manual_emote = None
        if emote_name is not None:
            GLib.idle_add(self._dispatch_manual_emote, emote_name)

    def _dispatch_manual_emote(self, emote_name: str) -> bool:
        self._start_manual_emote(emote_name)
        return GLib.SOURCE_REMOVE

    def _start_manual_emote(self, emote_name: str) -> bool:
        """Run one explicit emote while respecting critical Mochi states."""
        if emote_name not in {choice[2] for choice in EMOTE_CHOICES}:
            return False
        if self.state.current in _CRITICAL_STATES:
            self._logger.debug(
                "Manual emote %s rejected during %s",
                emote_name,
                self.state.current.name,
            )
            return False

        self._mark_interaction()
        self._cancel_hover_heart()

        cancel_look = getattr(self, "_cancel_idle_look", None)
        if callable(cancel_look):
            cancel_look()

        if self.state.current is MochiState.WALKING:
            self._cancel_walk()
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        elif self.state.current in _MANUAL_REACTION_STATES:
            self._transition_to(MochiState.IDLE)
            self._play_animation("idle")
        elif self.state.current is not MochiState.IDLE:
            self._cancel_active_emote()

        if self.state.current is not MochiState.IDLE:
            return False

        if emote_name == "heart":
            return self._start_heart_emote(ignore_cooldown=True)
        if emote_name == "look":
            play_look = getattr(self, "_play_idle_look", None)
            return bool(callable(play_look) and play_look())
        if emote_name == "dance":
            return self._play_manual_dance()

        state = {
            "bounce": MochiState.BOUNCING,
            "squish": MochiState.SQUISHING,
        }[emote_name]
        if not self._transition_to(state):
            return False
        self._sound.play(SoundEvent.PET)
        self._play_animation(emote_name)
        return True

    def _play_manual_dance(self) -> bool:
        if not self._transition_to(MochiState.DANCING):
            return False

        # The contextual music dance is intentionally looping. A menu-selected
        # dance is a one-shot emote so it finishes cleanly without requiring a
        # second user action.
        animation = replace(ANIMATIONS["dance"], looping=False, next_state="idle")
        previous = self._current_animation
        self._current_animation = "dance"
        self._active_animation = animation
        self._pending_animation = "idle"
        self.player.play(animation)
        self._logger.debug("Animation: %s -> dance (manual one-shot)", previous)
        self.queue_draw()
        return True

    def shutdown_presence(self) -> None:
        if self._emotes_menu is not None:
            self._emotes_menu.popdown()
            self._emotes_menu = None
        self._pending_manual_emote = None
        super().shutdown_presence()
