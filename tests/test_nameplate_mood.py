"""Regression coverage for wiring MoodModel into accepted Mochi transitions."""

from __future__ import annotations

import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

from mochi.animation import AnimationPlayer
from mochi.buddy import Buddy
from mochi.mood import MochiMood, MoodModel
from mochi.presence.idle_look import IdleLookMixin
from mochi.presence.nameplate_controls import NameplateMixin
from mochi.sprites import ANIMATIONS
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
    harness._current_animation = "idle"
    harness.player = SimpleNamespace(animation=ANIMATIONS["idle"])
    harness.played = []

    harness._resolve_mood_animation_name = MethodType(
        NameplateMixin._resolve_mood_animation_name,
        harness,
    )
    harness._animation_name_for_mood = MethodType(
        Buddy._animation_name_for_mood,
        harness,
    )
    harness._animation_for = MethodType(Buddy._animation_for, harness)
    harness._is_idle_visual_active = MethodType(
        Buddy._is_idle_visual_active,
        harness,
    )

    def play(name: str, after=None) -> None:
        harness._current_animation = name
        harness.player.animation = harness._animation_for(name)
        harness.played.append((name, after))

    harness._play_animation = play
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

    def test_explicit_sad_mood_survives_idle_and_walk_transitions(self) -> None:
        harness = _make_harness()
        self.assertIs(harness.set_mochi_mood("sad"), MochiMood.SAD)
        self.assertEqual(harness._nameplate_mood, "sad")
        self.assertEqual(harness.played[-1], ("idle", None))
        self.assertIs(harness.player.animation, ANIMATIONS["sad_idle"])
        self.assertTrue(harness._is_idle_visual_active())

        self.assertTrue(harness._transition_to(MochiState.WALKING))
        self.assertEqual(harness._nameplate_mood, "sad")
        self.assertEqual(harness._mood_model.current, MochiMood.SAD)
        harness._play_animation("walk")
        self.assertIs(harness.player.animation, ANIMATIONS["walk"])

        self.assertTrue(harness._transition_to(MochiState.IDLE))
        harness._play_animation("idle")
        self.assertIs(harness.player.animation, ANIMATIONS["sad_idle"])

    def test_clearing_explicit_mood_restores_contextual_mood(self) -> None:
        harness = _make_harness()
        harness.set_mochi_mood(MochiMood.SAD)
        self.assertTrue(harness._transition_to(MochiState.WALKING))
        harness._current_animation = "walk"

        self.assertIs(harness.clear_mochi_mood(), MochiMood.CURIOUS)
        self.assertEqual(harness._nameplate_mood, "curious")
        self.assertEqual(harness.played[-1], ("walk", None))
        self.assertIs(harness.player.animation, ANIMATIONS["walk"])

    def test_clearing_sad_while_idle_restores_normal_semantic_idle(self) -> None:
        harness = _make_harness()
        harness.set_mochi_mood(MochiMood.SAD)
        self.assertIs(harness.player.animation, ANIMATIONS["sad_idle"])

        self.assertIs(harness.clear_mochi_mood(), MochiMood.CONTENT)

        self.assertEqual(harness._current_animation, "idle")
        self.assertIs(harness.player.animation, ANIMATIONS["idle"])
        self.assertTrue(harness._is_idle_visual_active())

    def test_blink_resumes_the_installed_sad_idle_animation(self) -> None:
        harness = _make_harness()
        harness.set_mochi_mood(MochiMood.SAD)
        harness.player = AnimationPlayer()
        harness.player.play(ANIMATIONS["sad_idle"], frame_index=4, elapsed_ms=200)
        harness._current_animation = "idle"
        harness._active_animation = ANIMATIONS["sad_idle"]
        harness._idle_resume_position = None
        harness._logger = Mock()
        harness.queue_draw = Mock()
        harness._maybe_resume_ambient_activity = Mock(return_value=False)

        Buddy._play_animation(harness, "blink")
        self.assertIs(harness.player.animation, ANIMATIONS["blink"])

        Buddy._resume_idle(harness)
        self.assertEqual(harness._current_animation, "idle")
        self.assertIs(harness.player.animation, ANIMATIONS["sad_idle"])

    def test_idle_look_restores_the_installed_sad_idle_animation(self) -> None:
        harness = _make_harness()
        harness.set_mochi_mood(MochiMood.SAD)
        harness.player = AnimationPlayer()
        harness.player.play(ANIMATIONS["look"])
        harness._current_animation = "look"
        harness._active_animation = ANIMATIONS["look"]
        harness._pending_animation = None
        harness._idle_look_resume_position = (3, 100)
        harness._idle_look_active = True
        harness.IDLE_LOOK_ANIMATION = IdleLookMixin.IDLE_LOOK_ANIMATION
        harness._logger = Mock()
        harness.queue_draw = Mock()
        harness._schedule_idle_look = Mock()

        IdleLookMixin._restore_idle_after_look(harness, resume_ambient=False)

        self.assertEqual(harness._current_animation, "idle")
        self.assertIs(harness.player.animation, ANIMATIONS["sad_idle"])
        self.assertFalse(harness._idle_look_active)


if __name__ == "__main__":
    unittest.main()
