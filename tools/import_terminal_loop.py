"""Import the redrawn terminal typing loop from its Pixelorama export.

Usage:
    python3 tools/import_terminal_loop.py path/to/new_terminal_loop/

The export is 11 frames, 64 x 64 drawn and exported at 4x, 0.12 s each, the
same timing as the intro and outro. It is a palindrome (3-10, 4-9 and 5-8 are
the same drawing) with the middle pose held for two frames (6 and 7).

Frame 4 is pixel-identical to the intro's last frame once colors are snapped,
so the loop starts at frame 5: intro -> loop is then an ordinary one-frame
step instead of a pop (frame 1) or a doubled frame (frame 4). The rotated
loop ends on frame 4 and wraps back to 5, which is the artist's own step.

Colors get the same snap as the intro and outro (see import_terminal_tired).
Only terminal_NN.png is replaced; the intro and outro stay as they are.
"""

from __future__ import annotations

import sys
from pathlib import Path

from import_terminal_tired import TARGET, load_frame


SOURCE_NAME = "mochi_new_terminal_loop_{index:04d}.png"
FRAME_COUNT = 11
FIRST = 5


def loop_order() -> list[int]:
    return [(FIRST - 1 + offset) % FRAME_COUNT + 1 for offset in range(FRAME_COUNT)]


def main(source: Path) -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for old in TARGET.glob("terminal_[0-9][0-9].png"):
        old.unlink()
    for number, index in enumerate(loop_order(), start=1):
        frame = load_frame(source, index, source_name=SOURCE_NAME)
        frame.save(TARGET / f"terminal_{number:02d}.png", optimize=True)
    print(f"wrote {FRAME_COUNT} loop frames, starting at export frame {FIRST}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
