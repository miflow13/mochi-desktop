"""Large bond-aware emote collection window and manual emote dispatch."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
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


@lru_cache(maxsize=64)
def _bond_xp_to_level_start(level: int) -> int:
    """Cumulative XP needed to reach the beginning of a bond level."""
    normalized = max(1, int(level))
    return sum(bond_xp_required(current) for current in range(1, normalized))


def bond_xp_until_level(state: BondState, target_level: int) -> int:
    """Return exact XP remaining before the target level begins."""
    if target_level <= state.level:
        return 0

    current_total = _bond_xp_to_level_start(state.level) + state.xp
    target_total = _bond_xp_to_level_start(target_level)
    return max(0, target_total - current_total)


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
.mochi-emote-header {
    min-height: 42px;
    background-color: @theme_bg_color;
    border-bottom: 1px solid alpha(@theme_fg_color, 0.08);
    box-shadow: none;
}
.mochi-emote-header-title {
    font-weight: 700;
}
button.mochi-emote-close {
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    border-radius: 999px;
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
    min-height: 250px;
    padding: 0;
    border-radius: 12px;
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
.mochi-emote-footer {
    color: alpha(@theme_fg_color, 0.48);
    font-size: 11px;
}
gridview.mochi-emote-grid {
    border-spacing: 14px;
}
"""


