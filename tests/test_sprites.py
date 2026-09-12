import unittest

import cairo

from mochi.interaction_tuning import PICKUP_FRAME_DURATION_MS
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
                (surface.get_width(), surface.get_height()) == (256, 256)
                and surface.get_content() == cairo.CONTENT_COLOR_ALPHA
                for surface in atlas.frames.values()
            )
        )

    def test_required_visible_states_use_manifest_art(self) -> None:
        required = {
            "default", "idle", "blink", "walk", "walk_left", "bounce",
            "squish", "sleep", "sleeping", "wake", "dragged", "excited",
            "heart", "computer", "computer_intro", "computer_typing",
            "computer_outro", "typing_intro", "typing_loop", "typing_outro",
            "watch", "dance", "searching", "drop",
        }
        self.assertTrue(required.issubset(ANIMATIONS))

    def test_dance_is_an_eight_frame_loop(self) -> None:
        dance = ANIMATIONS["dance"]
        self.assertEqual(len(dance.frames), 8)
        self.assertTrue(dance.looping)

    def test_pickup_is_a_six_frame_one_shot(self) -> None:
        pickup = ANIMATIONS["pickup"]
        self.assertEqual(len(pickup.frames), 6)
        self.assertEqual(pickup.frame_duration_ms, PICKUP_FRAME_DURATION_MS)
        self.assertFalse(pickup.looping)

    def test_drop_is_a_quick_six_frame_one_shot(self) -> None:
        drop = ANIMATIONS["drop"]
        self.assertEqual(len(drop.frames), 6)
        self.assertLessEqual(
            len(drop.frames) * drop.frame_duration_ms,
            400,
        )
        self.assertFalse(drop.looping)

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
            (50, 55, 65, 85, 65, 55, 50),
        )
        self.assertEqual(sum(frame.duration_ms or 0 for frame in blink.frames), 425)
        self.assertFalse(blink.looping)

    def test_blink_starts_and_ends_on_the_same_authored_endpoint(self) -> None:
        surfaces = ASSET_SET.load_frames("blink")
        self.assertEqual(
            bytes(surfaces["blink/blink_01.png"].get_data()),
            bytes(surfaces["blink/blink_07.png"].get_data()),
        )

    def test_drag_uses_a_subtle_manifest_dangling_loop(self) -> None:
        dragged = ANIMATIONS["dragged"]
        self.assertEqual(len(dragged.frames), 8)
        self.assertEqual(dragged.frame_duration_ms, 167)
        self.assertTrue(dragged.looping)
        self.assertEqual(
            tuple(frame.sprite for frame in dragged.frames),
            (
                "drag/drag_neutral.png",
                "drag/drag_left_soft.png",
                "drag/drag_left_medium.png",
                "drag/drag_right_soft.png",
                "drag/drag_right_medium.png",
                "drag/drag_settle_left.png",
                "drag/drag_settle_right.png",
                "drag/drag_settle_neutral.png",
            ),
        )

    def test_walk_uses_the_manifest_directional_frames(self) -> None:
        self.assertTrue(ANIMATIONS["walk"].looping)
        self.assertTrue(ANIMATIONS["walk_left"].looping)
        self.assertEqual(
            tuple(frame.sprite for frame in ANIMATIONS["walk"].frames),
            tuple(f"walk/walk_{index:02}.png" for index in range(1, 9)),
        )
        self.assertEqual(
            tuple(frame.sprite for frame in ANIMATIONS["walk_left"].frames),
            tuple(
                f"walk_left/walk_left_{index:02}.png" for index in range(1, 9)
            ),
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

    def test_heart_is_a_single_manifest_backed_pass(self) -> None:
        heart = ANIMATIONS["heart"]
        self.assertEqual(len(heart.frames), 16)
        self.assertEqual(heart.frame_duration_ms, 120)
        self.assertFalse(heart.looping)

    def test_computer_emote_has_intro_typing_and_outro_phases(self) -> None:
        self.assertEqual(len(ANIMATIONS["computer_intro"].frames), 4)
        self.assertEqual(len(ANIMATIONS["computer_typing"].frames), 8)
        self.assertEqual(len(ANIMATIONS["computer_outro"].frames), 4)
        self.assertFalse(ANIMATIONS["computer_intro"].looping)
        self.assertTrue(ANIMATIONS["computer_typing"].looping)
        self.assertFalse(ANIMATIONS["computer_outro"].looping)

    def test_searching_emote_preserves_the_authored_twenty_frame_timing(self) -> None:
        searching = ANIMATIONS["searching"]
        self.assertEqual(len(searching.frames), 20)
        self.assertEqual(searching.frame_duration_ms, 120)
        self.assertTrue(searching.looping)
        self.assertEqual(
            tuple(frame.sprite for frame in searching.frames),
            tuple(f"searching/searching_{index:02}.png" for index in range(1, 21)),
        )

    def test_typing_transition_animations_surround_the_loop(self) -> None:
        self.assertEqual(len(ANIMATIONS["typing_intro"].frames), 5)
        self.assertFalse(ANIMATIONS["typing_intro"].looping)
        self.assertTrue(ANIMATIONS["typing_loop"].looping)
        self.assertEqual(len(ANIMATIONS["typing_outro"].frames), 3)
        self.assertFalse(ANIMATIONS["typing_outro"].looping)


if __name__ == "__main__":
    unittest.main()
