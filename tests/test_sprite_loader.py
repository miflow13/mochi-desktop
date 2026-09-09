import json
import tempfile
import unittest
from pathlib import Path

import cairo

from mochi.sprite_loader import AnimationAssetSet


class AnimationAssetSetTests(unittest.TestCase):
    def test_idle_metadata_builds_an_animation_from_the_manifest(self) -> None:
        assets = AnimationAssetSet()

        idle = assets.animation("idle")

        self.assertEqual(idle.name, "idle")
        self.assertEqual(len(idle.frames), 6)
        self.assertEqual(idle.frame_duration_ms, 400)
        self.assertTrue(idle.looping)
        self.assertIsNone(idle.next_state)

    def test_idle_frames_are_loaded_once_at_the_manifest_cell_size(self) -> None:
        assets = AnimationAssetSet()

        first = assets.load_frames("idle")
        second = assets.load_frames("idle")

        self.assertEqual(set(first), set(second))
        self.assertTrue(
            all(first[path] is second[path] for path in first)
        )
        self.assertTrue(
            all(
                (surface.get_width(), surface.get_height()) == (256, 256)
                for surface in first.values()
            )
        )

    def test_every_mochi_png_is_a_256px_rgba_asset(self) -> None:
        assets = AnimationAssetSet()
        paths = tuple(assets.root.rglob("*.png"))

        self.assertTrue(paths)
        for path in paths:
            surface = cairo.ImageSurface.create_from_png(str(path))
            self.assertEqual(
                (surface.get_width(), surface.get_height()),
                (256, 256),
                path.relative_to(assets.root),
            )
            self.assertEqual(
                surface.get_content(),
                cairo.CONTENT_COLOR_ALPHA,
                path.relative_to(assets.root),
            )

    def test_manifest_rejects_a_frame_path_outside_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "format": AnimationAssetSet.FORMAT,
                "cell_size": [256, 256],
                "animations": {
                    "idle": {
                        "frames": ["../outside.png"],
                        "frame_count": 1,
                        "fps": 2,
                        "loop": True,
                    }
                },
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            assets = AnimationAssetSet(path)

            with self.assertRaises(ValueError):
                assets.load_frames("idle")


if __name__ == "__main__":
    unittest.main()
