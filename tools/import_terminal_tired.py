"""Import the "tired typing" terminal set from its Pixelorama export.

Usage:
    python3 tools/import_terminal_tired.py path/to/mochi_type_tired/

The export is 22 frames, 64 x 64 drawn and exported at 4x, 0.12 s each. It is
a palindrome: frames 17-22 are frames 6-1 reversed. It is split into:

    terminal_intro  frames 1-9    laptop comes out, Mochi settles in
    terminal_loop   frames 10-15  tired typing; frame 16 redraws frame 10,
                                  so 15 -> 10 is the artist's own seam
    terminal_outro  frames 16-22  last typing pose, laptop put away

The loop has since been redrawn; import_terminal_loop.py writes it. This
script only writes the intro and outro, so re-running it keeps the new loop.

Export drift left Mochi's colors 1-4 RGB units off the canonical palette, and
the export has a single dark color where Mochi uses two. Snapping them makes
frame 1 match the idle silhouette and colors, so idle -> intro does not pop.
Laptop colors are new artwork and are left alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "assets" / "mochi" / "terminal"
SOURCE_NAME = "mochi_type_tired_{index:04d}.png"
SOURCE_CELL = 64
RUNTIME_CELL = 256

INTRO = range(1, 10)
OUTRO = range(16, 23)

CANONICAL = {
    (0x03, 0x2D, 0x0C): (0x03, 0x30, 0x0D),  # outline
    (0x76, 0xE2, 0x85): (0x78, 0xE2, 0x86),
    (0x38, 0xC4, 0x59): (0x3B, 0xC4, 0x5B),
    (0x6F, 0xE5, 0x5B): (0x6D, 0xE6, 0x5C),
    (0x04, 0x1D, 0x11): (0x02, 0x18, 0x10),  # eyes: idle's near-black
    (0xF9, 0xFB, 0xFA): (0xF9, 0xFB, 0xF9),  # eye highlight
}


def load_frame(source: Path, index: int, *, source_name: str = SOURCE_NAME) -> Image.Image:
    with Image.open(source / source_name.format(index=index)) as image:
        exported = image.convert("RGBA")
    if exported.size != (RUNTIME_CELL, RUNTIME_CELL):
        raise ValueError(
            f"frame {index} is {exported.size}, expected {RUNTIME_CELL} x {RUNTIME_CELL}"
        )
    cell = exported.resize((SOURCE_CELL, SOURCE_CELL), Image.Resampling.NEAREST)
    if cell.resize(exported.size, Image.Resampling.NEAREST).tobytes() != exported.tobytes():
        raise ValueError(f"frame {index} is not a clean 4x nearest-neighbor export")

    pixels = cell.load()
    for y in range(SOURCE_CELL):
        for x in range(SOURCE_CELL):
            red, green, blue, alpha = pixels[x, y]
            if alpha not in (0, 255):
                raise ValueError(f"frame {index} has soft alpha at {(x, y)}")
            if alpha and (red, green, blue) in CANONICAL:
                pixels[x, y] = (*CANONICAL[(red, green, blue)], 255)
    return cell.resize(exported.size, Image.Resampling.NEAREST)


def main(source: Path) -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for old in (*TARGET.glob("terminal_intro_*.png"), *TARGET.glob("terminal_outro_*.png")):
        old.unlink()
    outputs = {
        "terminal_intro_{:02d}.png": INTRO,
        "terminal_outro_{:02d}.png": OUTRO,
    }
    for pattern, indices in outputs.items():
        for number, index in enumerate(indices, start=1):
            load_frame(source, index).save(TARGET / pattern.format(number), optimize=True)
    print(f"wrote {len(INTRO)} intro and {len(OUTRO)} outro frames")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
