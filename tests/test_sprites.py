import unittest

import cairo

from mochi.sprites import ANIMATIONS, ASSET_SET, SpriteAtlas


class SpriteDefinitionsTests(unittest.TestCase):
    def test_every_animation_references_a_manifest_frame(self) -> None:
        known = {
            path
            for metadata in ASSET_SET.animations.values()
            for path in metadata.frame_paths
        }
        for animation in ANIMATIONS.values():
            for frame in animation.frames:
                self.assertIn(frame.sprite, known)

    def test_atlas_caches_every_manifest_frame_at_fixed_size(self) -> None:
        atlas = SpriteAtlas()
        expected = {
            path
            for metadata in ASSET_SET.animations.values()
            for path in metadata.frame_paths
        }
        self.assertEqual(set(atlas.frames), expected)
        self.assertTrue(
            all(
                (surface.get_width(), surface.get_height()) == (128, 128)
                and surface.get_content() == cairo.CONTENT_COLOR_ALPHA
                for surface in atlas.frames.values()
            )
        )

    def test_required_visible_states_use_manifest_art(self) -> None:
        required = {
            "idle", "blink", "walk_right", "walk_left", "bounce", "squish",
            "sleep", "wake", "excited", "hurt_sad", "curious", "sit", "dragged",
        }
        self.assertEqual(set(ANIMATIONS), required)

    def test_states_without_pixellab_art_explicitly_use_idle_fallback(self) -> None:
        fallback = ANIMATIONS["idle"].frames[0]
        fallback_states = {
            "blink", "bounce", "sleep", "wake", "excited", "hurt_sad",
            "curious", "sit",
        }

        for name in fallback_states:
            self.assertEqual(ANIMATIONS[name].frames, (fallback,), name)

    def test_every_runtime_png_is_referenced_by_the_manifest(self) -> None:
        referenced = {
            path
            for metadata in ASSET_SET.animations.values()
            for path in metadata.frame_paths
        }
        present = {
            str(path.relative_to(ASSET_SET.root))
            for path in ASSET_SET.root.rglob("*.png")
        }

        self.assertEqual(present, referenced)

    def test_sleep_transitions_to_sleeping(self) -> None:
        self.assertFalse(ANIMATIONS["sleep"].looping)
        self.assertEqual(ANIMATIONS["sleep"].frame_duration_ms, 400)
        self.assertFalse(ANIMATIONS["wake"].looping)
        self.assertEqual(ANIMATIONS["wake"].frame_duration_ms, 200)

    def test_idle_breathing_uses_slow_per_frame_timing(self) -> None:
        idle = ANIMATIONS["idle"]
        self.assertEqual(len(idle.frames), 6)
        surfaces = SpriteAtlas().frames
        idle_pixels = [bytes(surfaces[frame.sprite].get_data()) for frame in idle.frames]
        self.assertEqual(len(set(idle_pixels)), 1)
        self.assertTrue(idle.looping)

    def test_blink_uses_fast_per_frame_timing(self) -> None:
        blink = ANIMATIONS["blink"]
        self.assertEqual(blink.frame_duration_ms, 125)
        self.assertFalse(blink.looping)

    def test_drag_uses_complete_2d_velocity_pose_set(self) -> None:
        dragged = ANIMATIONS["dragged"]
        self.assertEqual(len(dragged.frames), 25)
        self.assertTrue(dragged.looping)
        surfaces = SpriteAtlas().frames
        drag_pixels = [bytes(surfaces[frame.sprite].get_data()) for frame in dragged.frames]
        self.assertEqual(len(set(drag_pixels)), 25)

    def test_walk_uses_a_slow_looping_bounce_prototype(self) -> None:
        self.assertTrue(ANIMATIONS["walk_right"].looping)
        self.assertTrue(ANIMATIONS["walk_left"].looping)
        for name in ("walk_right", "walk_left"):
            walk = ANIMATIONS[name]
            self.assertEqual(
                tuple(frame.sprite for frame in walk.frames),
                (ANIMATIONS["idle"].frames[0].sprite,) * 8,
            )
            self.assertEqual(
                tuple(frame.vertical_offset for frame in walk.frames),
                (0, -2, -5, -2, 0, -2, -5, -2),
            )

    def test_click_reactions_use_tactile_per_frame_timing(self) -> None:
        self.assertEqual(len(ANIMATIONS["squish"].frames), 9)
        self.assertEqual(
            ANIMATIONS["squish"].frames[0].sprite,
            "squish/squish_01.png",
        )
        self.assertEqual(ANIMATIONS["bounce"].frames, (ANIMATIONS["idle"].frames[0],))
        self.assertEqual(ANIMATIONS["squish"].frame_duration_ms, 125)
        self.assertFalse(ANIMATIONS["bounce"].looping)
        self.assertFalse(ANIMATIONS["squish"].looping)


if __name__ == "__main__":
    unittest.main()
