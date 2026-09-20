import hashlib
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
            "focus_start", "focus_loop", "focus_stop",
            "focus_thinking_start", "focus_thinking_loop", "focus_thinking_end",
            "watch", "dance", "searching", "drop", "side_eye", "table_flip",
            "wave", "vs_code", "mochi_exe", "level_up_default",
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
            (900, 600, 450, 1_100, 500, 1_400),
        )
        self.assertEqual(sum(frame.duration_ms or 0 for frame in idle.frames), 4950)
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

    def test_directional_drag_art_has_distinct_loaded_pixels(self) -> None:
        frames = ASSET_SET.load_frames("dragged")
        for left, right in (
            ("drag_left_soft", "drag_right_soft"),
            ("drag_left_medium", "drag_right_medium"),
            ("drag_settle_left", "drag_settle_right"),
        ):
            with self.subTest(pair=(left, right)):
                self.assertTrue(
                    bytes(frames[f"drag/{left}.png"].get_data())
                    != bytes(frames[f"drag/{right}.png"].get_data()),
                    f"{left} and {right} must display different artwork",
                )

    def test_soft_drag_assets_preserve_the_last_distinct_authored_pair(self) -> None:
        # Exact 256px files from d9d3db7, before 493788b duplicated the pair.
        # The 128px mochi_original_set drag files predate this hand-drawn art.
        expected = {
            "left": "30a84a149e456b801049d69e554bf98925f5933501df0c13fb440913e4372a27",
            "right": "232f7101dac99ccf3e90b410bf0661bc6b6bd442a4a9de0819470604b0a54a09",
        }
        for direction, digest in expected.items():
            path = ASSET_SET.root / f"drag/drag_{direction}_soft.png"
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

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

    def test_level_up_default_preserves_authored_64px_spritesheet(self) -> None:
        level_up = ANIMATIONS["level_up_default"]
        metadata = ASSET_SET.animations["level_up_default"]

        self.assertEqual(len(level_up.frames), 16)
        self.assertEqual(level_up.frame_duration_ms, 120)
        self.assertFalse(level_up.looping)
        self.assertEqual(metadata.spritesheet_path, "level_up_default/level_up_default.png")
        self.assertEqual(metadata.source_cell_size, (64, 64))

    def test_computer_emote_has_intro_typing_and_outro_phases(self) -> None:
        self.assertEqual(len(ANIMATIONS["computer_intro"].frames), 4)
        self.assertEqual(len(ANIMATIONS["computer_typing"].frames), 8)
        self.assertEqual(len(ANIMATIONS["computer_outro"].frames), 4)
        self.assertFalse(ANIMATIONS["computer_intro"].looping)
        self.assertTrue(ANIMATIONS["computer_typing"].looping)
        self.assertFalse(ANIMATIONS["computer_outro"].looping)

    def test_focus_animation_has_authored_start_loop_and_stop_phases(self) -> None:
        start = ANIMATIONS["focus_start"]
        loop = ANIMATIONS["focus_loop"]
        stop = ANIMATIONS["focus_stop"]

        self.assertEqual(len(start.frames), 4)
        self.assertEqual(start.frame_duration_ms, 120)
        self.assertFalse(start.looping)
        self.assertEqual(len(loop.frames), 24)
        self.assertEqual(loop.frame_duration_ms, 140)
        self.assertTrue(loop.looping)
        self.assertEqual(len(stop.frames), 4)
        self.assertEqual(stop.frame_duration_ms, 120)
        self.assertFalse(stop.looping)

    def test_focus_thinking_animation_has_start_loop_and_end_phases(self) -> None:
        start = ANIMATIONS["focus_thinking_start"]
        loop = ANIMATIONS["focus_thinking_loop"]
        end = ANIMATIONS["focus_thinking_end"]

        self.assertEqual(len(start.frames), 5)
        self.assertEqual(start.frame_duration_ms, 140)
        self.assertFalse(start.looping)
        self.assertEqual(len(loop.frames), 8)
        self.assertEqual(loop.frame_duration_ms, 140)
        self.assertTrue(loop.looping)
        self.assertEqual(len(end.frames), 5)
        self.assertEqual(end.frame_duration_ms, 140)
        self.assertFalse(end.looping)

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


def test_bond_idle_emotes_preserve_authored_timing() -> None:
    assert tuple(frame.duration_ms for frame in ANIMATIONS["side_eye"].frames) == (
        (120,) * 12 + (500,)
    )
    assert tuple(frame.duration_ms for frame in ANIMATIONS["table_flip"].frames) == (
        (120,) * 16
    )
    assert ANIMATIONS["side_eye"].looping is False
    assert ANIMATIONS["table_flip"].looping is False


def test_bond_idle_emotes_use_authored_64px_spritesheets() -> None:
    side_eye = ASSET_SET.animations["side_eye"]
    table_flip = ASSET_SET.animations["table_flip"]

    assert side_eye.spritesheet_path == "side_eye/side_eye.png"
    assert side_eye.source_cell_size == (64, 64)
    assert len(side_eye.frame_paths) == 13
    assert table_flip.spritesheet_path == "table_flip/table_flip.png"
    assert table_flip.source_cell_size == (64, 64)
    assert len(table_flip.frame_paths) == 16

def test_new_catalogue_emotes_preserve_authored_64px_spritesheets() -> None:
    expected = {
        "wave": ("wave/wave.png", 8, 120),
        "vs_code": ("vs_code/vs_code.png", 14, 240),
        "mochi_exe": ("mochi_exe/mochi_exe.png", 16, 120),
    }

    for animation_name, (sheet_path, frame_count, duration_ms) in expected.items():
        animation = ANIMATIONS[animation_name]
        metadata = ASSET_SET.animations[animation_name]

        assert len(animation.frames) == frame_count
        assert animation.frame_duration_ms == duration_ms
        assert animation.looping is False
        assert animation.next_state == "idle"
        assert metadata.spritesheet_path == sheet_path
        assert metadata.source_cell_size == (64, 64)
        assert len(metadata.frame_paths) == frame_count

