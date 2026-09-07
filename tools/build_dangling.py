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


def _dangling_frame(horizontal_offset: int, foot_offset: int) -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    sprite = source.crop((11, 26, 116, 128))
    # A narrow, slightly longer silhouette reads as gravity without making Mochi
    # look stretched or replacing the established face and palette.
    sprite = sprite.resize((97, 98), Image.Resampling.NEAREST)
    frame = Image.new("RGBA", (128, 128))
    x = (128 - sprite.width) // 2 + horizontal_offset
    frame.alpha_composite(sprite, (x, 21))

    draw = ImageDraw.Draw(frame)
    leg_color = source.getpixel((64, 121))
    shadow_color = source.getpixel((64, 126))
    left = 47 + horizontal_offset + foot_offset
    right = 75 + horizontal_offset - foot_offset
    for leg_x in (left, right):
        draw.rectangle((leg_x, 116, leg_x + 6, 126), fill=leg_color)
        draw.rectangle((leg_x + 1, 126, leg_x + 5, 127), fill=shadow_color)
    return frame


def build_frames() -> tuple[Image.Image, ...]:
    return (
        _dangling_frame(-1, -1),
        _dangling_frame(0, 0),
        _dangling_frame(1, 1),
    )


def main() -> None:
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(build_frames(), start=1):
            frame.save(target / f"dragged_{index:02d}.png", optimize=True)


if __name__ == "__main__":
    main()
