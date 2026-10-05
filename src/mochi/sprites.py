"""Manifest-backed animation definitions and fixed-canvas sprite rendering."""

from __future__ import annotations

from dataclasses import replace
import math
import sys

import cairo

from mochi.animation import AnimationFrame
from mochi.interaction_tuning import (
    DRAG_FRAME_DURATION_MS,
    PICKUP_FRAME_DURATION_MS,
)
from mochi.sprite_loader import AnimationAssetSet


ASSET_SET = AnimationAssetSet()
ANIMATIONS = {name: ASSET_SET.animation(name) for name in ASSET_SET.animations}
ANIMATIONS["pickup"] = replace(
    ANIMATIONS["pickup"], frame_duration_ms=PICKUP_FRAME_DURATION_MS
)
ANIMATIONS["dragged"] = replace(
    ANIMATIONS["dragged"], frame_duration_ms=DRAG_FRAME_DURATION_MS
)
computer_frames = ANIMATIONS["computer"].frames
ANIMATIONS["computer_intro"] = replace(
    ANIMATIONS["computer"], name="computer_intro", frames=computer_frames[:4]
)
ANIMATIONS["computer_typing"] = replace(
    ANIMATIONS["computer"],
    name="computer_typing",
    frames=computer_frames[4:12],
    looping=True,
    next_state=None,
)
ANIMATIONS["computer_outro"] = replace(
    ANIMATIONS["computer"], name="computer_outro", frames=computer_frames[12:]
)
idle_frames = ANIMATIONS["idle"].frames
idle_durations = (900, 600, 450, 1_100, 500, 1_400)
idle_cycle = tuple(
    replace(frame, duration_ms=duration)
    for frame, duration in zip(idle_frames, idle_durations, strict=True)
)
ANIMATIONS["idle"] = replace(
    ANIMATIONS["idle"],
    frames=idle_cycle,
    frame_duration_ms=250,
)
blink_frames = ANIMATIONS["blink"].frames
blink_durations = (50, 55, 65, 85, 65, 55, 50)
ANIMATIONS["blink"] = replace(
    ANIMATIONS["blink"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(blink_frames, blink_durations, strict=True)
    ),
)
bounce_durations = (50, 75, 85, 95, 135, 145, 110)
ANIMATIONS["bounce"] = replace(
    ANIMATIONS["bounce"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["bounce"].frames, bounce_durations, strict=True
        )
    ),
)
sleep_durations = (90, 100, 120, 140, 160, 180)
ANIMATIONS["sleep"] = replace(
    ANIMATIONS["sleep"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["sleep"].frames, sleep_durations, strict=True
        )
    ),
    next_state="sleeping",
)
wake_durations = (70, 80, 90, 100, 100, 90)
ANIMATIONS["wake"] = replace(
    ANIMATIONS["wake"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["wake"].frames, wake_durations, strict=True
        )
    ),
)
squish_durations = (45, 70, 105, 120, 145, 125)
ANIMATIONS["squish"] = replace(
    ANIMATIONS["squish"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["squish"].frames, squish_durations, strict=True
        )
    ),
)
side_eye_durations = (120,) * 12 + (500,)
ANIMATIONS["side_eye"] = replace(
    ANIMATIONS["side_eye"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["side_eye"].frames,
            side_eye_durations,
            strict=True,
        )
    ),
)
ANIMATIONS["table_flip"] = replace(
    ANIMATIONS["table_flip"],
    frames=tuple(
        replace(frame, duration_ms=120)
        for frame in ANIMATIONS["table_flip"].frames
    ),
)
ANIMATIONS["excited"] = replace(ANIMATIONS["bounce"], name="excited")
# Curiosity's standing-idle beat: one pass of the magnifying-glass art. The
# file-activity "searching" emote keeps its own looping definition.
ANIMATIONS["investigate"] = replace(
    ANIMATIONS["searching"], name="investigate", looping=False
)
pocket_grab_frames = ANIMATIONS["pocket_grab"].frames
ANIMATIONS["pocket_hover"] = replace(
    ANIMATIONS["pocket_grab"],
    name="pocket_hover",
    frames=tuple(pocket_grab_frames[index - 1] for index in (4, 5, 6, 7, 6, 5)),
    looping=True,
    next_state=None,
)
ANIMATIONS["pocket_finish"] = replace(
    ANIMATIONS["pocket_grab"],
    name="pocket_finish",
    frames=(pocket_grab_frames[6], pocket_grab_frames[7]),
    looping=False,
    next_state="idle",
)


