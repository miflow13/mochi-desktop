"""Large bond-aware emote collection window and manual emote dispatch."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import logging

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

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
    rarity: str = "common"

    def is_unlocked(self, state: BondState) -> bool:
        return bool(
            self.available
            and self.required_bond_level is not None
            and state.level >= self.required_bond_level
        )


EMOTE_CATALOGUE = (
    EmoteDefinition("heart", "Heart", "heart", 1, rarity="common"),
    EmoteDefinition("bounce", "Bounce", "bounce", 1, rarity="common"),
    EmoteDefinition("squish", "Squish", "squish", 1, rarity="uncommon"),
    EmoteDefinition("look", "Look Around", "look", 3, rarity="rare"),
    EmoteDefinition("dance", "Dance", "dance", 5, rarity="epic"),
    EmoteDefinition("mystery-1", "Mystery Emote I", None, None, False, "legendary"),
    EmoteDefinition("mystery-2", "Mystery Emote II", None, None, False, "legendary"),
    EmoteDefinition("mystery-3", "Mystery Emote III", None, None, False, "legendary"),
)
EMOTES_BY_ID = {emote.id: emote for emote in EMOTE_CATALOGUE}


@dataclass(frozen=True, slots=True)
class RarityStyle:
    label: str
    colour: tuple[float, float, float]
    ornament_count: int


RARITY_STYLES = {
    "common": RarityStyle("COMMON", (0.42, 0.50, 0.48), 1),
    "uncommon": RarityStyle("UNCOMMON", (0.25, 0.67, 0.42), 2),
    "rare": RarityStyle("RARE", (0.27, 0.53, 0.88), 3),
    "epic": RarityStyle("EPIC", (0.66, 0.38, 0.87), 4),
    "legendary": RarityStyle("LEGENDARY", (0.88, 0.62, 0.19), 5),
}


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

    Eight long cards fit in four rows, so a scroller and dozens of independently
    measured GTK widgets are unnecessary. The canvas is rendered into one cached
    surface only when bond state or display scale changes. Opening an unchanged
    catalogue reuses that surface immediately.
    """

    COLUMNS = 2
    CARD_WIDTH = 410
    CARD_HEIGHT = 112
    GAP = 16
    PREVIEW_SIZE = 88
    WIDTH = COLUMNS * CARD_WIDTH + (COLUMNS - 1) * GAP
    ROWS = (len(EMOTE_CATALOGUE) + COLUMNS - 1) // COLUMNS
    HEIGHT = ROWS * CARD_HEIGHT + (ROWS - 1) * GAP

    def __init__(self, *, atlas: SpriteAtlas) -> None:
        super().__init__()
        self._atlas = atlas
        self._state: BondState | None = None
        self._surface: cairo.ImageSurface | None = None
        self.set_content_width(self.WIDTH)
        self.set_content_height(self.HEIGHT)
        self.set_halign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw)
        self.connect("notify::scale-factor", self._on_scale_factor_changed)

    def refresh(self, state: BondState) -> None:
        state = BondState(level=state.level, xp=state.xp)
        if state == self._state and self._surface is not None:
            return
        self._state = state
        self._render_surface()

    def _on_scale_factor_changed(self, *_args) -> None:
        if self._state is not None:
            self._render_surface()

    def _render_surface(self) -> None:
        if self._state is None:
            return

        scale = max(1, self.get_scale_factor())
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, self.WIDTH * scale, self.HEIGHT * scale
        )
        surface.set_device_scale(scale, scale)
        context = cairo.Context(surface)
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)

        for index, emote in enumerate(EMOTE_CATALOGUE):
            column = index % self.COLUMNS
            row = index // self.COLUMNS
            self._draw_card(
                context,
                emote,
                column * (self.CARD_WIDTH + self.GAP),
                row * (self.CARD_HEIGHT + self.GAP),
            )

        surface.flush()
        # Swap the completed surface atomically, then ask GTK for one repaint.
        # This avoids eight full-area paints and eight GLib timer callbacks for
        # a catalogue that contains only eight static cards.
        self._surface = surface
        self.queue_draw()

    def _draw_card(
        self,
        context: cairo.Context,
        emote: EmoteDefinition,
        x: int,
        y: int,
    ) -> None:
        unlocked = emote.is_unlocked(self._state)
        rarity = RARITY_STYLES[emote.rarity]
        red, green, blue = rarity.colour
        context.save()
        context.translate(x, y)
        self._rounded_rectangle(
            context, 0.5, 0.5, self.CARD_WIDTH - 1, self.CARD_HEIGHT - 1, 14
        )
        background = cairo.LinearGradient(0, 0, 0, self.CARD_HEIGHT)
        background.add_color_stop_rgba(
            0, red, green, blue, 0.16 if unlocked else 0.055
        )
        background.add_color_stop_rgba(1, red, green, blue, 0.025)
        context.set_source(background)
        context.fill()
        context.set_source_rgba(red, green, blue, 0.54 if unlocked else 0.20)
        context.set_line_width(1)
        self._rounded_rectangle(
            context, 0.5, 0.5, self.CARD_WIDTH - 1, self.CARD_HEIGHT - 1, 14
        )
        context.stroke()

        context.set_source_rgba(red, green, blue, 0.10)
        self._rounded_rectangle(context, 12, 12, 96, 88, 10)
        context.fill()

        self._draw_ornaments(context, rarity)

        frame = self._preview_frame(emote)
        context.save()
        context.translate(16, 12)
        if unlocked:
            self._atlas.draw(context, frame, self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        else:
            self._draw_silhouette(context, frame)
        context.restore()

        self._draw_text(context, emote.label, 126, 42, 17, (0.12, 0.12, 0.12, 1), bold=True)
        status = emote_status_text(emote, self._state)
        status_colour = rarity.colour if unlocked else (0.38, 0.38, 0.38)
        self._draw_text(context, status, 126, 62, 10, status_colour, bold=True)
        self._draw_text(context, self._detail(emote, unlocked), 126, 88, 10, (0.40, 0.40, 0.40, 1))

        badge_width = 92
        badge_x = self.CARD_WIDTH - badge_width - 14
        context.set_source_rgba(red, green, blue, 0.14)
        self._rounded_rectangle(context, badge_x, 14, badge_width, 24, 12)
        context.fill()
        context.set_source_rgba(red, green, blue, 0.62)
        context.set_line_width(1)
        self._rounded_rectangle(context, badge_x, 14, badge_width, 24, 12)
        context.stroke()
        self._draw_text(context, rarity.label, badge_x + 12, 30, 9, rarity.colour, bold=True)
        context.restore()

    def _draw_ornaments(self, context: cairo.Context, rarity: RarityStyle) -> None:
        red, green, blue = rarity.colour
        for index in range(rarity.ornament_count):
            context.set_source_rgba(red, green, blue, 0.30 + index * 0.08)
            context.arc(
                self.CARD_WIDTH - 24 - index * 12,
                self.CARD_HEIGHT - 18,
                2.5,
                0,
                6.2832,
            )
            context.fill()

    @staticmethod
    def _rounded_rectangle(
        context: cairo.Context,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float,
    ) -> None:
        context.new_sub_path()
        context.arc(x + width - radius, y + radius, radius, -1.5708, 0)
        context.arc(x + width - radius, y + height - radius, radius, 0, 1.5708)
        context.arc(x + radius, y + height - radius, radius, 1.5708, 3.1416)
        context.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
        context.close_path()

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
            return "A little mood Mochi has learned."
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
    DEFAULT_HEIGHT = 780

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        atlas: SpriteAtlas,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._state: BondState | None = None

        self.window = Gtk.Window()
        self.window.set_title("Mochi Emote Catalogue")
        self.window.set_transient_for(owner)
        self.window.set_destroy_with_parent(True)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.connect("close-request", self._on_close_request)
        self.window.set_resizable(True)
        self.window.set_default_size(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.window.set_size_request(880, 680)
        self.window.add_css_class("mochi-emote-catalogue")

        # Keep this a native header-bar decoration. GTK reserves the remaining
        # header-bar area as the compositor-supported drag region on Wayland.
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        header.set_decoration_layout(":close")
        header.add_css_class("mochi-emote-header")
        # Leave the centre empty: Gtk.HeaderBar owns this native drag region.
        # The window title is still available to GNOME and assistive tooling.
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

        self._canvas = EmoteCatalogueCanvas(atlas=atlas)
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

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Keep the reusable catalogue alive when GTK's native X is clicked."""
        self.hide()
        return True

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
        # Reuse the retained surface when bond state has not changed. Hidden
        # catalogues intentionally skip live updates, so a changed state still
        # refreshes naturally here without forcing an unnecessary rebuild.
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
