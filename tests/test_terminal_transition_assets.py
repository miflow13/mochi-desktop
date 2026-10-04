from __future__ import annotations

import json
from pathlib import Path

import cairo


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "mochi"
MANIFEST = ASSETS / "manifest.json"


def _animations() -> dict:
    return json.loads(MANIFEST.read_text())["animations"]


def _pixels(relative_path: str) -> bytes:
    return bytes(cairo.ImageSurface.create_from_png(str(ASSETS / relative_path)).get_data())


def _silhouette(relative_path: str) -> bytes:
    # ARGB32 is stored little-endian as BGRA; keep only alpha.
    return _pixels(relative_path)[3::4]


def test_terminal_coworking_manifest_has_authored_transitions() -> None:
    animations = _animations()

    intro = animations["terminal_intro"]
    loop = animations["terminal_loop"]
    outro = animations["terminal_outro"]

    assert intro == {
        "frames": [f"terminal/terminal_intro_{index:02d}.png" for index in range(1, 10)],
        "frame_count": 9,
        "fps": 8.333333333333334,
        "loop": False,
    }
    assert loop == {
        "frames": [f"terminal/terminal_{index:02d}.png" for index in range(1, 12)],
        "frame_count": 11,
        "fps": 8.333333333333334,
        "loop": True,
    }
    assert outro == {
        "frames": [f"terminal/terminal_outro_{index:02d}.png" for index in range(1, 8)],
        "frame_count": 7,
        "fps": 8.333333333333334,
        "loop": False,
    }

    for name in ("terminal_intro", "terminal_loop", "terminal_outro"):
        for relative_path in animations[name]["frames"]:
            assert (ASSETS / relative_path).exists()


def test_terminal_intro_opens_from_the_idle_silhouette() -> None:
    animations = _animations()

    assert _silhouette(animations["terminal_intro"]["frames"][0]) == _silhouette(
        animations["idle"]["frames"][0]
    )


def test_terminal_outro_puts_the_laptop_away_by_reversing_the_intro() -> None:
    animations = _animations()
    intro = animations["terminal_intro"]["frames"]
    outro = animations["terminal_outro"]["frames"]

    # Closing ends on the exact pose opening started from, and the laptop goes
    # away along the same frames it came out on.
    assert _pixels(outro[-1]) == _pixels(intro[0])
    assert [_pixels(path) for path in outro[1:]] == [
        _pixels(path) for path in reversed(intro[:6])
    ]


def test_terminal_loop_picks_up_one_step_after_the_intro_ends() -> None:
    animations = _animations()
    intro_end = _pixels(animations["terminal_intro"]["frames"][-1])
    loop = [_pixels(path) for path in animations["terminal_loop"]["frames"]]

    # The loop's last frame is the intro's last pose, so intro -> loop is the
    # same step as the loop's own wrap-around: no pop and no doubled frame.
    assert loop[-1] == intro_end
    assert loop[0] != intro_end
