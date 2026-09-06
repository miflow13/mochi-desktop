import unittest

from mochi.animation import Animation, AnimationFrame, AnimationPlayer


class AnimationPlayerTests(unittest.TestCase):
    def test_non_looping_animation_finishes(self) -> None:
        finished: list[bool] = []
        animation = Animation(
            "test", (AnimationFrame("first"), AnimationFrame("second")), 100
        )
        player = AnimationPlayer(lambda: finished.append(True))

        player.play(animation)
        self.assertFalse(player.tick(99))
        self.assertTrue(player.tick(1))
        self.assertEqual(player.frame, AnimationFrame("second"))
        self.assertTrue(player.tick(100))
        self.assertEqual(finished, [True])

    def test_looping_animation_wraps(self) -> None:
        animation = Animation(
            "loop", (AnimationFrame("first"), AnimationFrame("second")), 50, True
        )
        player = AnimationPlayer()
        player.play(animation)

        player.tick(100)
        self.assertEqual(player.frame_index, 0)

    def test_stop_returns_to_default_frame(self) -> None:
        animation = Animation("loop", (AnimationFrame("only"),), 50, True)
        player = AnimationPlayer()
        player.play(animation)

        player.stop()

        self.assertIsNone(player.animation)
        self.assertIsNone(player.frame)


if __name__ == "__main__":
    unittest.main()