class EmotePreview(Gtk.Picture):
    """GPU-friendly static preview backed by pre-rendered immutable textures."""

    SIZE = 166

    def __init__(
        self,
        *,
        atlas: SpriteAtlas,
        texture_cache: dict[tuple[object, ...], Gdk.Texture],
    ) -> None:
        super().__init__()
        self._atlas = atlas
        self._texture_cache = texture_cache
        self._unlocked_texture: Gdk.Texture | None = None
        self._locked_texture: Gdk.Texture | None = None
        self._locked = True
        self.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.set_can_shrink(False)
        self.set_size_request(self.SIZE, self.SIZE)
        self.set_halign(Gtk.Align.CENTER)
        self.add_css_class("mochi-emote-preview")

    def set_emote(self, emote: EmoteDefinition) -> None:
        animation = ANIMATIONS[emote.animation or "idle"]
        frames = animation.frames
        frame = frames[min(len(frames) - 1, len(frames) // 2)]
        key = (
            frame.sprite,
            frame.horizontal_offset,
            frame.vertical_offset,
        )
        self._unlocked_texture = self._cached_texture(
            self._atlas,
            frame,
            locked=False,
            key=(*key, False),
            cache=self._texture_cache,
        )
        self._locked_texture = self._cached_texture(
            self._atlas,
            frame,
            locked=True,
            key=(*key, True),
            cache=self._texture_cache,
        )
        self.set_paintable(self._locked_texture if self._locked else self._unlocked_texture)

    def set_locked(self, locked: bool) -> None:
        if locked == self._locked:
            return
        self._locked = locked
        self.set_paintable(
            self._locked_texture if locked else self._unlocked_texture
        )

    @classmethod
    def _cached_texture(
        cls,
        atlas: SpriteAtlas,
        frame,
        *,
        locked: bool,
        key: tuple[object, ...],
        cache: dict[tuple[object, ...], Gdk.Texture],
    ) -> Gdk.Texture:
        cached = cache.get(key)
        if cached is not None:
            return cached

        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            cls.SIZE,
            cls.SIZE,
        )
        context = cairo.Context(surface)
        if locked:
            sprite = atlas.frames[frame.sprite]
            source_width, source_height = atlas.CANVAS_SIZE
            scale = min(cls.SIZE / source_width, cls.SIZE / source_height)
            offset_scale = cls.SIZE / atlas.OFFSET_COORDINATE_SIZE
            x = round(
                (cls.SIZE - source_width * scale) / 2
                + frame.horizontal_offset * offset_scale
            )
            y = round(
                (cls.SIZE - source_height * scale) / 2
                + frame.vertical_offset * offset_scale
            )
            context.translate(x, y)
            context.scale(scale, scale)
            context.set_source_rgba(0.10, 0.14, 0.11, 0.78)
            context.mask_surface(sprite, 0, 0)
        else:
            atlas.draw(context, frame, cls.SIZE, cls.SIZE)

        surface.flush()
        pixel_bytes = GLib.Bytes.new(bytes(surface.get_data()))
        memory_format = (
            Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED
            if sys.byteorder == "little"
            else Gdk.MemoryFormat.A8R8G8B8_PREMULTIPLIED
        )
        texture = Gdk.MemoryTexture.new(
            cls.SIZE,
            cls.SIZE,
            memory_format,
            pixel_bytes,
            surface.get_stride(),
        )
        cache[key] = texture
        return texture


class EmoteCard:
    """One large visual catalogue card."""

    def __init__(
        self,
        *,
        atlas: SpriteAtlas,
        on_activate,
        texture_cache: dict[tuple[object, ...], Gdk.Texture],
    ) -> None:
        self.emote: EmoteDefinition | None = None
        self._on_activate = on_activate
        self._last_unlocked: bool | None = None
        self._last_status: str | None = None
        self._last_detail: str | None = None
        self.button = Gtk.Button()
        self.button.add_css_class("mochi-emote-card")
        self.button.connect("clicked", self._on_clicked)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        self.preview = EmotePreview(
            atlas=atlas,
            texture_cache=texture_cache,
        )
        content.append(self.preview)

        self.name = Gtk.Label()
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

    def bind(self, emote: EmoteDefinition) -> None:
        if self.emote is emote:
            return
        self.emote = emote
        self._last_unlocked = None
        self._last_status = None
        self._last_detail = None
        self.name.set_text(emote.label)
        self.preview.set_emote(emote)

    def _on_clicked(self, _button: Gtk.Button) -> None:
        if self.emote is not None:
            self._on_activate(self.emote.id)

    def refresh(self, state: BondState) -> None:
        if self.emote is None:
            return
        unlocked = self.emote.is_unlocked(state)
        if unlocked != self._last_unlocked:
            self.button.set_sensitive(unlocked)
            self.preview.set_locked(not unlocked)
            if unlocked:
                self.status.remove_css_class("mochi-emote-card-locked")
            else:
                self.status.add_css_class("mochi-emote-card-locked")
            self._last_unlocked = unlocked

        status = emote_status_text(self.emote, state)
        if status != self._last_status:
            self.status.set_text(status)
            self._last_status = status

        if not self.emote.available:
            detail = "A future little mood. Not unlockable yet."
        elif unlocked:
            detail = "Click to ask Mochi to do this emote."
        else:
            remaining = bond_xp_until_level(
                state,
                self.emote.required_bond_level or state.level,
            )
            detail = f"{remaining:,} bond XP remaining"

        if detail != self._last_detail:
            self.detail.set_text(detail)
            self._last_detail = detail


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
        self._bound_cards: set[EmoteCard] = set()
        self._cards_by_button: dict[Gtk.Button, EmoteCard] = {}
        self._atlas = atlas
        self._preview_texture_cache: dict[tuple[object, ...], Gdk.Texture] = {}
        self._state: BondState | None = None
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

        # Keep this a native header-bar decoration. GTK reserves the remaining
        # header-bar area as the compositor-supported drag region on Wayland.
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        header.set_decoration_layout(":close")
        header.add_css_class("mochi-emote-header")
        header_title = Gtk.Label(label="Mochi Emotes")
        header_title.add_css_class("mochi-emote-header-title")
        header.set_title_widget(header_title)
        self.window.set_titlebar(header)

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

        self._emote_model = Gtk.StringList.new([emote.id for emote in EMOTE_CATALOGUE])
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_card)
        factory.connect("bind", self._bind_card)
        factory.connect("unbind", self._unbind_card)
        grid = Gtk.GridView.new(Gtk.NoSelection.new(self._emote_model), factory)
        grid.set_min_columns(1)
        grid.set_max_columns(3)
        grid.set_enable_rubberband(False)
        grid.add_css_class("mochi-emote-grid")
        scroller.set_child(grid)
        root.append(scroller)

        footer = Gtk.Label(label="Ctrl + Alt + E · Esc to close")
        footer.set_xalign(1)
        footer.set_margin_top(10)
        footer.add_css_class("mochi-emote-footer")
        root.append(footer)

        self.window.set_child(root)

    @property
    def visible(self) -> bool:
        return self.window.get_visible()

    def refresh(self, state: BondState, *, force: bool = False) -> bool:
        next_state = BondState(level=state.level, xp=state.xp)
        if not force and next_state == self._state:
            return False

        self._state = next_state
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

        for card in self._bound_cards:
            card.refresh(self._state)
        return True

    def _setup_card(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        card = EmoteCard(
            atlas=self._atlas,
            on_activate=self._on_card_activate,
            texture_cache=self._preview_texture_cache,
        )
        list_item.set_child(card.button)
        self._cards_by_button[card.button] = card

    def _bind_card(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        emote_id = list_item.get_item().get_string()
        card = self._cards_by_button[list_item.get_child()]
        card.bind(EMOTES_BY_ID[emote_id])
        self._bound_cards.add(card)
        if self._state is not None:
            card.refresh(self._state)

    def _unbind_card(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        self._bound_cards.discard(self._cards_by_button[list_item.get_child()])

    def present(self) -> None:
        self.window.present()
        self._logger.debug("Emote catalogue opened")

    def hide(self) -> None:
        self.window.hide()

    def destroy(self) -> None:
        self.window.destroy()

    def _on_card_activate(self, emote_id: str) -> None:
        emote = EMOTES_BY_ID.get(emote_id)
        if self._state is None or emote is None or not emote.is_unlocked(self._state):
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
            # Keep startup cheap: only the tiny shortcut subscriber exists until
            # the user actually asks to open the collection window.
            self._emote_shortcut_monitor = EmoteCatalogueShortcutMonitor(
                on_requested=self._show_emote_catalogue,
                logger=self._logger,
            )
            self._emote_shortcut_monitor.start()

    def _ensure_emote_catalogue_window(self) -> EmoteCatalogueWindow:
        window = self._emote_catalogue_window
        if window is None:
            window = EmoteCatalogueWindow(
                owner=self._window,
                atlas=self.atlas,
                on_emote_requested=self._start_manual_emote,
                logger=self._logger,
            )
            self._emote_catalogue_window = window
        return window

    def _refresh_emote_catalogue(self) -> None:
        window = self._emote_catalogue_window
        if window is not None and window.visible:
            window.refresh(self._bond_state)

    def _set_bond_state_for_ui(self, state: BondState) -> None:
        super()._set_bond_state_for_ui(state)
        self._refresh_emote_catalogue()

    def _show_emote_catalogue(self) -> None:
        if self._preview_mode:
            return
        window = self._ensure_emote_catalogue_window()
        window.refresh(self._bond_state, force=True)
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
