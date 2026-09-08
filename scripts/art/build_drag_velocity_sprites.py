"""Build crisp 2D velocity poses from the canonical PixelLab idle sprite."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets" / "mochi" / "idle" / "idle_01.png"
TARGET = ROOT / "assets" / "mochi" / "drag"
CANVAS = 128
TOP = 20.0
BASELINE = 127.0
DIRECTIONS = {
    "right": (1, 0),
    "down_right": (1, 1),
    "down": (0, 1),
    "down_left": (-1, 1),
    "left": (-1, 0),
    "up_left": (-1, -1),
    "up": (0, -1),
    "up_right": (1, -1),
}


def _inverse_affine(
    a: float, b: float, c: float, d: float, e: float, f: float
) -> tuple[float, float, float, float, float, float]:
    determinant = a * e - b * d
    return (
        e / determinant,
        -b / determinant,
        (b * f - e * c) / determinant,
        -d / determinant,
        a / determinant,
        (d * c - a * f) / determinant,
    )


STRENGTHS = {
    "gentle": (7.0, 0.04, 0.06, 0.05),
    "medium": (15.0, 0.10, 0.16, 0.12),
    "strong": (26.0, 0.18, 0.34, 0.23),
}


def build_pose(
    source: Image.Image, dx: int, dy: int, strength: str
) -> Image.Image:
    length = math.hypot(dx, dy) or 1.0
    dx, dy = dx / length, dy / length
    amount, horizontal_stretch, vertical_stretch, horizontal_squash = (
        STRENGTHS[strength]
    )
    trail_x = -dx * amount
    trail_y = -dy * amount * 0.72
    height = BASELINE - TOP
    scale_x = (
        1.0
        + abs(dx) * horizontal_stretch
        - max(dy, 0.0) * vertical_stretch * 0.55
        + max(-dy, 0.0) * vertical_stretch * 0.65
    )
    scale_y = 1.0 - abs(dx) * horizontal_squash + dy * vertical_stretch

    # The top trails more than the planted lower body, making the sprout lag.
    a = scale_x
    b = -trail_x / height
    c = 64.0 * (1.0 - scale_x) + trail_x * BASELINE / height
    d = 0.0
    e = scale_y - trail_y / height
    f = BASELINE * (1.0 - scale_y) + trail_y * BASELINE / height
    return source.transform(
        (CANVAS, CANVAS),
        Image.Transform.AFFINE,
        _inverse_affine(a, b, c, d, e, f),
        resample=Image.Resampling.NEAREST,
    )


def main() -> None:
    with Image.open(SOURCE) as image:
        source = image.convert("RGBA")
    frames = {"neutral": source.copy()}
    for name, (dx, dy) in DIRECTIONS.items():
        for strength in STRENGTHS:
            frames[f"move_{name}_{strength}"] = build_pose(
                source, dx, dy, strength
            )

    TARGET.mkdir(parents=True, exist_ok=True)
    for old_frame in TARGET.glob("*.png"):
        old_frame.unlink()
    for name, frame in frames.items():
        frame.save(TARGET / f"{name}.png", optimize=True)


if __name__ == "__main__":
    main()
