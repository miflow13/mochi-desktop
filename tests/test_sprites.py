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
            "default", "idle", "blink", "walk", "walk_left", "bounce",
            "squish", "sleep", "sleeping", "wake", "dragged", "excited",
        }
        self.assertTrue(required.issubset(ANIMATIONS))

    def test_sleep_transitions_to_sleeping(self) -> None:
        self.assertEqual(ANIMATIONS["sleep"].next_state, "sleeping")
        self.assertTrue(ANIMATIONS["sleeping"].looping)
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["sleep"].frames),
            (90, 100, 120, 140, 160, 180),
        )
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["wake"].frames),
            (70, 80, 90, 100, 100, 90),
        )

    def test_idle_breathing_uses_slow_per_frame_timing(self) -> None:
        idle = ANIMATIONS["idle"]
        self.assertEqual(len(idle.frames), 6)
        self.assertEqual(
            tuple(frame.duration_ms for frame in idle.frames),
            (750, 500, 350, 900, 400, 1_000),
        )
        self.assertEqual(sum(frame.duration_ms or 0 for frame in idle.frames), 3900)
        self.assertTrue(idle.looping)

    def test_blink_uses_fast_per_frame_timing(self) -> None:
        blink = ANIMATIONS["blink"]
        self.assertEqual(
            tuple(frame.duration_ms for frame in blink.frames),
            (90, 90, 120, 90),
        )
        self.assertEqual(sum(frame.duration_ms or 0 for frame in blink.frames), 390)
        self.assertFalse(blink.looping)

    def test_drag_uses_a_subtle_manifest_dangling_loop(self) -> None:
        dragged = ANIMATIONS["dragged"]
        self.assertEqual(len(dragged.frames), 8)
        self.assertEqual(dragged.frame_duration_ms, 167)
        self.assertTrue(dragged.looping)
        surfaces = SpriteAtlas().frames
        drag_pixels = [bytes(surfaces[frame.sprite].get_data()) for frame in dragged.frames]
        self.assertEqual(len(set(drag_pixels)), 8)

    def test_walk_uses_a_slow_looping_bounce_prototype(self) -> None:
        self.assertTrue(ANIMATIONS["walk"].looping)
        self.assertTrue(ANIMATIONS["walk_left"].looping)
        self.assertEqual(
            tuple(frame.sprite for frame in ANIMATIONS["walk"].frames),
            tuple(frame.sprite for frame in ANIMATIONS["bounce"].frames),
        )
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["walk"].frames),
            (80, 110, 125, 135, 180, 170, 130),
        )

    def test_click_reactions_use_tactile_per_frame_timing(self) -> None:
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["bounce"].frames),
            (50, 75, 85, 95, 135, 145, 110),
        )
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["squish"].frames),
            (45, 70, 105, 120, 145, 125),
        )
        self.assertFalse(ANIMATIONS["bounce"].looping)
        self.assertFalse(ANIMATIONS["squish"].looping)


if __name__ == "__main__":
    unittest.main()
