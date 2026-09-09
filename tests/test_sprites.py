import unittest
from pathlib import Path

import cairo

from mochi.sprites import (
    ANIMATIONS,
    ASSET_SET,
    COMPUTER_IDLE_PHASES,
    PREVIEW_ANIMATION_NAMES,
    SpriteAtlas,
)


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
            "heart", "idle_typing",
            "put_down",
        }
        self.assertTrue(required.issubset(ANIMATIONS))

    def test_developer_preview_includes_every_runtime_animation(self) -> None:
        self.assertEqual(set(PREVIEW_ANIMATION_NAMES), set(ANIMATIONS))
        self.assertEqual(len(PREVIEW_ANIMATION_NAMES), len(ANIMATIONS))

    def test_sleep_transitions_to_sleeping(self) -> None:
        self.assertEqual(ANIMATIONS["sleep"].next_state, "sleeping")
        self.assertTrue(ANIMATIONS["sleeping"].looping)
        self.assertEqual(
            ANIMATIONS["sleeping"].frames,
            (ANIMATIONS["sleep"].frames[-1],),
        )
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["sleep"].frames),
            (90, 100, 120, 140, 160, 180),
        )
        self.assertEqual(
            tuple(frame.duration_ms for frame in ANIMATIONS["wake"].frames),
            (70, 80, 90, 100, 100, 90, 120),
        )
        self.assertEqual(
            ANIMATIONS["wake"].frames[-1].sprite,
            ANIMATIONS["idle"].frames[0].sprite,
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

    def test_drag_uses_the_supplied_looping_dangle_sequence(self) -> None:
        dragged = ANIMATIONS["dragged"]
        self.assertEqual(len(dragged.frames), 14)
        self.assertEqual(dragged.frame_duration_ms, 160)
        self.assertTrue(dragged.looping)
        surfaces = SpriteAtlas().frames
        drag_pixels = [bytes(surfaces[frame.sprite].get_data()) for frame in dragged.frames]
        self.assertEqual(len(set(drag_pixels)), 8)
        self.assertEqual(
            tuple(frame.sprite for frame in dragged.frames),
            tuple(frame.sprite for frame in dragged.frames[:8])
            + tuple(frame.sprite for frame in dragged.frames[6:0:-1]),
        )
        self.assertEqual(dragged.frames[-1].sprite, dragged.frames[1].sprite)

    def test_drag_frames_have_no_opaque_gray_matte_pixels(self) -> None:
        surfaces = SpriteAtlas().frames
        matte_pixels = 0
        for frame in ANIMATIONS["dragged"].frames:
            surface = surfaces[frame.sprite]
            for blue, green, red, alpha in zip(
                *[iter(bytes(surface.get_data()))] * 4, strict=True
            ):
                if alpha and (red, green, blue) == (127, 127, 126):
                    matte_pixels += 1
        self.assertEqual(matte_pixels, 0)

    def test_drag_frames_use_a_crisp_bounded_pixel_palette(self) -> None:
        surfaces = SpriteAtlas().frames
        for frame in ANIMATIONS["dragged"].frames:
            surface = surfaces[frame.sprite]
            colors = {
                (red, green, blue)
                for blue, green, red, alpha in zip(
                    *[iter(bytes(surface.get_data()))] * 4, strict=True
                )
                if alpha
            }
            self.assertLessEqual(
                len(colors),
                96,
                f"{frame.sprite} has gradient-like edge noise",
            )

    def test_drag_eyes_keep_idle_style_highlights(self) -> None:
        surfaces = SpriteAtlas().frames
        eye_boxes = (
            ((19, 39, 27, 47), (37, 39, 45, 47)),
            ((18, 36, 26, 44), (36, 36, 44, 44)),
            ((18, 32, 26, 40), (36, 32, 44, 40)),
            ((19, 32, 27, 40), (37, 32, 45, 40)),
            ((20, 33, 28, 41), (38, 33, 46, 41)),
            ((21, 32, 29, 40), (39, 32, 47, 40)),
            ((21, 31, 29, 39), (39, 31, 47, 39)),
            ((20, 32, 28, 40), (38, 32, 46, 40)),
        )
        for frame, boxes in zip(
            ANIMATIONS["dragged"].frames[:8], eye_boxes, strict=True
        ):
            surface = surfaces[frame.sprite]
            data = bytes(surface.get_data())
            stride = surface.get_stride()
            for left, top, right, bottom in boxes:
                highlights = 0
                for y in range(top * 2, bottom * 2):
                    for x in range(left * 2, right * 2):
                        offset = y * stride + x * 4
                        blue, green, red, alpha = data[offset : offset + 4]
                        if alpha and min(red, green, blue) >= 240:
                            highlights += 1
                self.assertGreater(highlights, 0)

    def test_new_emotes_are_one_shot_spritesheet_animations(self) -> None:
        heart = ANIMATIONS["heart"]
        self.assertEqual(len(heart.frames), 16)
        self.assertEqual(heart.frame_duration_ms, 120)
        self.assertFalse(heart.looping)

        computer = ANIMATIONS["idle_typing"]
        self.assertEqual(len(computer.frames), 16)
        self.assertEqual(computer.frame_duration_ms, 167)
        self.assertFalse(computer.looping)
        self.assertEqual(
            ASSET_SET.animations["idle_typing"].transparent_color,
            (126, 126, 125),
        )

    def test_computer_idle_uses_intro_loop_and_outro_slices(self) -> None:
        source = ANIMATIONS["idle_typing"].frames
        intro = COMPUTER_IDLE_PHASES["intro"]
        typing = COMPUTER_IDLE_PHASES["loop"]
        outro = COMPUTER_IDLE_PHASES["outro"]

        self.assertEqual(intro.frames, source[:4])
        self.assertEqual(typing.frames, source[4:12])
        self.assertEqual(outro.frames, source[12:])
        self.assertFalse(intro.looping)
        self.assertTrue(typing.looping)
        self.assertFalse(outro.looping)
        self.assertTrue(
            all(
                phase.frame_duration_ms == 167
                for phase in (intro, typing, outro)
            )
        )

    def test_heart_frames_have_transparent_backgrounds(self) -> None:
        surfaces = SpriteAtlas().frames
        for frame in ANIMATIONS["heart"].frames:
            data = bytes(surfaces[frame.sprite].get_data())
            alpha = data[3::4]
            self.assertIn(0, alpha)
            self.assertIn(255, alpha)

    def test_computer_frames_have_transparent_backgrounds(self) -> None:
        surfaces = SpriteAtlas().frames
        for frame in ANIMATIONS["idle_typing"].frames:
            data = bytes(surfaces[frame.sprite].get_data())
            alpha = data[3::4]
            self.assertIn(0, alpha)
            self.assertIn(255, alpha)

    def test_put_down_uses_supplied_one_shot_drop_sequence(self) -> None:
        put_down = ANIMATIONS["put_down"]

        self.assertNotIn("pickup", ANIMATIONS)
        self.assertEqual(len(put_down.frames), 8)
        self.assertEqual(put_down.frame_duration_ms, 120)
        self.assertFalse(put_down.looping)
        self.assertEqual(put_down.next_state, "idle")

        surfaces = SpriteAtlas().frames
        for frame in put_down.frames:
            alpha = bytes(surfaces[frame.sprite].get_data())[3::4]
            self.assertIn(0, alpha)
            self.assertIn(255, alpha)

    def test_drag_sequence_preserves_visual_mass(self) -> None:
        surfaces = SpriteAtlas().frames
        idle_surface = surfaces[ANIMATIONS["idle"].frames[0].sprite]
        idle_area = sum(bytes(idle_surface.get_data())[3::4]) / 255
        minimum_area = idle_area * 0.85

        for name in ("dragged", "put_down"):
            for frame in ANIMATIONS[name].frames:
                surface = surfaces[frame.sprite]
                visible_area = sum(bytes(surface.get_data())[3::4]) / 255
                self.assertGreaterEqual(
                    visible_area,
                    minimum_area,
                    f"{frame.sprite} visually shrinks below the pickup/held baseline",
                )

    def test_every_runtime_frame_has_hard_transparency_and_clear_corners(self) -> None:
        surfaces = SpriteAtlas().frames
        for path, surface in surfaces.items():
            data = bytes(surface.get_data())
            self.assertTrue(
                set(data[3::4]).issubset({0, 255}),
                f"{path} contains softened alpha pixels",
            )
            stride = surface.get_stride()
            corner_offsets = (
                3,
                (surface.get_width() - 1) * 4 + 3,
                (surface.get_height() - 1) * stride + 3,
                (surface.get_height() - 1) * stride
                + (surface.get_width() - 1) * 4
                + 3,
            )
            self.assertTrue(
                all(data[offset] == 0 for offset in corner_offsets),
                f"{path} has an opaque canvas corner",
            )
            left_edge = (data[y * stride + 3] for y in range(surface.get_height()))
            right_edge = (
                data[y * stride + (surface.get_width() - 1) * 4 + 3]
                for y in range(surface.get_height())
            )
            if not path.startswith("put_down/"):
                self.assertTrue(
                    all(alpha == 0 for alpha in (*left_edge, *right_edge)),
                    f"{path} has background pixels reaching a canvas side",
                )

    def test_every_runtime_frame_uses_the_canonical_two_by_two_pixel_grid(self) -> None:
        surfaces = SpriteAtlas().frames
        for path, surface in surfaces.items():
            data = bytes(surface.get_data())
            stride = surface.get_stride()
            for y in range(0, 128, 2):
                for x in range(0, 128, 2):
                    pixels = {
                        data[(y + dy) * stride + (x + dx) * 4 :
                             (y + dy) * stride + (x + dx + 1) * 4]
                        for dy in (0, 1)
                        for dx in (0, 1)
                    }
                    self.assertEqual(
                        len(pixels),
                        1,
                        f"{path} contains noncanonical subpixel detail at {x},{y}",
                    )

    def test_character_animation_frames_use_a_bounded_pixel_palette(self) -> None:
        surfaces = SpriteAtlas().frames
        for name in ("blink", "bounce", "sleep", "sleeping", "wake"):
            for frame in ANIMATIONS[name].frames:
                data = bytes(surfaces[frame.sprite].get_data())
                colors = {
                    tuple(data[offset : offset + 3])
                    for offset in range(0, len(data), 4)
                    if data[offset + 3]
                }
                self.assertLessEqual(
                    len(colors),
                    64,
                    f"{frame.sprite} contains antialiased palette drift",
                )

    def test_archived_animation_tree_is_not_kept_in_the_runtime_project(self) -> None:
        legacy_root = Path(ASSET_SET.root).parent / "mochi_original_set"
        self.assertFalse(legacy_root.exists())

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
            (45, 55, 65, 75, 90, 85, 75, 65, 55),
        )
        self.assertFalse(ANIMATIONS["bounce"].looping)
        self.assertFalse(ANIMATIONS["squish"].looping)


if __name__ == "__main__":
    unittest.main()
