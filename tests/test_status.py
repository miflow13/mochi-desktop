import unittest

from mochi.state import MochiState
from mochi.status import (
    ContextActionDispatcher, NameplateMode, NameplateState, choose_plate_placement,
    friendly_state_label, sleep_action_label,
)


class NameplateStateTests(unittest.TestCase):
    def test_plate_leave_cannot_clear_an_active_buddy_hover(self) -> None:
        plate = NameplateState()
        plate.anchor_enter()
        plate.plate_leave()
        self.assertTrue(plate.hovered)
        self.assertIs(plate.mode, NameplateMode.COMPACT)

    def test_hover_progresses_from_compact_to_hover(self) -> None:
        plate = NameplateState()
        self.assertIs(plate.anchor_enter(), NameplateMode.COMPACT)
        self.assertIs(plate.expand_hover(), NameplateMode.HOVER)
        plate.anchor_leave()
        self.assertIs(plate.close(), NameplateMode.HIDDEN)

    def test_context_is_pinned_and_click_away_closes_it(self) -> None:
        plate = NameplateState()
        plate.open_context()
        generation = plate.generation
        self.assertFalse(plate.can_hide(generation))
        self.assertIs(plate.close(), NameplateMode.HIDDEN)

    def test_context_action_cleanup_forces_hidden_even_while_plate_hovered(self) -> None:
        plate = NameplateState()
        plate.plate_enter()
        plate.open_context()

        self.assertIs(plate.close_context(), NameplateMode.HIDDEN)
        self.assertIs(plate.close_context(), NameplateMode.HIDDEN)
        self.assertFalse(plate.hovered)

    def test_context_cleanup_precedes_behavior_dispatch(self) -> None:
        events = []
        dispatcher = ContextActionDispatcher()

        dispatcher.begin(
            lambda: events.append("closed"),
            lambda: events.append("walk"),
        )

        self.assertEqual(events, ["closed"])
        self.assertTrue(dispatcher.pending)
        dispatcher.complete()
        self.assertEqual(events, ["closed", "walk"])
        self.assertFalse(dispatcher.pending)

    def test_context_cleanup_survives_behavior_failure(self) -> None:
        events = []
        dispatcher = ContextActionDispatcher()

        dispatcher.begin(
            lambda: events.append("closed"),
            lambda: (_ for _ in ()).throw(RuntimeError("walk failed")),
        )

        with self.assertRaisesRegex(RuntimeError, "walk failed"):
            dispatcher.complete()

        self.assertEqual(events, ["closed"])
        self.assertFalse(dispatcher.pending)

    def test_drag_always_hides_context(self) -> None:
        plate = NameplateState(anchor_hovered=True)
        plate.open_context()
        self.assertIs(plate.begin_drag(), NameplateMode.HIDDEN)
        self.assertFalse(plate.hovered)

    def test_context_action_matches_sleep_state(self) -> None:
        self.assertEqual(sleep_action_label(MochiState.IDLE), "Sleep")
        self.assertEqual(sleep_action_label(MochiState.SLEEPING), "Wake")

    def test_friendly_labels_hide_internal_terminology(self) -> None:
        self.assertEqual(friendly_state_label(MochiState.DRAGGED), "Picked up")
        self.assertEqual(friendly_state_label(MochiState.WAKING), "Waking up…")

    def test_edge_placement_flips_and_clamps_without_using_sprite_bounds(self) -> None:
        above = choose_plate_placement(400, 128, 180, 0, 800, 100, 20, 80)
        self.assertEqual(above.side, "above")
        left = choose_plate_placement(0, 128, 180, 0, 800, 10, 100, 80)
        self.assertEqual(left.side, "below")
        self.assertGreater(left.offset_x, 0)
        right = choose_plate_placement(750, 128, 180, 0, 800, 100, 20, 80)
        self.assertLess(right.offset_x, 0)


if __name__ == "__main__":
    unittest.main()
