"""Large read-only bond-aware emote collection window."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.care import BondState, bond_xp_required
from mochi.emotes import (
    EMOTE_CATALOGUE,
    EMOTES_BY_ID,
    EmoteDefinition,
    next_emote_unlock,
)
from mochi.emote_shortcut import EmoteCatalogueShortcutMonitor
from mochi.sprites import ANIMATIONS, SpriteAtlas


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


EMOTES_PER_PAGE = 6


def catalogue_page_count(total: int, *, page_size: int = EMOTES_PER_PAGE) -> int:
    """Return at least one page so the catalogue shell always has stable UI."""
    normalized_size = max(1, int(page_size))
    normalized_total = max(0, int(total))
    return max(1, (normalized_total + normalized_size - 1) // normalized_size)


def catalogue_page_slice(
    emotes: tuple[EmoteDefinition, ...],
    page: int,
    *,
    page_size: int = EMOTES_PER_PAGE,
) -> tuple[EmoteDefinition, ...]:
    """Return a clamped page from the canonical catalogue ordering."""
    normalized_size = max(1, int(page_size))
    count = catalogue_page_count(len(emotes), page_size=normalized_size)
    normalized_page = max(0, min(int(page), count - 1))
    start = normalized_page * normalized_size
    return tuple(emotes[start : start + normalized_size])


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


def emote_status_text(
    emote: EmoteDefinition,
    state: BondState,
    *,
    unlock_all: bool = False,
) -> str:
    if not emote.available:
        return "COMING SOON"
    if emote.is_unlocked(state, unlock_all=unlock_all):
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
.mochi-emote-page-label {
    color: alpha(@theme_fg_color, 0.72);
    font-size: 12px;
    font-weight: 700;
}
button.mochi-emote-page-button {
    min-width: 40px;
    min-height: 34px;
    border-radius: 10px;
}
.mochi-emote-footer {
    color: alpha(@theme_fg_color, 0.48);
    font-size: 11px;
}
"""


