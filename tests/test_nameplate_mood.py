"""Regression coverage for wiring MoodModel into accepted Mochi transitions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from mochi.mood import MoodModel
from mochi.presence.nameplate_controls import NameplateMixin
from mochi.state import MochiState


class _TransitionBase:
    def _transition_to(self, next_state: MochiState) -> bool:
        if self.reject_transition:
            return False
        self.state.current = next_state
        return True


class _MoodHarness(NameplateMixin, _TransitionBase):
    pass


def _make_harness() -> _MoodHarness:
    harness = object.__new__(_MoodHarness)
    harness._mood_model = MoodModel()
    harness._nameplate = None
    harness._nameplate_name = "Mochi"
    harness._nameplate_mood = harness._mood_model.label
    harness._nameplate_feedback = None
    harness.state = SimpleNamespace(current=MochiState.IDLE)
    harness.reject_transition = False
    return harness


class NameplateMoodTransitionTests(unittest.TestCase):
    def test_accepted_transition_updates_visible_mood_state(self) -> None:
        harness = _make_harness()

        self.assertTrue(harness._transition_to(MochiState.SLEEPING))

        self.assertEqual(harness._nameplate_mood, "sleepy")
        self.assertEqual(harness._mood_model.label, "sleepy")

    def test_rejected_transition_does_not_change_mood(self) -> None:
        harness = _make_harness()
        harness.reject_transition = True

        self.assertFalse(harness._transition_to(MochiState.DANCING))

        self.assertEqual(harness._nameplate_mood, "content")
        self.assertEqual(harness._mood_model.label, "content")

    def test_mechanical_transition_preserves_last_meaningful_mood(self) -> None:
        harness = _make_harness()
        self.assertTrue(harness._transition_to(MochiState.HEART))
        self.assertEqual(harness._nameplate_mood, "cozy")

        self.assertTrue(harness._transition_to(MochiState.PICKUP))

        self.assertEqual(harness._nameplate_mood, "cozy")
        self.assertEqual(harness._mood_model.label, "cozy")

    def test_idle_after_reaction_restores_content(self) -> None:
        harness = _make_harness()
        self.assertTrue(harness._transition_to(MochiState.BOUNCING))
        self.assertEqual(harness._nameplate_mood, "excited")

        self.assertTrue(harness._transition_to(MochiState.IDLE))

        self.assertEqual(harness._nameplate_mood, "content")


if __name__ == "__main__":
    unittest.main()
