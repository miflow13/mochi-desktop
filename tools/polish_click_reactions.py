"""Build restrained bounce and squish reactions from the neutral Mochi sprite."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "mochi" / "idle" / "idle_01.png"
TARGET_ROOTS = (
    ROOT / "assets" / "mochi",
    ROOT / "assets" / "mochi_original_set" / "frames",
)
SOURCE_BOX = (11, 26, 116, 128)


def _pose(width: int, height: int, bottom: int = 128) -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    sprite = source.crop(SOURCE_BOX).resize(
        (width, height), Image.Resampling.NEAREST
    )
    frame = Image.new("RGBA", (128, 128))
    frame.alpha_composite(sprite, ((128 - width) // 2, bottom - height))
    return frame


def _neutral() -> Image.Image:
    return Image.open(SOURCE).convert("RGBA")


def _with_scrunched_eyes(frame: Image.Image) -> Image.Image:
    """Replace only the two open-eye regions with a compact squeezed face."""
    frame = frame.copy()
    source = frame.copy()
    for left, top, right, bottom in ((38, 90, 53, 102), (77, 90, 93, 102)):
        for y in range(top, bottom):
            start = source.getpixel((left - 1, y))
            end = source.getpixel((right, y))
            for x in range(left, right):
                amount = (x - left + 1) / (right - left + 1)
                frame.putpixel(
                    (x, y),
                    tuple(
                        round(a + (b - a) * amount)
                        for a, b in zip(start, end, strict=True)
                    ),
                )
    draw = ImageDraw.Draw(frame)
    black = (0, 0, 0, 255)
    draw.line(((41, 94), (46, 98), (41, 101)), fill=black, width=2)
    draw.line(((90, 94), (85, 98), (90, 101)), fill=black, width=2)
    return frame


def bounce_frames() -> tuple[Image.Image, ...]:
    return (
        _neutral(),             # neutral anticipation
        _pose(109, 94),         # small grounded crouch
        _pose(99, 106),         # upward stretch
        _pose(99, 106, 121),    # small airborne peak
        _pose(113, 91),         # soft landing compression
        _pose(108, 99),         # elastic recovery
        _neutral(),             # exact handoff to idle
    )


def squish_frames() -> tuple[Image.Image, ...]:
    return (
        _neutral(),             # neutral
        _pose(110, 94),         # fast compression
        _with_scrunched_eyes(_pose(115, 86)),  # tactile maximum squish
        _pose(102, 104),        # tiny rebound
        _pose(108, 98),         # settle
        _neutral(),             # exact handoff to idle
    )


def main() -> None:
    animations = {"bounce": bounce_frames(), "squish": squish_frames()}
    for root in TARGET_ROOTS:
        for name, frames in animations.items():
            target = root / name
            target.mkdir(parents=True, exist_ok=True)
            for index, frame in enumerate(frames, start=1):
                frame.save(target / f"{name}_{index:02d}.png", optimize=True)


if __name__ == "__main__":
    main()
