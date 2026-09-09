import unittest

from mochi.drag_motion import DragMotionModel


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

    def test_visual_offset_trails_fast_motion_but_stays_subtle(self) -> None:
        motion = DragMotionModel()
        motion.begin(0, 0, 0.0)
        motion.update(100, 50, 0.1)

        self.assertLess(motion.visual_offset_x, 0)
        self.assertLess(motion.visual_offset_y, 0)
        self.assertLessEqual(abs(motion.visual_offset_x), 6)
        self.assertLessEqual(abs(motion.visual_offset_y), 6)

    def test_visual_offset_settles_quickly_without_oscillation(self) -> None:
        motion = DragMotionModel()
        motion.begin(0, 0, 0.0)
        motion.update(100, 0, 0.1)
        offsets = []
        for index in range(1, 16):
            motion.update(100, 0, 0.1 + index * 0.016)
            offsets.append(abs(motion.visual_offset_x))

        self.assertEqual(offsets, sorted(offsets, reverse=True))
        self.assertLess(offsets[-1], 0.1)


if __name__ == "__main__":
    unittest.main()