class EmoteCatalogueCanvas(Gtk.DrawingArea):
    """Cached card catalogue with lightweight animated hover previews.

    Card chrome and resting preview art are rasterized once per bond
    level/display scale. Hovering a real emote advances that emote's existing
    sprite sequence with its authored frame timings while placeholders remain
    static. Pointer hover never rebuilds the cached surfaces.
    """

    COLUMNS = 2
    CARD_WIDTH = 410
    CARD_HEIGHT = 112
    GAP = 16
    GLOW_PAD = 12
    PREVIEW_SIZE = 88
    HOVER_LIFT = 4.0
    HOVER_INTERVAL_MS = 16
    HOVER_EASING = 0.34
    HOVER_EPSILON = 0.015
    WIDTH = (
        COLUMNS * CARD_WIDTH
        + (COLUMNS - 1) * GAP
        + GLOW_PAD * 2
    )
    ROWS = EMOTES_PER_PAGE // COLUMNS
    HEIGHT = (
        ROWS * CARD_HEIGHT
        + (ROWS - 1) * GAP
        + GLOW_PAD * 2
    )

    def __init__(
        self,
        *,
        atlas: SpriteAtlas,
        emotes: tuple[EmoteDefinition, ...] | None = None,
    ) -> None:
        super().__init__()
        self._atlas = atlas
        self._emotes = tuple(emotes or EMOTE_CATALOGUE[:EMOTES_PER_PAGE])
        self._state: BondState | None = None
        self._card_surfaces: list[cairo.ImageSurface] = []
        self._preview_surfaces: list[cairo.ImageSurface] = []
        self._render_scale = 0
        self._unlock_all = False
        self._hovered_index: int | None = None
        self._hover_progress = [0.0 for _ in self._emotes]
        self._hover_source_id: int | None = None
        self._hover_preview_source_id: int | None = None
        self._hover_preview_emote_id: str | None = None
        self._hover_preview_frame_index = 0

        self.set_content_width(self.WIDTH)
        self.set_content_height(self.HEIGHT)
        self.set_halign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw)
        self.connect("notify::scale-factor", self._on_scale_factor_changed)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    @classmethod
    def _card_origin(cls, index: int) -> tuple[float, float]:
        column = index % cls.COLUMNS
        row = index // cls.COLUMNS
        return (
            cls.GLOW_PAD + column * (cls.CARD_WIDTH + cls.GAP),
            cls.GLOW_PAD + row * (cls.CARD_HEIGHT + cls.GAP),
        )

    def card_index_at(self, x: float, y: float) -> int | None:
        for index in range(len(self._emotes)):
            card_x, card_y = self._card_origin(index)
            if (
                card_x <= x < card_x + self.CARD_WIDTH
                and card_y <= y < card_y + self.CARD_HEIGHT
            ):
                return index
        return None

    @property
    def emotes(self) -> tuple[EmoteDefinition, ...]:
        return self._emotes

    def set_emotes(self, emotes: tuple[EmoteDefinition, ...]) -> bool:
        next_emotes = tuple(emotes)
        if next_emotes == self._emotes:
            return False
        self.reset_hover()
        self._emotes = next_emotes
        self._hover_progress = [0.0 for _ in self._emotes]
        self._card_surfaces = []
        self._preview_surfaces = []
        self.queue_draw()
        return True

    def refresh(self, state: BondState, *, unlock_all: bool = False) -> None:
        state = BondState(level=state.level, xp=state.xp)
        previous = self._state
        previous_unlock_all = self._unlock_all
        self._state = state
        self._unlock_all = bool(unlock_all)
        if (
            previous is not None
            and state.level == previous.level
            and self._unlock_all == previous_unlock_all
            and len(self._card_surfaces) == len(self._emotes)
            and len(self._preview_surfaces) == len(self._emotes)
        ):
            return
        self._render_card_surfaces()

    def _on_scale_factor_changed(self, *_args) -> None:
        scale = max(1, self.get_scale_factor())
        if self._state is not None and scale != self._render_scale:
            self._render_card_surfaces()

    def _render_card_surfaces(self) -> None:
        if self._state is None:
            return

        scale = max(1, self.get_scale_factor())
        surfaces: list[cairo.ImageSurface] = []
        preview_surfaces: list[cairo.ImageSurface] = []
        for emote in self._emotes:
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32,
                self.CARD_WIDTH * scale,
                self.CARD_HEIGHT * scale,
            )
            surface.set_device_scale(scale, scale)
            context = cairo.Context(surface)
            context.set_operator(cairo.OPERATOR_CLEAR)
            context.paint()
            context.set_operator(cairo.OPERATOR_OVER)
            self._draw_card(context, emote, 0, 0)
            surface.flush()
            surfaces.append(surface)
            preview_surfaces.append(self._render_preview_surface(emote, scale))

        self._card_surfaces = surfaces
        self._preview_surfaces = preview_surfaces
        self._render_scale = scale
        self.queue_draw()

    def _render_preview_surface(
        self,
        emote: EmoteDefinition,
        scale: int,
    ) -> cairo.ImageSurface:
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32,
            self.PREVIEW_SIZE * scale,
            self.PREVIEW_SIZE * scale,
        )
        surface.set_device_scale(scale, scale)
        context = cairo.Context(surface)
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        self._draw_preview_frame(context, emote, self._preview_frame(emote))
        surface.flush()
        return surface

    def _on_motion(
        self,
        _controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        hovered = self.card_index_at(x, y)
        if hovered == self._hovered_index:
            return
        self._hovered_index = hovered
        self._start_hover_preview(hovered)
        self._ensure_hover_animation()
        self.queue_draw()

    def _on_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        if self._hovered_index is None:
            return
        self._hovered_index = None
        self._stop_hover_preview()
        self._ensure_hover_animation()
        self.queue_draw()

    def _ensure_hover_animation(self) -> None:
        if self._hover_source_id is not None:
            return
        self._hover_source_id = GLib.timeout_add(
            self.HOVER_INTERVAL_MS,
            self._tick_hover,
            priority=GLib.PRIORITY_LOW,
        )

    @staticmethod
    def _preview_animation_enabled(emote: EmoteDefinition) -> bool:
        if not emote.available or emote.animation is None:
            return False
        animation = ANIMATIONS[emote.animation]
        return len(animation.frames) > 1

    def _start_hover_preview(self, index: int | None) -> None:
        self._stop_hover_preview()
        if index is None:
            return

        emote = self._emotes[index]
        if not self._preview_animation_enabled(emote):
            return

        self._hover_preview_emote_id = emote.id
        self._hover_preview_frame_index = 0
        self._schedule_hover_preview_tick()

    def _stop_hover_preview(self) -> None:
        source_id = self._hover_preview_source_id
        self._hover_preview_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass
        self._hover_preview_emote_id = None
        self._hover_preview_frame_index = 0

    def _schedule_hover_preview_tick(self) -> None:
        if (
            self._hover_preview_source_id is not None
            or self._hover_preview_emote_id is None
        ):
            return

        emote = EMOTES_BY_ID[self._hover_preview_emote_id]
        animation = ANIMATIONS[emote.animation]
        frame = animation.frames[self._hover_preview_frame_index]
        delay_ms = max(16, frame.duration_ms or animation.frame_duration_ms)
        self._hover_preview_source_id = GLib.timeout_add(
            delay_ms,
            self._advance_hover_preview,
            priority=GLib.PRIORITY_LOW,
        )

    def _advance_hover_preview(self) -> bool:
        self._hover_preview_source_id = None
        emote_id = self._hover_preview_emote_id
        hovered_index = self._hovered_index
        if emote_id is None or hovered_index is None:
            return GLib.SOURCE_REMOVE

        emote = self._emotes[hovered_index]
        if emote.id != emote_id or not self._preview_animation_enabled(emote):
            self._stop_hover_preview()
            return GLib.SOURCE_REMOVE

        animation = ANIMATIONS[emote.animation]
        self._hover_preview_frame_index = (
            self._hover_preview_frame_index + 1
        ) % len(animation.frames)
        self.queue_draw()
        self._schedule_hover_preview_tick()
        return GLib.SOURCE_REMOVE

    @classmethod
    def _advance_hover_progress(
        cls,
        progress: tuple[float, ...],
        hovered_index: int | None,
    ) -> tuple[tuple[float, ...], bool]:
        updated_progress: list[float] = []
        animating = False
        for index, current in enumerate(progress):
            target = 1.0 if index == hovered_index else 0.0
            distance = target - current
            if abs(distance) <= cls.HOVER_EPSILON:
                updated = target
            else:
                updated = current + distance * cls.HOVER_EASING
                animating = True
            updated_progress.append(max(0.0, min(1.0, updated)))
        return tuple(updated_progress), animating

    def _tick_hover(self) -> bool:
        previous = tuple(self._hover_progress)
        updated, animating = self._advance_hover_progress(
            previous,
            self._hovered_index,
        )
        if updated != previous:
            self._hover_progress[:] = updated
            self.queue_draw()
        if animating:
            return GLib.SOURCE_CONTINUE

        self._hover_source_id = None
        return GLib.SOURCE_REMOVE

    def reset_hover(self) -> None:
        source_id = self._hover_source_id
        self._hover_source_id = None
        if source_id is not None:
            try:
                GLib.source_remove(source_id)
            except Exception:
                pass

        self._stop_hover_preview()
        had_hover = self._hovered_index is not None or any(self._hover_progress)
        self._hovered_index = None
        if had_hover:
            self._hover_progress[:] = (0.0 for _ in self._hover_progress)
            self.queue_draw()

    @staticmethod
    def _ease_out(progress: float) -> float:
        clamped = max(0.0, min(1.0, progress))
        return 1.0 - (1.0 - clamped) ** 3

    def _draw_card(
        self,
        context: cairo.Context,
        emote: EmoteDefinition,
        x: int,
        y: int,
    ) -> None:
        unlocked = emote.is_unlocked(
            self._state,
            unlock_all=self._unlock_all,
        )
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

        self._draw_text(
            context,
            emote.label,
            126,
            42,
            17,
            (0.12, 0.12, 0.12, 1),
            bold=True,
        )
        status = emote_status_text(
            emote,
            self._state,
            unlock_all=self._unlock_all,
        )
        status_colour = rarity.colour if unlocked else (0.38, 0.38, 0.38)
        self._draw_text(context, status, 126, 62, 10, status_colour, bold=True)
        self._draw_text(
            context,
            self._detail(emote, unlocked),
            126,
            88,
            10,
            (0.40, 0.40, 0.40, 1),
        )

        badge_width = 92
        badge_x = self.CARD_WIDTH - badge_width - 14
        context.set_source_rgba(red, green, blue, 0.14)
        self._rounded_rectangle(context, badge_x, 14, badge_width, 24, 12)
        context.fill()
        context.set_source_rgba(red, green, blue, 0.62)
        context.set_line_width(1)
        self._rounded_rectangle(context, badge_x, 14, badge_width, 24, 12)
        context.stroke()
        self._draw_text(
            context,
            rarity.label,
            badge_x + 12,
            30,
            9,
            rarity.colour,
            bold=True,
        )
        context.restore()

    def _draw_rarity_glow(
        self,
        context: cairo.Context,
        emote: EmoteDefinition,
        x: float,
        y: float,
        hover: float,
    ) -> None:
        if emote.rarity == "rare":
            base = 0.11
            boost = 0.11
        elif emote.rarity == "legendary":
            base = 0.18
            boost = 0.18
        else:
            return

        rarity = RARITY_STYLES[emote.rarity]
        red, green, blue = rarity.colour
        strength = base + boost * hover
        layers = (
            (8.0, 0.18),
            (5.0, 0.28),
            (2.5, 0.44),
        )
        for width, alpha_scale in layers:
            context.set_source_rgba(
                red,
                green,
                blue,
                strength * alpha_scale,
            )
            context.set_line_width(width)
            self._rounded_rectangle(
                context,
                x + 1,
                y + 1,
                self.CARD_WIDTH - 2,
                self.CARD_HEIGHT - 2,
                15,
            )
            context.stroke()

    def _draw_hover_outline(
        self,
        context: cairo.Context,
        emote: EmoteDefinition,
        x: float,
        y: float,
        hover: float,
    ) -> None:
        if hover <= 0:
            return
        rarity = RARITY_STYLES[emote.rarity]
        red, green, blue = rarity.colour
        context.set_source_rgba(red, green, blue, 0.16 + 0.34 * hover)
        context.set_line_width(1.0 + 1.25 * hover)
        self._rounded_rectangle(
            context,
            x + 1,
            y + 1,
            self.CARD_WIDTH - 2,
            self.CARD_HEIGHT - 2,
            14,
        )
        context.stroke()

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
        context.arc(
            x + width - radius,
            y + height - radius,
            radius,
            0,
            1.5708,
        )
        context.arc(
            x + radius,
            y + height - radius,
            radius,
            1.5708,
            3.1416,
        )
        context.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
        context.close_path()

    def _preview_frame(self, emote: EmoteDefinition):
        animation = ANIMATIONS[emote.animation or "idle"]
        return animation.frames[
            min(len(animation.frames) - 1, len(animation.frames) // 2)
        ]

    def _draw_preview_frame(
        self,
        context: cairo.Context,
        emote: EmoteDefinition,
        frame,
    ) -> None:
        unlocked = emote.is_unlocked(
            self._state,
            unlock_all=self._unlock_all,
        )
        if unlocked:
            self._atlas.draw(context, frame, self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        else:
            self._draw_silhouette(context, frame)

    def _draw_silhouette(self, context: cairo.Context, frame) -> None:
        sprite = self._atlas.frames[frame.sprite]
        source_width, source_height = self._atlas.CANVAS_SIZE
        scale = min(
            self.PREVIEW_SIZE / source_width,
            self.PREVIEW_SIZE / source_height,
        )
        offset_scale = self.PREVIEW_SIZE / self._atlas.OFFSET_COORDINATE_SIZE
        x = round(
            (self.PREVIEW_SIZE - source_width * scale) / 2
            + frame.horizontal_offset * offset_scale
        )
        y = round(
            (self.PREVIEW_SIZE - source_height * scale) / 2
            + frame.vertical_offset * offset_scale
        )
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_rgba(0.10, 0.14, 0.11, 0.78)
        context.mask_surface(sprite, 0, 0)

    def _detail(self, emote: EmoteDefinition, unlocked: bool) -> str:
        if not emote.available:
            return "A future little mood."
        if unlocked:
            return "A little mood Mochi has learned."
        return "Keep bonding to discover this mood."

    @staticmethod
    def _draw_text(
        context,
        text: str,
        x: float,
        y: float,
        size: float,
        colour,
        *,
        bold: bool = False,
    ) -> None:
        weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
        context.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, weight)
        context.set_font_size(size)
        context.set_source_rgba(*colour)
        context.move_to(x, y)
        context.show_text(text)

    def _draw(
        self,
        _area,
        context: cairo.Context,
        _width: int,
        _height: int,
    ) -> None:
        if (
            len(self._card_surfaces) != len(self._emotes)
            or len(self._preview_surfaces) != len(self._emotes)
        ):
            return

        for index, (emote, surface, preview_surface) in enumerate(
            zip(
                self._emotes,
                self._card_surfaces,
                self._preview_surfaces,
            )
        ):
            x, y = self._card_origin(index)
            hover = self._ease_out(self._hover_progress[index])
            lifted_y = y - self.HOVER_LIFT * hover

            self._draw_rarity_glow(context, emote, x, lifted_y, hover)
            context.set_source_surface(surface, x, lifted_y)
            context.paint()

            preview_x = x + 16
            preview_y = lifted_y + 12
            if (
                index == self._hovered_index
                and self._hover_preview_emote_id == emote.id
                and self._preview_animation_enabled(emote)
            ):
                animation = ANIMATIONS[emote.animation]
                frame = animation.frames[self._hover_preview_frame_index]
                context.save()
                context.translate(preview_x, preview_y)
                self._draw_preview_frame(context, emote, frame)
                context.restore()
            else:
                context.set_source_surface(
                    preview_surface,
                    preview_x,
                    preview_y,
                )
                context.paint()

            self._draw_hover_outline(context, emote, x, lifted_y, hover)


class EmoteCatalogueWindow:
    """Large reusable collection window opened by Mochi's global shortcut."""

    DEFAULT_WIDTH = 900
    DEFAULT_HEIGHT = 900

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        atlas: SpriteAtlas,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._state: BondState | None = None
        self._unlock_all = False
        self._current_page = 0

        application = owner.get_application()
        if application is not None:
            self.window = Gtk.ApplicationWindow(application=application)
        else:
            # Fallback keeps isolated tests/embedders usable without coupling the
            # catalogue to Mochi's tiny always-on-top buddy as a transient child.
            self.window = Gtk.Window()
        self.window.set_title("Mochi Emote Catalogue")
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_resizable(True)
        self.window.set_default_size(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.window.set_size_request(880, 780)
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

        self._canvas = EmoteCatalogueCanvas(
            atlas=atlas,
            emotes=self._page_emotes(),
        )
        self._canvas.set_margin_top(18)
        root.append(self._canvas)

        pagination = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        pagination.set_halign(Gtk.Align.CENTER)
        pagination.set_margin_top(10)

        self._previous_page_button = Gtk.Button(label="‹")
        self._previous_page_button.add_css_class("mochi-emote-page-button")
        self._previous_page_button.set_tooltip_text("Previous emote page")
        self._previous_page_button.connect("clicked", self._on_previous_page)
        pagination.append(self._previous_page_button)

        self._page_label = Gtk.Label()
        self._page_label.set_width_chars(7)
        self._page_label.set_xalign(0.5)
        self._page_label.add_css_class("mochi-emote-page-label")
        pagination.append(self._page_label)

        self._next_page_button = Gtk.Button(label="›")
        self._next_page_button.add_css_class("mochi-emote-page-button")
        self._next_page_button.set_tooltip_text("Next emote page")
        self._next_page_button.connect("clicked", self._on_next_page)
        pagination.append(self._next_page_button)

        root.append(pagination)
        self._update_page_controls()
        self.window.connect("notify::visible", self._on_visibility_changed)

        footer = Gtk.Label(label="Ctrl + Alt + E · ←/→ pages · Esc to close")
        footer.set_xalign(1)
        footer.set_margin_top(10)
        footer.add_css_class("mochi-emote-footer")
        root.append(footer)

        self.window.set_child(root)

    @property
    def page_count(self) -> int:
        return catalogue_page_count(len(EMOTE_CATALOGUE))

    def _page_emotes(self) -> tuple[EmoteDefinition, ...]:
        return catalogue_page_slice(EMOTE_CATALOGUE, self._current_page)

    def _update_page_controls(self) -> None:
        count = self.page_count
        self._current_page = max(0, min(self._current_page, count - 1))
        self._page_label.set_text(f"{self._current_page + 1} / {count}")
        self._previous_page_button.set_sensitive(self._current_page > 0)
        self._next_page_button.set_sensitive(self._current_page < count - 1)

    def _set_page(self, page: int) -> bool:
        count = self.page_count
        next_page = max(0, min(int(page), count - 1))
        if next_page == self._current_page:
            self._update_page_controls()
            return False

        self._current_page = next_page
        self._canvas.set_emotes(self._page_emotes())
        if self._state is not None:
            self._canvas.refresh(
                self._state,
                unlock_all=self._unlock_all,
            )
        self._update_page_controls()
        self._logger.debug(
            "Emote catalogue page %d/%d",
            self._current_page + 1,
            count,
        )
        return True

    def _on_previous_page(self, _button: Gtk.Button) -> None:
        self._set_page(self._current_page - 1)

    def _on_next_page(self, _button: Gtk.Button) -> None:
        self._set_page(self._current_page + 1)

    @property
    def visible(self) -> bool:
        return self.window.get_visible()

    def refresh(
        self,
        state: BondState,
        *,
        force: bool = False,
        unlock_all: bool = False,
    ) -> bool:
        next_state = BondState(level=state.level, xp=state.xp)
        next_unlock_all = bool(unlock_all)
        if (
            not force
            and next_state == self._state
            and next_unlock_all == self._unlock_all
        ):
            return False

        self._state = next_state
        self._unlock_all = next_unlock_all
        self._current_page = max(0, min(self._current_page, self.page_count - 1))
        self._canvas.set_emotes(self._page_emotes())
        self._update_page_controls()
        next_unlock = None if self._unlock_all else next_emote_unlock(self._state)

        if self._unlock_all:
            self._next_label.set_text(
                f"Bond Lv. {self._state.level} · all available emotes unlocked (developer) ✦"
            )
            self._progress.set_fraction(1.0)
        elif next_unlock is None:
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

        self._canvas.refresh(
            self._state,
            unlock_all=self._unlock_all,
        )
        return True

    def present(self) -> None:
        self.window.present()
        self._logger.debug("Emote catalogue opened")

    def hide(self) -> None:
        self._canvas.reset_hover()
        self.window.hide()

    def destroy(self) -> None:
        self._canvas.reset_hover()
        self.window.destroy()

    def _on_visibility_changed(self, window: Gtk.Window, _pspec=None) -> None:
        if not window.get_visible():
            self._canvas.reset_hover()

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
        if keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left):
            self._set_page(self._current_page - 1)
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Right):
            self._set_page(self._current_page + 1)
            return True
        return False


class EmoteCatalogueMixin:
    """Own the read-only catalogue window and its global shortcut bridge."""

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

    def _refresh_emote_catalogue(self, *, force: bool = False) -> None:
        window = self._emote_catalogue_window
        if window is not None and window.visible:
            window.refresh(
                self._bond_state,
                force=force,
                unlock_all=getattr(self, "_dev_unlock_all_emotes", False),
            )

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
        window.refresh(
            self._bond_state,
            unlock_all=getattr(self, "_dev_unlock_all_emotes", False),
        )
        window.present()

    def shutdown_presence(self) -> None:
        if self._emote_shortcut_monitor is not None:
            self._emote_shortcut_monitor.stop()
            self._emote_shortcut_monitor = None
        if self._emote_catalogue_window is not None:
            self._emote_catalogue_window.destroy()
            self._emote_catalogue_window = None
        super().shutdown_presence()
