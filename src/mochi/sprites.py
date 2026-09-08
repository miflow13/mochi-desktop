"""Manifest-backed animation definitions and fixed-canvas sprite rendering."""

from __future__ import annotations

from dataclasses import replace

import cairo

from mochi.animation import AnimationFrame
from mochi.sprite_loader import AnimationAssetSet


ASSET_SET = AnimationAssetSet()
ANIMATIONS = {name: ASSET_SET.animation(name) for name in ASSET_SET.animations}

# Walking keeps the canonical PixelLab neutral texture while whole-canvas
# offsets restore a light stepping bounce. No alternate character art is used.
_walk_offsets = (0, -2, -5, -2, 0, -2, -5, -2)
for _walk_name in ("walk_right", "walk_left"):
    _walk = ANIMATIONS[_walk_name]
    ANIMATIONS[_walk_name] = replace(
        _walk,
        frames=tuple(
            replace(_walk.frames[0], vertical_offset=offset)
            for offset in _walk_offsets
        ),
    )


class SpriteAtlas:
    """Caches every manifest frame once and draws fixed 128px canvases."""

    CANVAS_SIZE = (128, 128)

    def __init__(self) -> None:
        self.frames = ASSET_SET.load_all()

    def draw(
        self, context: cairo.Context, frame: AnimationFrame, width: int, height: int
    ) -> None:
        sprite = self.frames[frame.sprite]
        scale = max(1, int(min(width / 128, height / 128)))
        if scale * 128 > width or scale * 128 > height:
            scale = min(width / 128, height / 128)
        x = round((width - 128 * scale) / 2 + frame.horizontal_offset * scale)
        y = round(height - 128 * scale + frame.vertical_offset * scale)
        context.save()
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_surface(sprite, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()
