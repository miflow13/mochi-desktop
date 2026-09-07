"""Author subtle idle variants from Mochi's neutral fixed-canvas pose."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def tiny_inhale(neutral: Image.Image) -> Image.Image:
    frame = neutral.copy()
    pixels = frame.load()
    for x in range(24, 104):
        visible = [y for y in range(55, 81) if pixels[x, y][3]]
        if visible:
            y = visible[0]
            pixels[x, y - 1] = pixels[x, y]
    return frame


def tiny_exhale(neutral: Image.Image) -> Image.Image:
    frame = neutral.copy()
    pixels = frame.load()
    for y in range(78, 116):
        visible = [x for x in range(128) if pixels[x, y][3]]
        if visible:
            left, right = visible[0], visible[-1]
            if left > 0:
                pixels[left - 1, y] = pixels[left, y]
            if right < 127:
                pixels[right + 1, y] = pixels[right, y]
    return frame


def refine(directory: Path) -> None:
    neutral = Image.open(directory / "idle_01.png").convert("RGBA")
    frames = (
        neutral,
        neutral,
        tiny_inhale(neutral),
        neutral,
        tiny_exhale(neutral),
        neutral,
    )
    for index, frame in enumerate(frames, start=1):
        frame.save(directory / f"idle_{index:02d}.png", optimize=True)


def main() -> None:
    refine(Path("assets/mochi/idle"))
    staged = Path("assets/mochi_original_set/frames/idle")
    if staged.is_dir():
        refine(staged)


if __name__ == "__main__":
    main()
