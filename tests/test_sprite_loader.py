import json
import tempfile
import unittest
from pathlib import Path

from mochi.sprite_loader import AnimationAssetSet


class AnimationAssetSetTests(unittest.TestCase):
    def test_idle_metadata_builds_an_animation_from_the_manifest(self) -> None:
        assets = AnimationAssetSet()

        idle = assets.animation("idle")

        self.assertEqual(idle.name, "idle")
        self.assertEqual(len(idle.frames), 6)
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
                "anchor": "bottom-center",
                "scaling": "nearest-neighbor",
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
