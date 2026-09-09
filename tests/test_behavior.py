import random
import unittest

from mochi.behavior import (
    ClickReactionBuffer,
    WalkMotion,
    can_begin_sleep,
    can_begin_wake,
    can_transition,
    can_queue_click_reaction,
    can_start_click_reaction,
    choose_click_reaction,
    choose_walk_animation,
)
from mochi.state import MochiState


class ClickReactionTests(unittest.TestCase):
    def test_click_reaction_state_restrictions(self) -> None:
        self.assertTrue(can_start_click_reaction(MochiState.IDLE))
        self.assertFalse(can_start_click_reaction(MochiState.SLEEPING))
        self.assertFalse(can_start_click_reaction(MochiState.WALKING))
        self.assertTrue(can_queue_click_reaction(MochiState.BOUNCING))
        self.assertTrue(can_queue_click_reaction(MochiState.SQUISHING))
        self.assertFalse(can_queue_click_reaction(MochiState.SLEEPING))

    def test_sleep_and_wake_transition_state_restrictions(self) -> None:
        self.assertTrue(can_begin_sleep(MochiState.IDLE))
        self.assertTrue(can_begin_sleep(MochiState.WALKING))
        self.assertFalse(can_begin_sleep(MochiState.SLEEPING))
        self.assertFalse(can_begin_sleep(MochiState.WAKING))
        self.assertTrue(can_begin_wake(MochiState.SLEEPING))
        self.assertFalse(can_begin_wake(MochiState.WAKING))
        self.assertFalse(can_begin_wake(MochiState.IDLE))

    def test_transition_policy_prioritizes_user_and_major_states(self) -> None:
        self.assertFalse(can_transition(MochiState.WALKING, MochiState.BLINKING))
        self.assertTrue(can_transition(MochiState.WALKING, MochiState.BOUNCING))
        self.assertTrue(can_transition(MochiState.WALKING, MochiState.SLEEPING))
        self.assertFalse(can_transition(MochiState.DRAGGED, MochiState.SLEEPING))
        self.assertFalse(can_transition(MochiState.WAKING, MochiState.BOUNCING))
        self.assertTrue(can_transition(MochiState.SLEEPING, MochiState.WAKING))
        self.assertTrue(can_transition(MochiState.IDLE, MochiState.PICKUP))
        self.assertTrue(can_transition(MochiState.PICKUP, MochiState.DRAGGED))
        self.assertFalse(can_transition(MochiState.PICKUP, MochiState.BLINKING))

    def test_rapid_clicks_queue_at_most_one_follow_up(self) -> None:
        buffer = ClickReactionBuffer()

        self.assertTrue(buffer.request(MochiState.IDLE))
        self.assertFalse(buffer.request(MochiState.BOUNCING))
        self.assertFalse(buffer.request(MochiState.SQUISHING))
        self.assertTrue(buffer.consume())
        self.assertFalse(buffer.consume())
        self.assertFalse(buffer.request(MochiState.SLEEPING))

    def test_walk_direction_matches_horizontal_motion(self) -> None:
        self.assertEqual(choose_walk_animation((100, 20), (40, 25)), "walk_left")
        self.assertEqual(choose_walk_animation((40, 20), (100, 25)), "walk")

    def test_walk_motion_uses_distance_and_smooth_endpoints(self) -> None:
        motion = WalkMotion((0, 0), (144, 0), cycle_duration_ms=1_000)

        self.assertEqual(motion.distance, 144)
        self.assertEqual(motion.pixels_per_cycle, 72.0)
        self.assertEqual(motion.cycles, 2)
        self.assertEqual(motion.duration_ms, 2_000)
        self.assertEqual(motion.position_at(0), (0, 0))
        self.assertEqual(motion.position_at(2_000), (144, 0))
        self.assertLess(motion.position_at(100)[0], 10)
        self.assertGreater(motion.position_at(1_900)[0], 134)
        self.assertEqual(motion.animation_progress(2_000), 0.0)

    def test_default_weight_is_about_fifty_five_percent_bounce(self) -> None:
        rng = random.Random(42)
        results = [choose_click_reaction(rng=rng).name for _ in range(10_000)]
        self.assertAlmostEqual(results.count("bounce") / len(results), 0.55, delta=0.02)
        self.assertEqual(set(results), {"bounce", "squish"})

    def test_two_repeats_favor_the_other_reaction(self) -> None:
        bounce_rng = random.Random(42)
        after_bounces = [
            choose_click_reaction(("bounce", "bounce"), bounce_rng).name
            for _ in range(10_000)
        ]
        squish_rng = random.Random(42)
        after_squishes = [
            choose_click_reaction(("squish", "squish"), squish_rng).name
            for _ in range(10_000)
        ]
        self.assertAlmostEqual(after_bounces.count("bounce") / 10_000, 0.40, delta=0.02)
        self.assertAlmostEqual(after_squishes.count("bounce") / 10_000, 0.60, delta=0.02)


if __name__ == "__main__":
    unittest.main()
