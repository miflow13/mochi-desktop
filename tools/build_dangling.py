"""Build Mochi's subtle dangling drag loop from the neutral production sprite."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "mochi" / "idle" / "idle_01.png"
TARGETS = (
    ROOT / "assets" / "mochi" / "dragged",
    ROOT / "assets" / "mochi_original_set" / "frames" / "dragged",
)


def _dangling_frame(horizontal_offset: int, leg_sway: int, body_lean: int) -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    sprite = source.crop((11, 26, 116, 128)).resize(
        (100, 96), Image.Resampling.NEAREST
    )
    frame = Image.new("RGBA", (128, 128))
    x = (128 - sprite.width) // 2 + horizontal_offset
    y = 23

    # Keep the lower body anchored while shifting the upper bands opposite
    # travel. The stepped bands preserve crisp pixels while reading as squash.
    bands = (
        (0, 0, sprite.width, 34, body_lean),
        (0, 30, sprite.width, 68, body_lean // 2),
        (0, 64, sprite.width, sprite.height, 0),
    )
    for left, top, right, bottom, offset in bands:
        frame.alpha_composite(
            sprite.crop((left, top, right, bottom)),
            (x + offset, y + top),
        )

    draw = ImageDraw.Draw(frame)
    leg_outline = (1, 50, 5, 255)
    leg_color = (55, 202, 92, 255)
    leg_highlight = (112, 232, 124, 255)
    left = 47 + horizontal_offset + leg_sway
    right = 75 + horizontal_offset + leg_sway
    for leg_x in (left, right):
        draw.rectangle((leg_x - 1, 117, leg_x + 7, 127), fill=leg_outline)
        draw.rectangle((leg_x, 118, leg_x + 6, 125), fill=leg_color)
        draw.rectangle((leg_x + 1, 118, leg_x + 3, 120), fill=leg_highlight)
    return frame


def build_frames() -> tuple[Image.Image, ...]:
    return (
        _dangling_frame(-2, -5, -8),
        _dangling_frame(0, 0, 0),
        _dangling_frame(2, 5, 8),
    )


def main() -> None:
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(build_frames(), start=1):
            frame.save(target / f"dragged_{index:02d}.png", optimize=True)


if __name__ == "__main__":
    main()
