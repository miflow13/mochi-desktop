"""Manifest-backed animation definitions and fixed-canvas sprite rendering."""

from __future__ import annotations

from dataclasses import replace

import cairo

from mochi.animation import AnimationFrame
from mochi.sprite_loader import AnimationAssetSet


ASSET_SET = AnimationAssetSet()
ANIMATIONS = {name: ASSET_SET.animation(name) for name in ASSET_SET.animations}
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
bounce_durations = (70, 100, 90, 120, 130, 110, 80)
ANIMATIONS["bounce"] = replace(
    ANIMATIONS["bounce"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["bounce"].frames, bounce_durations, strict=True
        )
    ),
)
squish_durations = (70, 85, 125, 95, 115, 80)
ANIMATIONS["squish"] = replace(
    ANIMATIONS["squish"],
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["squish"].frames, squish_durations, strict=True
        )
    ),
)
ANIMATIONS["sleep"] = replace(ANIMATIONS["sleep"], next_state="sleeping")
ANIMATIONS["excited"] = replace(ANIMATIONS["bounce"], name="excited")


class SpriteAtlas:
    """Caches every manifest frame once and draws fixed 128px canvases."""

    CANVAS_SIZE = (128, 128)

    def __init__(self) -> None:
        self.frames: dict[str, cairo.ImageSurface] = {}
        for name in ASSET_SET.animations:
            self.frames.update(ASSET_SET.load_frames(name))

    def draw(
        self, context: cairo.Context, frame: AnimationFrame, width: int, height: int
    ) -> None:
        sprite = self.frames[frame.sprite]
        scale = min(width / 128, height / 128)
        x = round((width - 128 * scale) / 2)
        y = round((height - 128 * scale) / 2 + frame.vertical_offset * height / 128)
        context.save()
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_surface(sprite, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()
