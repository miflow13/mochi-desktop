from __future__ import annotations

import json
from pathlib import Path

from mochi.presence.clicks import ClickBurstDetector


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "mochi" / "manifest.json"


def test_fedora_secret_requires_six_rapid_clicks() -> None:
    detector = ClickBurstDetector(required_clicks=6, window_seconds=2.4)

    for timestamp in (1.0, 1.2, 1.4, 1.6, 1.8):
        assert detector.record(now=timestamp) is False

    assert detector.record(now=2.0) is True


def test_fedora_secret_resets_when_clicks_are_not_rapid() -> None:
    detector = ClickBurstDetector(required_clicks=6, window_seconds=2.4)

    for timestamp in (1.0, 1.5, 2.0, 2.5, 3.0):
        assert detector.record(now=timestamp) is False

    assert detector.record(now=4.0) is False


def test_fedora_manifest_preserves_handoff_timing_and_sequence() -> None:
    animations = json.loads(MANIFEST.read_text())["animations"]

    intro = animations["fedora_intro"]
    loop = animations["fedora_loop"]
    outro = animations["fedora_outro"]

    assert intro["frame_count"] == 16
    assert intro["loop"] is False
    assert abs(intro["fps"] - (1000 / 120)) < 0.01

    assert loop["frame_count"] == 12
    assert loop["loop"] is True
    assert loop["source_cell_size"] == [64, 64]
    assert abs(loop["fps"] - (1000 / 120)) < 0.01

    assert outro["frame_count"] == 13
    assert outro["loop"] is False
    assert abs(outro["fps"] - (1000 / 120)) < 0.01

    for name in ("fedora_intro", "fedora_loop", "fedora_outro"):
        for relative_path in animations[name]["frames"]:
            assert (ROOT / "assets" / "mochi" / relative_path).exists()
