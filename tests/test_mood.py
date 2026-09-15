"""Focused regression coverage for Mochi's v0.3 mood model."""

from __future__ import annotations

import unittest

from mochi.mood import MochiMood, MoodModel
from mochi.state import MochiState


class MoodModelTests(unittest.TestCase):
    def test_default_mood_is_content(self) -> None:
        model = MoodModel()
        self.assertIs(model.current, MochiMood.CONTENT)
        self.assertEqual(model.label, "content")

    def test_meaningful_states_map_to_expected_moods(self) -> None:
        cases = {
            MochiState.IDLE: MochiMood.CONTENT,
            MochiState.BOUNCING: MochiMood.EXCITED,
            MochiState.SQUISHING: MochiMood.EXCITED,
            MochiState.EXCITED: MochiMood.EXCITED,
            MochiState.WALKING: MochiMood.CURIOUS,
            MochiState.SLEEPING: MochiMood.SLEEPY,
            MochiState.WAKING: MochiMood.CURIOUS,
            MochiState.HEART: MochiMood.COZY,
            MochiState.COMPUTER: MochiMood.CURIOUS,
            MochiState.TYPING: MochiMood.CURIOUS,
            MochiState.WATCHING: MochiMood.CURIOUS,
            MochiState.DANCING: MochiMood.EXCITED,
            MochiState.SEARCHING: MochiMood.CURIOUS,
            MochiState.FEDORA: MochiMood.EXCITED,
        }
        for state, expected in cases.items():
            with self.subTest(state=state):
                model = MoodModel()
                self.assertIs(model.observe_state(state), expected)
                self.assertIs(model.current, expected)

    def test_mechanical_states_preserve_previous_mood(self) -> None:
        model = MoodModel()
        self.assertIs(model.observe_state(MochiState.HEART), MochiMood.COZY)

        for state in (
            MochiState.BLINKING,
            MochiState.PICKUP,
            MochiState.DRAGGED,
            MochiState.DROPPING,
        ):
            with self.subTest(state=state):
                self.assertIsNone(model.observe_state(state))
                self.assertIs(model.current, MochiMood.COZY)

    def test_returning_to_idle_restores_content(self) -> None:
        model = MoodModel()
        self.assertIs(model.observe_state(MochiState.DANCING), MochiMood.EXCITED)

        self.assertIs(model.observe_state(MochiState.IDLE), MochiMood.CONTENT)
        self.assertIs(model.current, MochiMood.CONTENT)


if __name__ == "__main__":
    unittest.main()
