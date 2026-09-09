#!/usr/bin/env python3
"""Import the approved PixelLab idle and click/squish artwork."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets" / "mochi"


def _extract_handoff(source: Path, destination: Path) -> Path:
    if source.is_dir():
        return source
    with zipfile.ZipFile(source) as archive:
        archive.extractall(destination)
    roots = [path for path in destination.iterdir() if path.is_dir()]
    return roots[0] if len(roots) == 1 else destination


def _find_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern!r} below {root}, found {len(matches)}")
    return matches[0]


def _normalize(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        image = image.convert("RGBA")
        if image.size == (64, 64):
            image = image.resize((128, 128), Image.Resampling.NEAREST)
        elif image.size != (128, 128):
            raise ValueError(f"Expected a 64x64 or 128x128 source frame, got {image.size}")
        image.save(destination)


def import_assets(source: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="mochi-pixellab-import-") as temp:
        handoff = _extract_handoff(source, Path(temp))
        idle_source = _find_one(handoff, "south.png")
        squish_sources = sorted(handoff.rglob("frame_*.png"))
        if len(squish_sources) != 9:
            raise RuntimeError(f"Expected 9 squish frames, found {len(squish_sources)}")

        idle_dir = ASSET_ROOT / "idle"
        squish_dir = ASSET_ROOT / "squish"
        idle_dir.mkdir(parents=True, exist_ok=True)
        squish_dir.mkdir(parents=True, exist_ok=True)

        for old in (*idle_dir.glob("*.png"), *squish_dir.glob("*.png")):
            old.unlink()
        for index in range(1, 7):
            _normalize(idle_source, idle_dir / f"idle_{index:02d}.png")
        for index, frame in enumerate(squish_sources, 1):
            _normalize(frame, squish_dir / f"squish_{index:02d}.png")

        manifest_path = ASSET_ROOT / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        squish = manifest["animations"]["squish"]
        squish["frames"] = [f"squish/squish_{index:02d}.png" for index in range(1, 10)]
        squish["frame_count"] = 9
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="PixelLab handoff directory or ZIP")
    args = parser.parse_args()
    import_assets(args.source.resolve())


if __name__ == "__main__":
    main()
