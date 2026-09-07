"""Build stable blink frames from the finished neutral idle pose."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "mochi" / "idle" / "idle_01.png"
TARGETS = (
    ROOT / "assets" / "mochi" / "blink",
    ROOT / "assets" / "mochi_original_set" / "frames" / "blink",
)
EYE_BOXES = ((40, 83, 54, 99), (76, 83, 90, 99))


def _clear_eyes(image: Image.Image) -> None:
    source = image.copy()
    for left, top, right, bottom in EYE_BOXES:
        for y in range(top, bottom):
            start = source.getpixel((left - 1, y))
            end = source.getpixel((right, y))
            for x in range(left, right):
                weight = (x - left + 1) / (right - left + 1)
                color = tuple(
                    round(a + (b - a) * weight)
                    for a, b in zip(start, end, strict=True)
                )
                image.putpixel((x, y), color)


def build_frames() -> tuple[Image.Image, ...]:
    neutral = Image.open(SOURCE).convert("RGBA")
    closing = neutral.copy()
    closed = neutral.copy()
    _clear_eyes(closing)
    _clear_eyes(closed)

    closing_draw = ImageDraw.Draw(closing)
    closed_draw = ImageDraw.Draw(closed)
    black = (0, 0, 0, 255)
    for center_x in (47, 83):
        closing_draw.rectangle((center_x - 4, 91, center_x + 4, 93), fill=black)
        closed_draw.rectangle((center_x - 4, 93, center_x + 4, 95), fill=black)
        closed_draw.point((center_x - 3, 96), fill=black)
        closed_draw.point((center_x + 3, 96), fill=black)

    return neutral, closing, closed, neutral.copy()


def main() -> None:
    frames = build_frames()
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(frames, start=1):
            frame.save(target / f"blink_{index:02d}.png", optimize=True)


if __name__ == "__main__":
    main()
