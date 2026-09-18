"""Bond-aware user emote catalogue and manual emote dispatch."""

from __future__ import annotations

from dataclasses import dataclass, replace

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.care import BondState, bond_xp_required
from mochi.menu_window import MenuWindow
from mochi.sprites import ANIMATIONS
from mochi.sound import SoundEvent
from mochi.state import MochiState, PresentationState


@dataclass(frozen=True, slots=True)
class EmoteDefinition:
    id: str
    label: str
    icon_name: str
    animation: str | None
    required_bond_level: int | None
    available: bool = True

    def is_unlocked(self, state: BondState) -> bool:
        return bool(
            self.available
            and self.required_bond_level is not None
            and state.level >= self.required_bond_level
        )


EMOTE_CATALOGUE = (
    EmoteDefinition(
        id="heart",
        label="Heart",
        icon_name="emblem-favorite-symbolic",
        animation="heart",
        required_bond_level=1,
    ),
    EmoteDefinition(
        id="bounce",
        label="Bounce",
        icon_name="go-up-symbolic",
        animation="bounce",
        required_bond_level=1,
    ),
    EmoteDefinition(
        id="squish",
        label="Squish",
        icon_name="object-select-symbolic",
        animation="squish",
        required_bond_level=1,
    ),
    EmoteDefinition(
        id="look",
        label="Look Around",
        icon_name="view-reveal-symbolic",
        animation="look",
        required_bond_level=3,
    ),
    EmoteDefinition(
        id="dance",
        label="Dance",
        icon_name="media-playback-start-symbolic",
        animation="dance",
        required_bond_level=5,
    ),
    EmoteDefinition(
        id="mystery-1",
        label="Mystery Emote I",
        icon_name="changes-prevent-symbolic",
        animation=None,
        required_bond_level=None,
        available=False,
    ),
    EmoteDefinition(
        id="mystery-2",
        label="Mystery Emote II",
        icon_name="changes-prevent-symbolic",
        animation=None,
        required_bond_level=None,
        available=False,
    ),
    EmoteDefinition(
        id="mystery-3",
        label="Mystery Emote III",
        icon_name="changes-prevent-symbolic",
        animation=None,
        required_bond_level=None,
        available=False,
    ),
)
EMOTES_BY_ID = {emote.id: emote for emote in EMOTE_CATALOGUE}


def bond_xp_until_level(state: BondState, target_level: int) -> int:
    """Return exact XP remaining before the target level begins."""
    if target_level <= state.level:
        return 0

    remaining = state.xp_required - state.xp
    for level in range(state.level + 1, target_level):
        remaining += bond_xp_required(level)
    return max(0, remaining)


def next_emote_unlock(state: BondState) -> EmoteDefinition | None:
    """Return the next real level-gated emote, ignoring future placeholders."""
    candidates = (
        emote
        for emote in EMOTE_CATALOGUE
        if emote.available
        and emote.required_bond_level is not None
        and emote.required_bond_level > state.level
    )
    return min(candidates, key=lambda emote: emote.required_bond_level, default=None)


def emote_status_text(emote: EmoteDefinition, state: BondState) -> str:
    if not emote.available:
        return "Coming soon"
    if emote.is_unlocked(state):
        return "Unlocked"
    return f"Bond Lv. {emote.required_bond_level}"


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
        MochiState.BLINKING,
        MochiState.BOUNCING,
        MochiState.SQUISHING,
        MochiState.EXCITED,
    )
)


