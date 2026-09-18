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
        self.assertEqual(idle.frame_duration_ms, 667)
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

    def test_every_runtime_frame_matches_its_declared_source_size(self) -> None:
        assets = AnimationAssetSet()

        self.assertTrue(assets.animations)
        for animation in assets.animations.values():
            if animation.spritesheet_path is not None:
                path = assets.root / animation.spritesheet_path
                surface = cairo.ImageSurface.create_from_png(str(path))
                expected_size = (
                    animation.source_cell_size[0] * len(animation.frame_paths),
                    animation.source_cell_size[1],
                )
                self.assertEqual(
                    (surface.get_width(), surface.get_height()),
                    expected_size,
                    path.relative_to(assets.root),
                )
                self.assertEqual(
                    surface.get_content(),
                    cairo.CONTENT_COLOR_ALPHA,
                    path.relative_to(assets.root),
                )
                continue

            for relative_path in animation.frame_paths:
                path = assets.root / relative_path
                surface = cairo.ImageSurface.create_from_png(str(path))
                self.assertEqual(
                    (surface.get_width(), surface.get_height()),
                    animation.source_cell_size,
                    path.relative_to(assets.root),
                )
                self.assertEqual(
                    surface.get_content(),
                    cairo.CONTENT_COLOR_ALPHA,
                    path.relative_to(assets.root),
                )

    def test_loaded_frames_are_canonical_256px_surfaces(self) -> None:
        assets = AnimationAssetSet()

        for name in assets.animations:
            loaded = assets.load_frames(name)
            self.assertTrue(loaded)
            self.assertTrue(
                all(
                    (surface.get_width(), surface.get_height()) == (256, 256)
                    for surface in loaded.values()
                ),
                name,
            )

    def test_manifest_is_the_complete_runtime_png_inventory(self) -> None:
        assets = AnimationAssetSet()
        declared: set[str] = set()
        for animation in assets.animations.values():
            if animation.spritesheet_path is not None:
                declared.add(Path(animation.spritesheet_path).as_posix())
            else:
                declared.update(
                    Path(path).as_posix()
                    for path in animation.frame_paths
                )
        actual = {
            path.relative_to(assets.root).as_posix()
            for path in assets.root.rglob("*.png")
        }

        self.assertEqual(
            actual,
            declared,
            "assets/mochi must contain only PNG frames declared in manifest.json",
        )

    def test_runtime_asset_directory_contains_no_archives(self) -> None:
        assets = AnimationAssetSet()
        archives = sorted(
            path.relative_to(assets.root).as_posix()
            for pattern in ("*.zip", "*.tar", "*.tar.gz", "*.7z")
            for path in assets.root.rglob(pattern)
        )

        self.assertEqual(
            archives,
            [],
            "authoring/export archives do not belong in assets/mochi",
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


    def test_spritesheet_frames_are_virtual_runtime_keys() -> None:
        assets = AnimationAssetSet()
        side_eye = assets.animations["side_eye"]

        assert side_eye.spritesheet_path == "side_eye/side_eye.png"
        assert all("#" in key for key in side_eye.frame_paths)
        assert not any((assets.root / key).exists() for key in side_eye.frame_paths)
        loaded = assets.load_frames("side_eye")
        assert set(loaded) == set(side_eye.frame_paths)
