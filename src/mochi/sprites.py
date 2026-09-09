"""Manifest-backed animation definitions and fixed-canvas sprite rendering."""

from __future__ import annotations

from dataclasses import replace

import cairo

from mochi.animation import AnimationFrame
from mochi.sprite_loader import AnimationAssetSet


ASSET_SET = AnimationAssetSet()
ANIMATIONS = {name: ASSET_SET.animation(name) for name in ASSET_SET.animations}
ANIMATIONS["pickup"] = replace(ANIMATIONS["pickup"], next_state="dragged")
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
walk_bounce_durations = (80, 110, 125, 135, 180, 170, 130)
walk_bounce = replace(
    ANIMATIONS["bounce"],
    name="walk",
    frames=tuple(
        replace(frame, duration_ms=duration)
        for frame, duration in zip(
            ANIMATIONS["bounce"].frames, walk_bounce_durations, strict=True
        )
    ),
    looping=True,
    next_state=None,
)
ANIMATIONS["walk"] = walk_bounce
ANIMATIONS["walk_left"] = replace(walk_bounce, name="walk_left")
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
        x = round((width - 128 * scale) / 2 + frame.horizontal_offset * scale)
        y = round((height - 128 * scale) / 2 + frame.vertical_offset * height / 128)
        context.save()
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_surface(sprite, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()