class EmoteCatalogueMixin:
    """Expose Mochi's emotes as one bond-aware collection and trigger surface."""

    EMOTE_CATALOGUE_WIDTH = 316
    EMOTE_CATALOGUE_HEIGHT = 460

    def __init__(self, *args, **kwargs) -> None:
        self._emote_catalogue_window: MenuWindow | None = None
        self._emote_catalogue_next_label: Gtk.Label | None = None
        self._emote_catalogue_rows: dict[
            str, tuple[Gtk.Button, Gtk.Label, Gtk.Label]
        ] = {}
        self._pending_manual_emote: str | None = None
        self._emote_catalogue_content: Gtk.Widget | None = None
        self._emote_catalogue_animated_rows: tuple[Gtk.Widget, ...] = ()
        super().__init__(*args, **kwargs)

        if not self._preview_mode:
            self._emote_catalogue_window = self._build_emote_catalogue()
            self._emote_catalogue_window.connect(
                "closed",
                self._on_emote_catalogue_closed,
            )
            self._refresh_emote_catalogue()

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        button, _ = self._make_menu_button(
            "Emotes",
            "face-smile-symbolic",
            self._open_emote_catalogue_from_context_menu,
        )
        button.set_tooltip_text("Open Mochi's emote catalogue")
        self._register_context_menu_row(
            "emote-catalogue",
            button,
            before="sleep",
        )
        return menu

    def _build_emote_catalogue(self) -> MenuWindow:
        menu = MenuWindow(
            owner=self._window,
            anchor_widget=self,
            preferred_width=self.EMOTE_CATALOGUE_WIDTH,
            preferred_height=self.EMOTE_CATALOGUE_HEIGHT,
            follow_owner=True,
            dismiss_on_focus_loss=True,
            logger=self._logger,
        )
        menu.add_css_class("mochi-user-menu")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.add_css_class("mochi-menu-card")
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        root.set_size_request(284, -1)

        title = Gtk.Label(label="Emote Catalogue  ✦")
        title.set_xalign(0)
        title.add_css_class("mochi-menu-title")
        root.append(title)

        subtitle = Gtk.Label(label="grow your bond · collect little moods")
        subtitle.set_xalign(0)
        subtitle.add_css_class("mochi-menu-subtitle")
        root.append(subtitle)

        self._emote_catalogue_next_label = Gtk.Label()
        self._emote_catalogue_next_label.set_xalign(0)
        self._emote_catalogue_next_label.set_wrap(True)
        self._emote_catalogue_next_label.add_css_class("mochi-menu-value")
        root.append(self._emote_catalogue_next_label)

        root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        animated_rows: list[Gtk.Widget] = []
        for emote in EMOTE_CATALOGUE:
            button = Gtk.Button()
            button.add_css_class("mochi-menu-row")

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            icon = Gtk.Image.new_from_icon_name(emote.icon_name)
            icon.add_css_class("mochi-menu-icon")
            row.append(icon)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text_box.set_hexpand(True)
            name = Gtk.Label(label=emote.label)
            name.set_xalign(0)
            text_box.append(name)

            requirement = Gtk.Label()
            requirement.set_xalign(0)
            requirement.add_css_class("mochi-menu-subtitle")
            text_box.append(requirement)
            row.append(text_box)

            status = Gtk.Label()
            status.add_css_class("mochi-menu-value")
            row.append(status)

            button.set_child(row)
            button.connect(
                "clicked",
                lambda _button, emote_id=emote.id: self._choose_manual_emote(
                    emote_id
                ),
            )
            list_box.append(button)
            animated_rows.append(button)
            self._emote_catalogue_rows[emote.id] = (
                button,
                requirement,
                status,
            )

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(True)
        scroller.set_child(list_box)
        root.append(scroller)

        self._emote_catalogue_content = root
        self._emote_catalogue_animated_rows = tuple(animated_rows)
        menu.set_child(root)
        return menu

    def _refresh_emote_catalogue(self) -> None:
        state = getattr(self, "_bond_state", BondState())
        next_unlock = next_emote_unlock(state)

        if self._emote_catalogue_next_label is not None:
            if next_unlock is None:
                next_text = "All current emotes unlocked ✦"
            else:
                xp_left = bond_xp_until_level(
                    state,
                    next_unlock.required_bond_level or state.level,
                )
                next_text = (
                    f"Next: {next_unlock.label} · Bond Lv. "
                    f"{next_unlock.required_bond_level} · {xp_left:,} XP to go"
                )
            self._emote_catalogue_next_label.set_text(next_text)

        for emote in EMOTE_CATALOGUE:
            row = self._emote_catalogue_rows.get(emote.id)
            if row is None:
                continue
            button, requirement, status = row
            unlocked = emote.is_unlocked(state)
            button.set_sensitive(unlocked)
            if not emote.available:
                requirement.set_text("Future reward")
            elif unlocked:
                requirement.set_text("Ready to play")
            else:
                xp_left = bond_xp_until_level(
                    state,
                    emote.required_bond_level or state.level,
                )
                requirement.set_text(f"{xp_left:,} XP remaining")
            status.set_text(emote_status_text(emote, state))

    def _set_bond_state_for_ui(self, state: BondState) -> None:
        super()._set_bond_state_for_ui(state)
        self._refresh_emote_catalogue()

    def _open_emote_catalogue_from_context_menu(self, _button=None) -> None:
        self._close_context_menu_then(self._show_emote_catalogue)

    def _show_emote_catalogue(self) -> None:
        menu = self._emote_catalogue_window
        if menu is None or self._preview_mode:
            return
        if menu.get_visible():
            menu.popdown()
            return

        self._refresh_emote_catalogue()
        rectangle = Gdk.Rectangle()
        rectangle.x = max(1, self.get_width() // 2)
        rectangle.y = max(1, self.get_height() // 2)
        rectangle.width = 1
        rectangle.height = 1
        menu.set_pointing_to(rectangle)

        self._context_menu_open = True
        menu.popup()
        if self._emote_catalogue_content is not None:
            self._animate_menu_open(
                self._emote_catalogue_content,
                self._emote_catalogue_animated_rows,
            )
        self._logger.debug("Emote catalogue opened")

    def _show_context_menu(self, *args) -> None:
        if (
            self._emote_catalogue_window is not None
            and self._emote_catalogue_window.get_visible()
        ):
            self._emote_catalogue_window.popdown()
        super()._show_context_menu(*args)

    def _choose_manual_emote(self, emote_id: str) -> None:
        emote = EMOTES_BY_ID.get(emote_id)
        state = getattr(self, "_bond_state", BondState())
        if emote is None or not emote.is_unlocked(state):
            return
        self._pending_manual_emote = emote_id
        if self._emote_catalogue_window is not None:
            self._emote_catalogue_window.popdown()

    def _on_emote_catalogue_closed(self, _menu: MenuWindow) -> None:
        self._context_menu_open = False
        emote_id = self._pending_manual_emote
        self._pending_manual_emote = None
        if emote_id is not None:
            GLib.idle_add(self._dispatch_manual_emote, emote_id)

    def _dispatch_manual_emote(self, emote_id: str) -> bool:
        self._start_manual_emote(emote_id)
        return GLib.SOURCE_REMOVE

    def _start_manual_emote(self, emote_id: str) -> bool:
        emote = EMOTES_BY_ID.get(emote_id)
        state = getattr(self, "_bond_state", BondState())
        if emote is None or not emote.is_unlocked(state):
            return False
        if self.state.current in _CRITICAL_STATES:
            return False
        if (
            getattr(self.state, "presentation", PresentationState.NORMAL)
            is not PresentationState.NORMAL
        ):
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

        if emote.id == "heart":
            return self._start_heart_emote(ignore_cooldown=True)
        if emote.id == "look":
            play_look = getattr(self, "_play_idle_look", None)
            return bool(callable(play_look) and play_look())
        if emote.id == "dance":
            return self._play_manual_dance()

        reaction_state = {
            "bounce": MochiState.BOUNCING,
            "squish": MochiState.SQUISHING,
        }.get(emote.id)
        if reaction_state is None or emote.animation is None:
            return False
        if not self._transition_to(reaction_state):
            return False
        self._sound.play(SoundEvent.PET)
        self._play_animation(emote.animation)
        return True

    def _play_manual_dance(self) -> bool:
        if not self._transition_to(MochiState.DANCING):
            return False

        animation = replace(
            ANIMATIONS["dance"],
            looping=False,
            next_state="idle",
        )
        previous = self._current_animation
        self._current_animation = "dance"
        self._active_animation = animation
        self._pending_animation = "idle"
        self.player.play(animation)
        self._logger.debug("Animation: %s -> dance (manual one-shot)", previous)
        self.queue_draw()
        return True

    def shutdown_presence(self) -> None:
        if self._emote_catalogue_window is not None:
            self._emote_catalogue_window.popdown()
            self._emote_catalogue_window = None
        self._pending_manual_emote = None
        super().shutdown_presence()
