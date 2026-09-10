"""Manifest-backed animation definitions and fixed-canvas sprite rendering."""

from __future__ import annotations

from dataclasses import replace
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
idle_durations = (750, 500, 350, 900, 400, 1_000)
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
blink_durations = (90, 90, 120, 90)
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
ANIMATIONS["excited"] = replace(ANIMATIONS["bounce"], name="excited")


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
