import unittest

from mochi.drag_motion import DragMotionModel, DragPoseSelector, drag_settle_sprite
from mochi.interaction_tuning import (
    DRAG_HEAVY_VELOCITY_PX_PER_SECOND,
    DRAG_MEDIUM_ENTER_THRESHOLD,
    DRAG_MEDIUM_EXIT_THRESHOLD,
    DRAG_SOFT_ENTER_THRESHOLD,
)


class DragMotionModelTests(unittest.TestCase):
    def test_first_sample_is_neutral(self) -> None:
        motion = DragMotionModel()
        motion.begin(0, 0, 0.0)
        self.assertEqual(motion.filtered_velocity_x, 0.0)
        self.assertEqual(motion.leg_sway, 0.0)

    def test_rightward_motion_moves_legs_opposite_direction(self) -> None:
        motion = DragMotionModel()
        motion.begin(0, 0, 0.0)
        motion.update(100, 0, 0.1)
        self.assertLess(motion.leg_sway, 0.0)

    def test_leftward_motion_moves_legs_opposite_direction(self) -> None:
        motion = DragMotionModel()
        motion.begin(100, 0, 0.0)
        motion.update(0, 0, 0.1)
        self.assertGreater(motion.leg_sway, 0.0)

    def test_faster_motion_has_stronger_sway_until_clamped(self) -> None:
        slow = DragMotionModel()
        fast = DragMotionModel()
        slow.begin(0, 0, 0.0)
        fast.begin(0, 0, 0.0)
        slow.update(20, 0, 0.1)
        fast.update(100, 0, 0.1)
        self.assertGreater(abs(fast.leg_sway), abs(slow.leg_sway))
        self.assertLessEqual(abs(fast.leg_sway), 1.0)
        self.assertLess(fast.body_sway, 0.0)

    def test_settle_reduces_sway_and_reset_clears_state(self) -> None:
        motion = DragMotionModel()
        motion.begin(0, 0, 0.0)
        motion.update(100, 0, 0.1)
        before = abs(motion.leg_sway)
        motion.settle()
        self.assertLess(abs(motion.leg_sway), before)
        motion.reset()
        self.assertEqual(motion.leg_sway, 0.0)
        motion.update(100, 0, 0.2)
        self.assertEqual(motion.leg_sway, 0.0)

    def test_drag_pose_uses_the_remaining_soft_and_medium_frames(self) -> None:
        selector = DragPoseSelector()
        self.assertEqual(selector.select(0.0, 0.0), "drag/drag_neutral.png")
        self.assertEqual(selector.select(0.2, 0.1), "drag/drag_left_soft.png")
        self.assertEqual(selector.select(1.0, 0.2), "drag/drag_left_medium.png")
        selector.reset()
        self.assertEqual(selector.select(-0.2, 0.3), "drag/drag_right_soft.png")
        self.assertEqual(selector.select(-1.0, 0.4), "drag/drag_right_medium.png")

    def test_drag_pose_threshold_boundaries_are_explicit(self) -> None:
        self.assertEqual(
            DragPoseSelector().select(DRAG_SOFT_ENTER_THRESHOLD - 0.001, 0.0),
            "drag/drag_neutral.png",
        )
        self.assertEqual(
            DragPoseSelector().select(DRAG_SOFT_ENTER_THRESHOLD, 0.0),
            "drag/drag_left_soft.png",
        )
        self.assertEqual(
            DragPoseSelector().select(DRAG_MEDIUM_ENTER_THRESHOLD, 0.0),
            "drag/drag_left_medium.png",
        )
        self.assertEqual(
            DragMotionModel().max_velocity,
            DRAG_HEAVY_VELOCITY_PX_PER_SECOND,
        )

    def test_medium_pose_uses_hysteresis_instead_of_fighting_near_boundary(self) -> None:
        selector = DragPoseSelector()

        self.assertIn("soft", selector.select(0.27, 0.0))
        self.assertIn("medium", selector.select(DRAG_MEDIUM_ENTER_THRESHOLD, 0.1))
        self.assertIn("medium", selector.select(0.25, 0.2))
        self.assertIn("medium", selector.select(DRAG_MEDIUM_EXIT_THRESHOLD, 0.3))
        self.assertIn("soft", selector.select(DRAG_MEDIUM_EXIT_THRESHOLD - 0.01, 0.4))

    def test_optional_drag_dwell_delays_only_soft_medium_changes(self) -> None:
        selector = DragPoseSelector(dwell_ms=100)

        self.assertIn("soft", selector.select(0.2, 0.0))
        self.assertIn("soft", selector.select(0.5, 0.05))
        self.assertIn("medium", selector.select(0.5, 0.11))

    def test_drag_release_selects_a_valid_directional_settle_frame(self) -> None:
        self.assertEqual(
            drag_settle_sprite("drag/drag_left_medium.png"),
            "drag/drag_settle_left.png",
        )
        self.assertEqual(
            drag_settle_sprite("drag/drag_right_soft.png"),
            "drag/drag_settle_right.png",
        )
        self.assertEqual(
            drag_settle_sprite("drag/drag_neutral.png"),
            "drag/drag_settle_neutral.png",
        )


if __name__ == "__main__":
    unittest.main()
