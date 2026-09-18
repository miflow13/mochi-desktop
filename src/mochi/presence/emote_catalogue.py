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
.mochi-emote-footer {
    color: alpha(@theme_fg_color, 0.48);
    font-size: 11px;
}
"""


class EmoteCatalogueCanvas(Gtk.DrawingArea):
    """One retained Cairo canvas for all catalogue cards.

    Eight cards fit in two rows, so a scroller and dozens of independently
    measured GTK widgets are unnecessary. The canvas only re-rasterizes on a
    bond-state or display-scale change; pointer movement does not redraw it.
    """

    COLUMNS = 3
    CARD_WIDTH = 268
    CARD_HEIGHT = 178
    GAP = 16
    PREVIEW_SIZE = 104
    WIDTH = COLUMNS * CARD_WIDTH + (COLUMNS - 1) * GAP
    ROWS = (len(EMOTE_CATALOGUE) + COLUMNS - 1) // COLUMNS
    HEIGHT = ROWS * CARD_HEIGHT + (ROWS - 1) * GAP

    def __init__(self, *, atlas: SpriteAtlas, on_activate) -> None:
        super().__init__()
        self._atlas = atlas
        self._on_activate = on_activate
        self._state: BondState | None = None
        self._surface: cairo.ImageSurface | None = None
        self.set_content_width(self.WIDTH)
        self.set_content_height(self.HEIGHT)
        self.set_halign(Gtk.Align.CENTER)
        self.set_cursor_from_name("pointer")
        self.set_draw_func(self._draw)

        click = Gtk.GestureClick.new()
        click.connect("released", self._on_click)
        self.add_controller(click)
        self.connect("notify::scale-factor", self._on_scale_factor_changed)

    def refresh(self, state: BondState) -> None:
        state = BondState(level=state.level, xp=state.xp)
        if state == self._state:
            return
        self._state = state
        self._render()
        self.queue_draw()

    def emote_at(self, x: float, y: float) -> EmoteDefinition | None:
        column = int(x // (self.CARD_WIDTH + self.GAP))
        row = int(y // (self.CARD_HEIGHT + self.GAP))
        if column < 0 or column >= self.COLUMNS or row < 0 or row >= self.ROWS:
            return None
        card_x = column * (self.CARD_WIDTH + self.GAP)
        card_y = row * (self.CARD_HEIGHT + self.GAP)
        if x >= card_x + self.CARD_WIDTH or y >= card_y + self.CARD_HEIGHT:
            return None
        index = row * self.COLUMNS + column
        return EMOTE_CATALOGUE[index] if index < len(EMOTE_CATALOGUE) else None

    def _on_click(self, _gesture, _presses: int, x: float, y: float) -> None:
        emote = self.emote_at(x, y)
        if self._state is not None and emote is not None and emote.is_unlocked(self._state):
            self._on_activate(emote.id)

    def _on_scale_factor_changed(self, *_args) -> None:
        if self._state is not None:
            self._render()
            self.queue_draw()

    def _render(self) -> None:
        if self._state is None:
            return
        scale = max(1, self.get_scale_factor())
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.WIDTH * scale, self.HEIGHT * scale)
        surface.set_device_scale(scale, scale)
        context = cairo.Context(surface)
        for index, emote in enumerate(EMOTE_CATALOGUE):
            column = index % self.COLUMNS
            row = index // self.COLUMNS
            self._draw_card(
                context,
                emote,
                column * (self.CARD_WIDTH + self.GAP),
                row * (self.CARD_HEIGHT + self.GAP),
            )
        self._surface = surface

    def _draw_card(
        self,
        context: cairo.Context,
        emote: EmoteDefinition,
        x: int,
        y: int,
    ) -> None:
        unlocked = emote.is_unlocked(self._state)
        context.save()
        context.translate(x, y)
        context.set_source_rgba(0.32, 0.70, 0.41, 0.055)
        context.rectangle(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        context.fill()
        context.set_source_rgba(0.32, 0.70, 0.41, 0.16)
        context.set_line_width(1)
        context.rectangle(0.5, 0.5, self.CARD_WIDTH - 1, self.CARD_HEIGHT - 1)
        context.stroke()

        frame = self._preview_frame(emote)
        context.save()
        context.translate((self.CARD_WIDTH - self.PREVIEW_SIZE) / 2, 8)
        if unlocked:
            self._atlas.draw(context, frame, self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        else:
            self._draw_silhouette(context, frame)
        context.restore()

        self._draw_text(context, emote.label, 14, 126, 15, (0.12, 0.12, 0.12, 1), bold=True)
        status = emote_status_text(emote, self._state)
        colour = (0.18, 0.52, 0.28, 1) if unlocked else (0.38, 0.38, 0.38, 1)
        self._draw_text(context, status, 14, 145, 10, colour, bold=True)
        self._draw_text(context, self._detail(emote, unlocked), 14, 164, 10, (0.40, 0.40, 0.40, 1))
        context.restore()

    def _preview_frame(self, emote: EmoteDefinition):
        animation = ANIMATIONS[emote.animation or "idle"]
        return animation.frames[min(len(animation.frames) - 1, len(animation.frames) // 2)]

    def _draw_silhouette(self, context: cairo.Context, frame) -> None:
        sprite = self._atlas.frames[frame.sprite]
        source_width, source_height = self._atlas.CANVAS_SIZE
        scale = min(self.PREVIEW_SIZE / source_width, self.PREVIEW_SIZE / source_height)
        offset_scale = self.PREVIEW_SIZE / self._atlas.OFFSET_COORDINATE_SIZE
        x = round((self.PREVIEW_SIZE - source_width * scale) / 2 + frame.horizontal_offset * offset_scale)
        y = round((self.PREVIEW_SIZE - source_height * scale) / 2 + frame.vertical_offset * offset_scale)
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_rgba(0.10, 0.14, 0.11, 0.78)
        context.mask_surface(sprite, 0, 0)

    def _detail(self, emote: EmoteDefinition, unlocked: bool) -> str:
        if not emote.available:
            return "A future little mood."
        if unlocked:
            return "Click to ask Mochi to do this emote."
        remaining = bond_xp_until_level(self._state, emote.required_bond_level or self._state.level)
        return f"{remaining:,} bond XP remaining"

    @staticmethod
    def _draw_text(context, text: str, x: float, y: float, size: float, colour, *, bold: bool = False) -> None:
        weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
        context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, weight)
        context.set_font_size(size)
        context.set_source_rgba(*colour)
        context.move_to(x, y)
        context.show_text(text)

    def _draw(self, _area, context: cairo.Context, _width: int, _height: int) -> None:
        if self._surface is not None:
            context.set_source_surface(self._surface, 0, 0)
            context.paint()


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

        self._canvas = EmoteCatalogueCanvas(
            atlas=atlas,
            on_activate=self._on_card_activate,
        )
        self._canvas.set_margin_top(18)
        root.append(self._canvas)

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

        self._canvas.refresh(self._state)
        return True

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