class SpriteAtlas:
    """Caches 256px asset frames and scales them to the configured window."""

    CANVAS_SIZE = (256, 256)
    OFFSET_COORDINATE_SIZE = 128

    def __init__(self) -> None:
        self.frames: dict[str, cairo.ImageSurface] = {}
        for name in ASSET_SET.animations:
            self.frames.update(ASSET_SET.load_frames(name))
        self._visible_bounds_cache: dict[str, tuple[int, int, int, int]] = {}

    def draw(
        self, context: cairo.Context, frame: AnimationFrame, width: int, height: int
    ) -> None:
        sprite = self.frames[frame.sprite]
        source_width, source_height = self.CANVAS_SIZE
        scale = min(width / source_width, height / source_height)
        offset_scale = min(width, height) / self.OFFSET_COORDINATE_SIZE
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
        context.set_source_surface(sprite, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()

    def draw_glow(
        self,
        context: cairo.Context,
        frame: AnimationFrame,
        width: int,
        height: int,
        *,
        pulse: float = 0.5,
    ) -> None:
        """Paint a soft breathing Pocket acceptance glow around the sprite."""
        pulse = max(0.0, min(1.0, float(pulse)))
        x, y, visible_width, visible_height = self.visible_bounds(
            frame,
            width,
            height,
        )
        center_x = x + visible_width / 2
        center_y = y + visible_height / 2

        # Keep the aura comfortably inside the transparent Buddy canvas so
        # GTK never clips a visible pixel into a square edge.
        edge_margin = 10.0
        max_radius_x = max(
            1.0,
            min(center_x, width - center_x) - edge_margin,
        )
        max_radius_y = max(
            1.0,
            min(center_y, height - center_y) - edge_margin,
        )

        # The halo must extend beyond Mochi's opaque body. Base the radius on
        # half the visible sprite size plus a small exterior halo, rather than
        # shrinking the whole gradient inside the sprite bounds.
        half_width = visible_width / 2
        half_height = visible_height / 2
        halo_x = min(10.0, max(5.0, visible_width * 0.11))
        halo_y = min(10.0, max(5.0, visible_height * 0.11))
        pulse_scale = 0.88 + 0.12 * pulse
        desired_radius_x = half_width + halo_x * pulse_scale
        desired_radius_y = half_height + halo_y * pulse_scale
        radius_x = min(max_radius_x, max(1.0, desired_radius_x))
        radius_y = min(max_radius_y, max(1.0, desired_radius_y))
        outer_alpha = 0.22 + 0.10 * pulse
        inner_alpha = 0.23 + 0.10 * pulse

        context.save()
        context.translate(center_x, center_y)
        context.scale(radius_x, radius_y)

        outer = cairo.RadialGradient(0.0, 0.0, 0.06, 0.0, 0.0, 1.0)
        outer.add_color_stop_rgba(0.0, 0.475, 0.788, 0.545, outer_alpha)
        outer.add_color_stop_rgba(
            0.55,
            0.475,
            0.788,
            0.545,
            outer_alpha * 0.62,
        )
        outer.add_color_stop_rgba(
            0.84,
            0.475,
            0.788,
            0.545,
            outer_alpha * 0.24,
        )
        outer.add_color_stop_rgba(1.0, 0.475, 0.788, 0.545, 0.0)
        context.set_source(outer)
        context.arc(0.0, 0.0, 1.0, 0.0, math.tau)
        context.fill()

        context.scale(0.66, 0.66)
        inner = cairo.RadialGradient(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        inner.add_color_stop_rgba(0.0, 0.56, 0.88, 0.63, inner_alpha)
        inner.add_color_stop_rgba(
            0.62,
            0.56,
            0.88,
            0.63,
            inner_alpha * 0.30,
        )
        inner.add_color_stop_rgba(1.0, 0.56, 0.88, 0.63, 0.0)
        context.set_source(inner)
        context.arc(0.0, 0.0, 1.0, 0.0, math.tau)
        context.fill()
        context.restore()

    def visible_bounds(
        self, frame: AnimationFrame, width: int, height: int
    ) -> tuple[float, float, float, float]:
        """Return the current frame's opaque bounds in Buddy-widget coordinates.

        Speech bubbles and future overlays should follow the visible character,
        not the full transparent 256x256 authoring canvas. Bounds are cached per
        sprite and transformed with the same scale/offset math used by draw().
        """
        left, top, right, bottom = self._source_visible_bounds(frame.sprite)
        source_width, source_height = self.CANVAS_SIZE
        scale = min(width / source_width, height / source_height)
        offset_scale = min(width, height) / self.OFFSET_COORDINATE_SIZE
        origin_x = (
            (width - source_width * scale) / 2
            + frame.horizontal_offset * offset_scale
        )
        origin_y = (
            (height - source_height * scale) / 2
            + frame.vertical_offset * offset_scale
        )
        return (
            origin_x + left * scale,
            origin_y + top * scale,
            max(1.0, (right - left) * scale),
            max(1.0, (bottom - top) * scale),
        )

    def _source_visible_bounds(self, sprite_name: str) -> tuple[int, int, int, int]:
        cached = self._visible_bounds_cache.get(sprite_name)
        if cached is not None:
            return cached

        surface = self.frames[sprite_name]
        width = surface.get_width()
        height = surface.get_height()
        if surface.get_format() != cairo.FORMAT_ARGB32:
            bounds = (0, 0, width, height)
            self._visible_bounds_cache[sprite_name] = bounds
            return bounds

        surface.flush()
        data = memoryview(surface.get_data())
        stride = surface.get_stride()
        alpha_offset = 3 if sys.byteorder == "little" else 0
        left = width
        top = height
        right = -1
        bottom = -1

        for y in range(height):
            row = y * stride
            for x in range(width):
                if data[row + x * 4 + alpha_offset] == 0:
                    continue
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)

        if right < left or bottom < top:
            bounds = (0, 0, width, height)
        else:
            bounds = (left, top, right + 1, bottom + 1)
        self._visible_bounds_cache[sprite_name] = bounds
        return bounds
