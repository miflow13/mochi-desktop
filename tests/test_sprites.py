import unittest

import cairo

from mochi.sprites import ANIMATIONS, FRAME_RECTANGLES, SpriteAtlas


class SpriteDefinitionsTests(unittest.TestCase):
    def test_every_rectangle_fits_inside_source_sheet(self) -> None:
        sheet_width, sheet_height = SpriteAtlas.SOURCE_SIZE
        for name, rectangle in FRAME_RECTANGLES.items():
            with self.subTest(name=name):
                self.assertGreater(rectangle.width, 0)
                self.assertGreater(rectangle.height, 0)
                self.assertLessEqual(rectangle.x + rectangle.width, sheet_width)
                self.assertLessEqual(rectangle.y + rectangle.height, sheet_height)

    def test_every_animation_references_a_known_frame(self) -> None:
        for animation in ANIMATIONS.values():
            for frame in animation.frames:
                with self.subTest(animation=animation.name, frame=frame.sprite):
                    self.assertIn(frame.sprite, FRAME_RECTANGLES)

    def test_atlas_loads_and_caches_every_rgba_crop(self) -> None:
        atlas = SpriteAtlas()

        self.assertEqual(set(atlas.frames), set(FRAME_RECTANGLES))
        self.assertTrue(
            all(frame.get_content() == cairo.CONTENT_COLOR_ALPHA for frame in atlas.frames.values())
        )


if __name__ == "__main__":
    unittest.main()
