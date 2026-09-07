import unittest

from mochi.animation import Animation, AnimationFrame, AnimationPlayer
from mochi.state import MochiState


class AnimationPlayerTests(unittest.TestCase):
    def test_non_looping_animation_finishes(self) -> None:
        finished: list[bool] = []
        state = [MochiState.BOUNCING]
        animation = Animation(
            "test", (AnimationFrame("first"), AnimationFrame("second")), 100
        )

        def finish_reaction(completed: Animation) -> None:
            finished.append(completed is animation)
            state[0] = MochiState.IDLE

        player = AnimationPlayer(finish_reaction)

        player.play(animation)
        self.assertFalse(player.tick(99))
        self.assertTrue(player.tick(1))
        self.assertEqual(player.frame, AnimationFrame("second"))
        self.assertTrue(player.tick(100))
        self.assertEqual(finished, [True])
        self.assertEqual(state[0], MochiState.IDLE)

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

    def test_animation_can_resume_at_a_saved_playhead(self) -> None:
        animation = Animation(
            "loop",
            (AnimationFrame("first"), AnimationFrame("second")),
            100,
            True,
        )
        player = AnimationPlayer()

        player.play(animation, frame_index=1, elapsed_ms=40)

        self.assertEqual(player.frame, AnimationFrame("second"))
        self.assertEqual(player.elapsed_ms, 40)
        self.assertFalse(player.tick(59))
        self.assertTrue(player.tick(1))
        self.assertEqual(player.frame, AnimationFrame("first"))

    def test_frame_duration_can_override_animation_default(self) -> None:
        animation = Animation(
            "varied",
            (
                AnimationFrame("brief", duration_ms=40),
                AnimationFrame("held", duration_ms=180),
                AnimationFrame("default"),
            ),
            100,
        )
        player = AnimationPlayer()
        player.play(animation)

        self.assertEqual(player.frame_duration_ms, 40)
        self.assertTrue(player.tick(40))
        self.assertEqual(player.frame_duration_ms, 180)
        self.assertFalse(player.tick(179))
        self.assertTrue(player.tick(1))
        self.assertEqual(player.frame_duration_ms, 100)

    def test_seek_progress_controls_looping_animation(self) -> None:
        animation = Animation(
            "walk",
            (
                AnimationFrame("first", duration_ms=100),
                AnimationFrame("second", duration_ms=200),
            ),
            100,
            looping=True,
        )
        player = AnimationPlayer()
        player.play(animation)

        self.assertTrue(player.seek_progress(0.5))
        self.assertEqual(player.frame, AnimationFrame("second", duration_ms=200))
        self.assertEqual(player.elapsed_ms, 50)
        self.assertTrue(player.seek_progress(1.0))
        self.assertEqual(player.frame, AnimationFrame("first", duration_ms=100))


if __name__ == "__main__":
    unittest.main()
