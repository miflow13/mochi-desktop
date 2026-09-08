import unittest

from mochi.drag_motion import DragMotionModel


def sampled(dx: float, dy: float, elapsed: float = 0.1) -> DragMotionModel:
    motion = DragMotionModel()
    motion.begin(0, 0, 0.0)
    motion.update(dx, dy, elapsed)
    return motion


class DragMotionModelTests(unittest.TestCase):
    def test_zero_and_tiny_velocity_are_neutral(self) -> None:
        self.assertEqual(sampled(0, 0).visual().pose, "neutral")
        self.assertEqual(sampled(2, 1).visual().pose, "neutral")

    def test_low_medium_and_high_velocity_select_distinct_strengths(self) -> None:
        self.assertEqual(sampled(20, 0).visual().pose, "move_right_gentle")
        self.assertEqual(sampled(60, 0).visual().pose, "move_right_medium")
        self.assertEqual(sampled(200, 0).visual().pose, "move_right_strong")

    def test_left_and_right_use_velocity_direction(self) -> None:
        self.assertEqual(sampled(-40, 0).visual().pose, "move_left_gentle")
        self.assertEqual(sampled(40, 0).visual().pose, "move_right_gentle")

    def test_vertical_motion_is_represented(self) -> None:
        self.assertEqual(sampled(0, -40).visual().pose, "move_up_gentle")
        self.assertEqual(sampled(0, 40).visual().pose, "move_down_gentle")
        self.assertEqual(sampled(0, -200).visual().pose, "move_up_strong")
        self.assertEqual(sampled(0, 200).visual().pose, "move_down_strong")

    def test_diagonal_motion_blends_both_axes(self) -> None:
        self.assertEqual(sampled(40, -40).visual().pose, "move_up_right_medium")
        self.assertEqual(sampled(-40, 40).visual().pose, "move_down_left_medium")
        self.assertEqual(sampled(200, -200).visual().pose, "move_up_right_strong")

    def test_velocity_vector_is_clamped(self) -> None:
        motion = sampled(10_000, 10_000, 0.01)
        self.assertLessEqual(
            (motion.filtered_velocity_x**2 + motion.filtered_velocity_y**2) ** 0.5,
            motion.max_velocity,
        )
        self.assertLessEqual(motion.speed, 1.0)

    def test_smoothing_rejects_a_single_direction_flip(self) -> None:
        motion = DragMotionModel()
        motion.begin(0, 0, 0.0)
        motion.update(40, 0, 0.05)
        motion.update(30, 0, 0.066)
        self.assertGreater(motion.filtered_velocity_x, 0)

    def test_settle_decays_to_neutral_and_reset_releases_neutral(self) -> None:
        motion = sampled(200, 0)
        before = motion.speed
        motion.settle(0.1)
        self.assertLess(motion.speed, before)
        for _ in range(10):
            motion.settle(0.1)
        self.assertEqual(motion.visual().pose, "neutral")
        motion.reset()
        self.assertEqual(motion.visual().pose, "neutral")


if __name__ == "__main__":
    unittest.main()
