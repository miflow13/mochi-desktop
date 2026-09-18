"""Large bond-aware emote collection window and manual emote dispatch."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.care import BondState, bond_xp_required
from mochi.emote_shortcut import EmoteCatalogueShortcutMonitor
from mochi.sprites import ANIMATIONS, SpriteAtlas
from mochi.sound import SoundEvent
from mochi.state import MochiState, PresentationState


@dataclass(frozen=True, slots=True)
class EmoteDefinition:
    id: str
    label: str
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
    EmoteDefinition("heart", "Heart", "heart", 1),
    EmoteDefinition("bounce", "Bounce", "bounce", 1),
    EmoteDefinition("squish", "Squish", "squish", 1),
    EmoteDefinition("look", "Look Around", "look", 3),
    EmoteDefinition("dance", "Dance", "dance", 5),
    EmoteDefinition("mystery-1", "Mystery Emote I", None, None, False),
    EmoteDefinition("mystery-2", "Mystery Emote II", None, None, False),
    EmoteDefinition("mystery-3", "Mystery Emote III", None, None, False),
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
        return "COMING SOON"
    if emote.is_unlocked(state):
        return "UNLOCKED"
    return f"BOND LV. {emote.required_bond_level}"


CATALOGUE_CSS = """
window.mochi-emote-catalogue {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}
.mochi-emote-kicker {
    color: #79c98b;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.10em;
}
.mochi-emote-title {
    font-size: 26px;
    font-weight: 850;
}
.mochi-emote-subtitle,
.mochi-emote-progress-copy {
    color: alpha(@theme_fg_color, 0.68);
}
.mochi-emote-progress-copy {
    font-size: 12px;
}
.mochi-emote-progress {
    min-height: 7px;
}
button.mochi-emote-card {
    min-width: 232px;
    min-height: 258px;
    padding: 0;
    border-radius: 18px;
    background-image: none;
    background-color: alpha(@theme_fg_color, 0.045);
    border: 1px solid alpha(@theme_fg_color, 0.10);
}
button.mochi-emote-card:hover {
    background-color: alpha(#79c98b, 0.10);
    border-color: alpha(#79c98b, 0.42);
}
button.mochi-emote-card:disabled {
    opacity: 1.0;
    background-color: alpha(@theme_fg_color, 0.025);
    border-color: alpha(@theme_fg_color, 0.07);
}
.mochi-emote-card-name {
    font-size: 15px;
    font-weight: 800;
}
.mochi-emote-card-status {
    color: #79c98b;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.06em;
}
.mochi-emote-card-locked {
    color: alpha(@theme_fg_color, 0.55);
}
.mochi-emote-card-detail {
    color: alpha(@theme_fg_color, 0.62);
    font-size: 11px;
}
.mochi-emote-preview {
    background-color: alpha(@theme_fg_color, 0.028);
    border-radius: 14px;
}
.mochi-emote-footer {
    color: alpha(@theme_fg_color, 0.48);
    font-size: 11px;
}
"""


class EmotePreview(Gtk.DrawingArea):
    """Static catalogue art using authored animation frames and silhouette masks."""

    SIZE = 166

    def __init__(
        self,
        *,
        atlas: SpriteAtlas,
        emote: EmoteDefinition,
    ) -> None:
        super().__init__()
        self._atlas = atlas
        self._emote = emote
        self._locked = True
        self.set_content_width(self.SIZE)
        self.set_content_height(self.SIZE)
        self.set_hexpand(True)
        self.add_css_class("mochi-emote-preview")
        self.set_draw_func(self._draw)

    def set_locked(self, locked: bool) -> None:
        if locked == self._locked:
            return
        self._locked = locked
        self.queue_draw()

    def _representative_frame(self):
        animation_name = self._emote.animation or "idle"
        animation = ANIMATIONS[animation_name]
        frames = animation.frames
        return frames[min(len(frames) - 1, len(frames) // 2)]

    def _draw(
        self,
        _area: Gtk.DrawingArea,
        context: cairo.Context,
        width: int,
        height: int,
    ) -> None:
        frame = self._representative_frame()
        if not self._locked:
            self._atlas.draw(context, frame, width, height)
            return

        sprite = self._atlas.frames[frame.sprite]
        source_width, source_height = self._atlas.CANVAS_SIZE
        scale = min(width / source_width, height / source_height)
        offset_scale = min(width, height) / self._atlas.OFFSET_COORDINATE_SIZE
        x = round(
            (width - source_width * scale) / 2
            + frame.horizontal_offset * offset_scale
        )
        y = round(
            (height - source_height * scale) / 2
            + frame.vertical_offset * offset_scale
        )

        context.save()
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_rgba(0.10, 0.14, 0.11, 0.78)
        context.mask_surface(sprite, 0, 0)
        context.restore()


class EmoteCard:
    """One large visual catalogue card."""

    def __init__(
        self,
        *,
        atlas: SpriteAtlas,
        emote: EmoteDefinition,
        on_activate,
    ) -> None:
        self.emote = emote
        self.button = Gtk.Button()
        self.button.add_css_class("mochi-emote-card")
        self.button.connect("clicked", lambda _button: on_activate(emote.id))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        self.preview = EmotePreview(atlas=atlas, emote=emote)
        content.append(self.preview)

        self.name = Gtk.Label(label=emote.label)
        self.name.set_xalign(0)
        self.name.add_css_class("mochi-emote-card-name")
        content.append(self.name)

        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.add_css_class("mochi-emote-card-status")
        content.append(self.status)

        self.detail = Gtk.Label()
        self.detail.set_xalign(0)
        self.detail.set_wrap(True)
        self.detail.add_css_class("mochi-emote-card-detail")
        content.append(self.detail)

        self.button.set_child(content)

    def refresh(self, state: BondState) -> None:
        unlocked = self.emote.is_unlocked(state)
        self.button.set_sensitive(unlocked)
        self.preview.set_locked(not unlocked)
        self.status.set_text(emote_status_text(self.emote, state))

        if not self.emote.available:
            detail = "A future little mood. Not unlockable yet."
            self.status.add_css_class("mochi-emote-card-locked")
        elif unlocked:
            detail = "Click to ask Mochi to do this emote."
            self.status.remove_css_class("mochi-emote-card-locked")
        else:
            remaining = bond_xp_until_level(
                state,
                self.emote.required_bond_level or state.level,
            )
            detail = f"{remaining:,} bond XP remaining"
            self.status.add_css_class("mochi-emote-card-locked")
        self.detail.set_text(detail)


class EmoteCatalogueWindow:
    """Large reusable collection window opened by Mochi's global shortcut."""

    DEFAULT_WIDTH = 900
    DEFAULT_HEIGHT = 680

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        atlas: SpriteAtlas,
        on_emote_requested,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._cards: dict[str, EmoteCard] = {}
        self._state = BondState()
        self._on_emote_requested = on_emote_requested

        self.window = Gtk.Window()
        self.window.set_title("Mochi Emote Catalogue")
        self.window.set_transient_for(owner)
        self.window.set_destroy_with_parent(True)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_resizable(True)
        self.window.set_default_size(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.window.set_size_request(680, 500)
        self.window.add_css_class("mochi-emote-catalogue")

        css = Gtk.CssProvider()
        css.load_from_string(CATALOGUE_CSS)
        self._css = css
        Gtk.StyleContext.add_provider_for_display(
            owner.get_display(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(keys)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_margin_top(24)
        root.set_margin_bottom(18)
        root.set_margin_start(24)
        root.set_margin_end(24)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        kicker = Gtk.Label(label="MOCHI COLLECTION")
        kicker.set_xalign(0)
        kicker.add_css_class("mochi-emote-kicker")
        hero.append(kicker)

        title = Gtk.Label(label="Emote Catalogue")
        title.set_xalign(0)
        title.add_css_class("mochi-emote-title")
        hero.append(title)

        subtitle = Gtk.Label(
            label="Grow your bond with Mochi to reveal more little moods."
        )
        subtitle.set_xalign(0)
        subtitle.add_css_class("mochi-emote-subtitle")
        hero.append(subtitle)

        self._next_label = Gtk.Label()
        self._next_label.set_xalign(0)
        self._next_label.set_margin_top(8)
        self._next_label.add_css_class("mochi-emote-progress-copy")
        hero.append(self._next_label)

        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(False)
        self._progress.add_css_class("mochi-emote-progress")
        hero.append(self._progress)
        root.append(hero)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_margin_top(18)

        grid = Gtk.Grid()
        grid.set_column_spacing(14)
        grid.set_row_spacing(14)
        grid.set_column_homogeneous(True)
        for index, emote in enumerate(EMOTE_CATALOGUE):
            card = EmoteCard(
                atlas=atlas,
                emote=emote,
                on_activate=self._on_card_activate,
            )
            self._cards[emote.id] = card
            grid.attach(card.button, index % 3, index // 3, 1, 1)
        scroller.set_child(grid)
        root.append(scroller)

        footer = Gtk.Label(label="Ctrl + Alt + E · Esc to close")
        footer.set_xalign(1)
        footer.set_margin_top(10)
        footer.add_css_class("mochi-emote-footer")
        root.append(footer)

        self.window.set_child(root)
        self.refresh(self._state)

    def refresh(self, state: BondState) -> None:
        self._state = BondState(level=state.level, xp=state.xp)
        next_unlock = next_emote_unlock(self._state)

        if next_unlock is None:
            self._next_label.set_text(
                f"Bond Lv. {self._state.level} · all current emotes unlocked ✦"
            )
            self._progress.set_fraction(1.0)
        else:
            target = next_unlock.required_bond_level or self._state.level
            remaining = bond_xp_until_level(self._state, target)
            total_from_level_start = bond_xp_until_level(
                BondState(level=self._state.level, xp=0),
                target,
            )
            completed = max(0, total_from_level_start - remaining)
            fraction = (
                completed / total_from_level_start
                if total_from_level_start > 0
                else 1.0
            )
            self._progress.set_fraction(min(1.0, max(0.0, fraction)))
            self._next_label.set_text(
                f"Bond Lv. {self._state.level} · Next: {next_unlock.label} "
                f"at Lv. {target} · {remaining:,} XP to go"
            )

        for card in self._cards.values():
            card.refresh(self._state)

    def present(self) -> None:
        self.window.present()
        self._logger.debug("Emote catalogue opened")

    def hide(self) -> None:
        self.window.hide()

    def destroy(self) -> None:
        self.window.destroy()

    def _on_card_activate(self, emote_id: str) -> None:
        emote = EMOTES_BY_ID.get(emote_id)
        if emote is None or not emote.is_unlocked(self._state):
            return
        self.hide()
        GLib.idle_add(self._dispatch_card, emote_id)

    def _dispatch_card(self, emote_id: str) -> bool:
        self._on_emote_requested(emote_id)
        return GLib.SOURCE_REMOVE

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
    """Own the catalogue window, shortcut bridge, and manual emote dispatch."""

    def __init__(self, *args, **kwargs) -> None:
        self._emote_catalogue_window: EmoteCatalogueWindow | None = None
        self._emote_shortcut_monitor: EmoteCatalogueShortcutMonitor | None = None
        super().__init__(*args, **kwargs)

        if not self._preview_mode:
            self._emote_catalogue_window = EmoteCatalogueWindow(
                owner=self._window,
                atlas=self.atlas,
                on_emote_requested=self._start_manual_emote,
                logger=self._logger,
            )
            self._emote_catalogue_window.refresh(self._bond_state)
            self._emote_shortcut_monitor = EmoteCatalogueShortcutMonitor(
                on_requested=self._show_emote_catalogue,
                logger=self._logger,
            )
            self._emote_shortcut_monitor.start()

    def _refresh_emote_catalogue(self) -> None:
        if self._emote_catalogue_window is not None:
            self._emote_catalogue_window.refresh(self._bond_state)

    def _set_bond_state_for_ui(self, state: BondState) -> None:
        super()._set_bond_state_for_ui(state)
        self._refresh_emote_catalogue()

    def _show_emote_catalogue(self) -> None:
        window = self._emote_catalogue_window
        if window is None or self._preview_mode:
            return
        window.refresh(self._bond_state)
        window.present()

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
        if self._emote_shortcut_monitor is not None:
            self._emote_shortcut_monitor.stop()
            self._emote_shortcut_monitor = None
        if self._emote_catalogue_window is not None:
            self._emote_catalogue_window.destroy()
            self._emote_catalogue_window = None
        super().shutdown_presence()
