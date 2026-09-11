from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "mochi" / "manifest.json"


def test_terminal_coworking_manifest_has_authored_transitions() -> None:
    animations = json.loads(MANIFEST.read_text())["animations"]

    intro = animations["terminal_intro"]
    loop = animations["terminal_loop"]
    outro = animations["terminal_outro"]

    assert intro == {
        "frames": [
            "terminal/terminal_intro_01.png",
            "terminal/terminal_intro_02.png",
            "terminal/terminal_intro_03.png",
            "terminal/terminal_intro_04.png",
        ],
        "frame_count": 4,
        "fps": 8.333333333333334,
        "loop": False,
    }
    assert loop["frame_count"] == 8
    assert loop["loop"] is True
    assert abs(loop["fps"] - (1000 / 120)) < 0.01
    assert outro == {
        "frames": [
            "terminal/terminal_outro_01.png",
            "terminal/terminal_outro_02.png",
            "terminal/terminal_outro_03.png",
            "terminal/terminal_outro_04.png",
        ],
        "frame_count": 4,
        "fps": 8.333333333333334,
        "loop": False,
    }

    for name in ("terminal_intro", "terminal_loop", "terminal_outro"):
        for relative_path in animations[name]["frames"]:
            assert (ROOT / "assets" / "mochi" / relative_path).exists()
