import unittest

import cairo

from mochi.animation import AnimationPlayer
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
        self.assertEqual(len(dragged.frames), 10)
        self.assertEqual(dragged.frame_duration_ms, 167)
        self.assertTrue(dragged.looping)
        surfaces = SpriteAtlas().frames
        drag_pixels = [bytes(surfaces[frame.sprite].get_data()) for frame in dragged.frames]
        self.assertGreaterEqual(len(set(drag_pixels)), 9)

    def test_pickup_is_a_six_frame_one_shot_into_stable_drag(self) -> None:
        pickup = ANIMATIONS["pickup"]
        self.assertEqual(len(pickup.frames), 6)
        self.assertEqual(pickup.frame_duration_ms, 120)
        self.assertEqual(sum(frame.duration_ms or 120 for frame in pickup.frames), 720)
        self.assertFalse(pickup.looping)
        self.assertEqual(pickup.next_state, "dragged")

        surfaces = SpriteAtlas().frames
        self.assertEqual(len({bytes(surfaces[frame.sprite].get_data()) for frame in pickup.frames}), 6)
        for frame in pickup.frames:
            data = bytes(surfaces[frame.sprite].get_data())
            alpha = data[3::4]
            self.assertTrue(set(alpha).issubset({0, 255}))
            self.assertIn(0, alpha)
            self.assertIn(255, alpha)
            self.assertFalse(
                any(
                    opaque == 255 and (red, green, blue) == (127, 127, 126)
                    for blue, green, red, opaque in zip(
                        *[iter(data)] * 4, strict=True
                    )
                )
            )

    def test_pickup_completion_fires_once_and_quick_release_cancels_it(self) -> None:
        pickup = ANIMATIONS["pickup"]
        for release_after_ms in (0, 360, 600):
            completions = []
            player = AnimationPlayer(on_finished=completions.append)
            player.play(pickup)
            player.tick(release_after_ms)
            player.play(ANIMATIONS["idle"])
            player.tick(1_000)
            self.assertEqual(completions, [])

        completions = []
        player = AnimationPlayer(on_finished=completions.append)
        player.play(pickup)
        player.tick(720)
        player.tick(720)
        self.assertEqual(completions, [pickup])

    def test_repeated_pickup_interruptions_do_not_accumulate_callbacks(self) -> None:
        completions = []
        player = AnimationPlayer(on_finished=completions.append)
        for _ in range(100):
            player.play(ANIMATIONS["pickup"])
            player.tick(240)
            player.play(ANIMATIONS["idle"])
        self.assertEqual(completions, [])

    def test_put_down_is_the_seven_frame_plop_handoff(self) -> None:
        put_down = ANIMATIONS["put_down"]
        self.assertEqual(len(put_down.frames), 7)
        self.assertEqual(put_down.frame_duration_ms, 120)
        self.assertEqual(sum(frame.duration_ms or 120 for frame in put_down.frames), 840)
        self.assertFalse(put_down.looping)
        self.assertEqual(put_down.next_state, "idle")

        surfaces = SpriteAtlas().frames
        self.assertEqual(
            len({bytes(surfaces[frame.sprite].get_data()) for frame in put_down.frames}),
            7,
        )
        for frame in put_down.frames:
            data = bytes(surfaces[frame.sprite].get_data())
            alpha = data[3::4]
            self.assertTrue(set(alpha).issubset({0, 255}))
            self.assertIn(0, alpha)
            self.assertIn(255, alpha)
            self.assertFalse(
                any(
                    opaque == 255 and (red, green, blue) == (127, 127, 126)
                    for blue, green, red, opaque in zip(
                        *[iter(data)] * 4, strict=True
                    )
                )
            )

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
