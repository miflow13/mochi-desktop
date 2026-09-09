import random
import unittest

from mochi.behavior import (
    ClickGestureRouter,
    ClickReactionBuffer,
    DragReleaseLatch,
    OwnedTimer,
    SourceRegistry,
    WalkMotion,
    can_begin_sleep,
    can_begin_wake,
    can_start_heart,
    can_start_typing,
    can_transition,
    can_queue_click_reaction,
    can_start_click_reaction,
    choose_click_reaction,
    choose_computer_emote_duration_ms,
    choose_computer_idle_delay_ms,
    choose_emote,
    choose_walk_animation,
)
from mochi.state import MochiState


class ClickReactionTests(unittest.TestCase):
    def test_double_click_cancels_the_pending_single_click(self) -> None:
        callbacks = {}
        removed = []
        events = []

        def add(_delay, callback):
            callbacks[1] = callback
            return 1

        router = ClickGestureRouter(
            OwnedTimer(add, removed.append),
            lambda: events.append("single"),
            lambda: events.append("heart"),
            250,
        )
        router.release(1)
        router.press(2)
        router.release(2)

        self.assertEqual(events, ["heart"])
        self.assertEqual(removed, [1])

    def test_owned_timer_replaces_sources_without_accumulating(self) -> None:
        added = []
        removed = []

        def add(delay, callback):
            added.append((delay, callback))
            return len(added)

        timer = OwnedTimer(add, removed.append)
        timer.schedule(1_000, lambda: False)
        timer.schedule(2_000, lambda: False)

        self.assertEqual([delay for delay, _callback in added], [1_000, 2_000])
        self.assertEqual(removed, [1])
        self.assertEqual(timer.source_id, 2)

    def test_source_registry_cancels_only_live_recurring_sources(self) -> None:
        callbacks = {}
        removed = []

        def add(_delay, callback):
            source_id = len(callbacks) + 1
            callbacks[source_id] = callback
            return source_id

        sources = SourceRegistry(removed.append)
        recurring = sources.schedule(add, 16, lambda: True)
        completed = sources.schedule(add, 100, lambda: False)

        self.assertFalse(callbacks[completed]())
        sources.cancel_all()
        sources.cancel_all()

        self.assertEqual(recurring, 1)
        self.assertEqual(removed, [recurring])
        self.assertEqual(sources.count, 0)

    def test_source_registry_tracks_a_source_scheduled_by_a_callback(self) -> None:
        callbacks = {}
        removed = []

        def add(_delay, callback):
            source_id = len(callbacks) + 1
            callbacks[source_id] = callback
            return source_id

        sources = SourceRegistry(removed.append)

        def replace_self() -> bool:
            sources.schedule(add, 100, lambda: False)
            return False

        first = sources.schedule(add, 100, replace_self)
        callbacks[first]()
        sources.cancel_all()

        self.assertEqual(removed, [2])
        self.assertEqual(sources.count, 0)

    def test_drag_release_latch_handles_gesture_end_before_click_release(self) -> None:
        drag = DragReleaseLatch()
        drag.begin()

        self.assertTrue(drag.gesture_end())
        self.assertTrue(drag.click_release_consumed())
        self.assertFalse(drag.active)
        self.assertFalse(drag.click_release_consumed())

    def test_drag_release_latch_handles_click_release_without_gesture_end(self) -> None:
        drag = DragReleaseLatch()
        drag.begin()

        self.assertTrue(drag.click_release_consumed())
        self.assertFalse(drag.active)
        self.assertFalse(drag.gesture_end())

    def test_heart_and_typing_state_eligibility(self) -> None:
        self.assertTrue(can_start_heart(MochiState.IDLE))
        self.assertTrue(can_start_heart(MochiState.TYPING))
        self.assertFalse(can_start_heart(MochiState.DRAGGED))
        self.assertFalse(can_start_heart(MochiState.SLEEPING))
        self.assertTrue(can_start_typing(MochiState.IDLE))
        self.assertFalse(can_start_typing(MochiState.WALKING))
        self.assertFalse(can_start_typing(MochiState.DRAGGED))
        self.assertTrue(can_transition(MochiState.DRAGGED, MochiState.IDLE))

    def test_context_emote_uses_only_existing_emote_animations(self) -> None:
        rng = random.Random(42)
        choices = {choose_emote(rng) for _ in range(500)}
        self.assertEqual(
            choices,
            {"bounce", "squish", "excited", "heart", "idle_typing"},
        )

    def test_computer_emote_duration_is_randomized_within_three_to_four_seconds(self) -> None:
        rng = random.Random(42)
        durations = {choose_computer_emote_duration_ms(rng) for _ in range(500)}
        self.assertTrue(all(3_000 <= duration <= 4_000 for duration in durations))
        self.assertGreater(len(durations), 1)

    def test_computer_idle_delay_is_randomized_within_45_to_120_seconds(self) -> None:
        rng = random.Random(42)
        delays = {choose_computer_idle_delay_ms(rng) for _ in range(500)}
        self.assertTrue(all(45_000 <= delay <= 120_000 for delay in delays))
        self.assertGreater(len(delays), 1)

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
        self.assertFalse(can_begin_sleep(MochiState.FALLING_ASLEEP))
        self.assertFalse(can_begin_sleep(MochiState.SLEEPING))
        self.assertFalse(can_begin_sleep(MochiState.WAKING))
        self.assertTrue(can_begin_wake(MochiState.SLEEPING))
        self.assertFalse(can_begin_wake(MochiState.WAKING))
        self.assertFalse(can_begin_wake(MochiState.IDLE))

    def test_transition_policy_prioritizes_user_and_major_states(self) -> None:
        self.assertFalse(can_transition(MochiState.WALKING, MochiState.BLINKING))
        self.assertTrue(can_transition(MochiState.WALKING, MochiState.BOUNCING))
        self.assertTrue(
            can_transition(MochiState.WALKING, MochiState.FALLING_ASLEEP)
        )
        self.assertTrue(
            can_transition(MochiState.TYPING, MochiState.FALLING_ASLEEP)
        )
        self.assertFalse(
            can_transition(MochiState.FALLING_ASLEEP, MochiState.HEART)
        )
        self.assertTrue(
            can_transition(MochiState.FALLING_ASLEEP, MochiState.SLEEPING)
        )
        self.assertTrue(
            can_transition(MochiState.FALLING_ASLEEP, MochiState.DRAGGED)
        )
        self.assertFalse(can_transition(MochiState.DRAGGED, MochiState.SLEEPING))
        self.assertFalse(can_transition(MochiState.WAKING, MochiState.BOUNCING))
        self.assertTrue(can_transition(MochiState.SLEEPING, MochiState.WAKING))

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
