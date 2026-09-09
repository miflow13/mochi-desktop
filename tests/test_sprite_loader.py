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
                (surface.get_width(), surface.get_height()) == (128, 128)
                for surface in first.values()
            )
        )

    def test_manifest_rejects_a_frame_path_outside_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "format": AnimationAssetSet.FORMAT,
                "cell_size": [128, 128],
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

    def test_spritesheet_frames_are_sliced_into_the_fixed_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sheet = cairo.ImageSurface(cairo.FORMAT_ARGB32, 128, 64)
            context = cairo.Context(sheet)
            context.set_source_rgba(1, 0, 0, 1)
            context.rectangle(0, 0, 64, 64)
            context.fill()
            context.set_source_rgba(0, 1, 0, 1)
            context.rectangle(64, 0, 64, 64)
            context.fill()
            sheet.write_to_png(str(root / "sheet.png"))
            manifest = {
                "format": AnimationAssetSet.FORMAT,
                "cell_size": [128, 128],
                "animations": {
                    "pickup": {
                        "spritesheet": "sheet.png",
                        "frame_count": 2,
                        "frame_width": 64,
                        "frame_height": 64,
                        "fps": 8.333333333333334,
                        "loop": False,
                    }
                },
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            assets = AnimationAssetSet(path)
            animation = assets.animation("pickup")
            frames = assets.load_frames("pickup")

            self.assertEqual(len(animation.frames), 2)
            self.assertEqual(animation.frame_duration_ms, 120)
            self.assertEqual(len(frames), 2)
            self.assertTrue(
                all(
                    (surface.get_width(), surface.get_height()) == (128, 128)
                    for surface in frames.values()
                )
            )


if __name__ == "__main__":
    unittest.main()
