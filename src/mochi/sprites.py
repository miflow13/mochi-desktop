"""Sprite atlas coordinates, animation definitions, and one-time image loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import cairo

from mochi.animation import Animation, AnimationFrame


@dataclass(frozen=True)
class FrameRectangle:
    x: int
    y: int
    width: int
    height: int


# Explicit alpha-content bounds. The source is intentionally not a uniform grid.
FRAME_RECTANGLES = {
    "idle_1": FrameRectangle(266, 32, 200, 154),
    "idle_2": FrameRectangle(508, 29, 191, 166),
    "idle_3": FrameRectangle(739, 35, 196, 156),
    "idle_4": FrameRectangle(976, 50, 198, 141),
    "blink_1": FrameRectangle(402, 219, 199, 158),
    "blink_2": FrameRectangle(627, 234, 194, 145),
    "blink_3": FrameRectangle(850, 216, 194, 162),
    "walk_1": FrameRectangle(79, 397, 193, 156),
    "walk_2": FrameRectangle(305, 392, 181, 161),
    "walk_3": FrameRectangle(514, 405, 196, 154),
    "walk_4": FrameRectangle(739, 397, 195, 157),
    "walk_5": FrameRectangle(957, 401, 191, 156),
    "walk_6": FrameRectangle(1178, 398, 188, 156),
    "pose_1": FrameRectangle(259, 577, 191, 157),
    "pose_2": FrameRectangle(496, 613, 208, 123),
    "pose_3": FrameRectangle(745, 565, 194, 167),
    "pose_4": FrameRectangle(993, 582, 198, 147),
    "excited_1": FrameRectangle(256, 735, 194, 158),
    "excited_2": FrameRectangle(499, 756, 196, 139),
    "excited_3": FrameRectangle(738, 785, 214, 112),
    "excited_4": FrameRectangle(997, 738, 193, 158),
    "sleep_1": FrameRectangle(252, 908, 195, 150),
    "sleep_2": FrameRectangle(497, 906, 195, 155),
    "sleep_3": FrameRectangle(738, 923, 198, 137),
    "sleep_4": FrameRectangle(980, 896, 243, 161),
}


def _frames(
    *names: str, offsets: tuple[float, ...] | None = None
) -> tuple[AnimationFrame, ...]:
    frame_offsets = offsets or (0.0,) * len(names)
    return tuple(
        AnimationFrame(name, offset)
        for name, offset in zip(names, frame_offsets, strict=True)
    )


ANIMATIONS = {
    "idle": Animation("idle", _frames("idle_1", "idle_2", "idle_3", "idle_4", "idle_3", "idle_2"), 700, True, None),
    "blink": Animation("blink", _frames("blink_1", "blink_2", "blink_3"), 130),
    "walk": Animation("walk", _frames("walk_1", "walk_2", "walk_3", "walk_4", "walk_5", "walk_6"), 190, True, None),
    "bounce": Animation("bounce", _frames("pose_1", "pose_2", "pose_3", "pose_4", offsets=(0, 0, -12, -4)), 120),
    "squish": Animation("squish", _frames("pose_1", "pose_2", "pose_1"), 140),
    "excited": Animation("excited", _frames("excited_1", "excited_2", "excited_3", "excited_2", "excited_4"), 120),
    "sleep": Animation("sleep", _frames("sleep_1", "sleep_2", "sleep_3", "sleep_4"), 350, False, "sleeping"),
    "sleeping": Animation("sleeping", _frames("sleep_4"), 1_000, True, None),
    "wake": Animation("wake", _frames("sleep_4", "sleep_3", "sleep_2", "sleep_1"), 220),
    "dragged": Animation("dragged", _frames("pose_2"), 1_000, True, None),
}


class SpriteAtlas:
    """Loads the sheet once and caches all frame crops in memory."""

    SOURCE_SIZE = (1448, 1086)
    SCALE = 0.5
    BOTTOM_PADDING = 8

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self._find_sheet()
        sheet = cairo.ImageSurface.create_from_png(str(self.path))
        actual_size = (sheet.get_width(), sheet.get_height())
        if actual_size != self.SOURCE_SIZE:
            raise ValueError(f"Expected sprite sheet {self.SOURCE_SIZE}, got {actual_size}")
        self.frames = {
            name: self._crop(sheet, rect)
            for name, rect in FRAME_RECTANGLES.items()
        }

    @staticmethod
    def _crop(
        sheet: cairo.ImageSurface, rectangle: FrameRectangle
    ) -> cairo.ImageSurface:
        frame = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, rectangle.width, rectangle.height
        )
        context = cairo.Context(frame)
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_surface(sheet, -rectangle.x, -rectangle.y)
        context.paint()
        return frame

    @staticmethod
    def _find_sheet() -> Path:
        candidates = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "mochi"
            / "mochi-sprites.png",
            Path(sys.prefix) / "share" / "mochi" / "mochi-sprites.png",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError("Mochi sprite sheet was not found")

    def draw(
        self,
        context: cairo.Context,
        frame: AnimationFrame,
        width: int,
        height: int,
    ) -> None:
        sprite = self.frames[frame.sprite]
        rendered_width = sprite.get_width() * self.SCALE
        rendered_height = sprite.get_height() * self.SCALE
        x = round((width - rendered_width) / 2)
        y = round(
            height - self.BOTTOM_PADDING - rendered_height + frame.vertical_offset
        )

        context.save()
        context.translate(x, y)
        context.scale(self.SCALE, self.SCALE)
        context.set_source_surface(sprite, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()
