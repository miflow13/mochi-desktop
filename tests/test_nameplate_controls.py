"""Regression tests for the reusable nameplate/speech-bubble UI surface."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from mochi.presence.nameplate_controls import NameplateMixin


class _FakeNameplate:
    def __init__(self) -> None:
        self.visible = False
        self.name = "Mochi"
        self.status = None
        self.show_calls = 0
        self.hide_calls = 0
        self.update_position_calls = 0

    def show(self) -> None:
        self.show_calls += 1
        self.visible = True

    def hide(self) -> None:
        self.hide_calls += 1
        self.visible = False

    def update_position(self) -> None:
        self.update_position_calls += 1

    def set_name(self, name: str) -> None:
        self.name = name

    def set_status(self, status: str | None) -> None:
        self.status = status


class _FakeBubble:
    def __init__(self, *, visible: bool) -> None:
        self.visible = visible


def _make_mixin(
    *,
    nameplate_visible: bool,
    bubble,
) -> tuple[NameplateMixin, _FakeNameplate]:
    mixin = object.__new__(NameplateMixin)
    nameplate = _FakeNameplate()
    nameplate.visible = nameplate_visible
    mixin._nameplate = nameplate
    mixin._presence_bubble = bubble
    mixin._nameplate_name = "Mochi"
    mixin._nameplate_mood = None
    mixin._nameplate_feedback = None
    mixin._nameplate_feedback_remaining_seconds = 0.0
    mixin._nameplate_feedback_active_since = None
    return mixin, nameplate


class NameplateSpeechExclusivityTests(unittest.TestCase):
    def test_bubble_visible_hides_nameplate(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=True)
        )
        mixin._sync_nameplate_with_speech()
        self.assertFalse(nameplate.visible)
        self.assertEqual(nameplate.hide_calls, 1)

    def test_bubble_visible_keeps_nameplate_hidden_without_repeated_calls(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=False, bubble=_FakeBubble(visible=True)
        )
        mixin._sync_nameplate_with_speech()
        mixin._sync_nameplate_with_speech()
        self.assertFalse(nameplate.visible)
        self.assertEqual(nameplate.hide_calls, 0)
        self.assertEqual(nameplate.show_calls, 0)

    def test_bubble_hidden_shows_nameplate(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=False, bubble=_FakeBubble(visible=False)
        )
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)
        self.assertEqual(nameplate.show_calls, 1)

    def test_bubble_hidden_and_nameplate_already_visible_only_repositions(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)
        self.assertEqual(nameplate.show_calls, 0)
        self.assertEqual(nameplate.update_position_calls, 1)

    def test_bubble_appearing_then_disappearing_swaps_correctly(self) -> None:
        bubble = _FakeBubble(visible=False)
        mixin, nameplate = _make_mixin(nameplate_visible=False, bubble=bubble)

        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)

        bubble.visible = True
        mixin._sync_nameplate_with_speech()
        self.assertFalse(nameplate.visible)

        bubble.visible = False
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)

    def test_no_bubble_attribute_falls_back_to_showing_nameplate(self) -> None:
        mixin = object.__new__(NameplateMixin)
        nameplate = _FakeNameplate()
        mixin._nameplate = nameplate
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)

    def test_no_nameplate_is_a_safe_no_op(self) -> None:
        mixin = object.__new__(NameplateMixin)
        mixin._nameplate = None
        mixin._presence_bubble = _FakeBubble(visible=True)
        mixin._sync_nameplate_with_speech()


class NameplateContentPriorityTests(unittest.TestCase):
    def test_name_and_persistent_mood_use_same_surface(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )

        mixin.set_nameplate_name("Mochi")
        mixin.set_nameplate_mood("cozy")

        self.assertEqual(nameplate.name, "Mochi")
        self.assertEqual(nameplate.status, "cozy")

    def test_blank_name_falls_back_to_mochi(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )

        mixin.set_nameplate_name("   ")

        self.assertEqual(nameplate.name, "Mochi")

    def test_feedback_temporarily_overrides_mood_then_restores_it(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )
        mixin.set_nameplate_mood("cozy")

        mixin.show_nameplate_feedback("♥ thank you", duration_seconds=2.0)
        self.assertEqual(nameplate.status, "♥ thank you")

        mixin.clear_nameplate_feedback()
        self.assertEqual(nameplate.status, "cozy")

    def test_clearing_mood_leaves_name_only_when_no_feedback_exists(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )
        mixin.set_nameplate_mood("curious")

        mixin.clear_nameplate_mood()

        self.assertIsNone(nameplate.status)

    def test_new_feedback_replaces_old_feedback_and_resets_lifetime(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )
        mixin.show_nameplate_feedback("first", duration_seconds=1.0)
        mixin._nameplate_feedback_active_since = 10.0
        mixin._nameplate_feedback_remaining_seconds = 0.2

        mixin.show_nameplate_feedback("second", duration_seconds=3.0)

        self.assertEqual(nameplate.status, "second")
        self.assertEqual(mixin._nameplate_feedback_remaining_seconds, 3.0)
        self.assertIsNone(mixin._nameplate_feedback_active_since)

    def test_non_positive_feedback_duration_clears_override(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )
        mixin.set_nameplate_mood("cozy")
        mixin.show_nameplate_feedback("temporary", duration_seconds=2.0)

        mixin.show_nameplate_feedback("ignored", duration_seconds=0)

        self.assertIsNone(mixin._nameplate_feedback)
        self.assertEqual(nameplate.status, "cozy")

    def test_feedback_expires_after_visible_time_and_restores_mood(self) -> None:
        mixin, nameplate = _make_mixin(
            nameplate_visible=True, bubble=_FakeBubble(visible=False)
        )
        mixin.set_nameplate_mood("cozy")
        mixin.show_nameplate_feedback("thanks", duration_seconds=2.0)

        with patch(
            "mochi.presence.nameplate_controls.time.monotonic",
            side_effect=[100.0, 101.0, 102.1],
        ):
            mixin._advance_nameplate_feedback_lifetime()
            mixin._advance_nameplate_feedback_lifetime()
            self.assertEqual(nameplate.status, "thanks")
            mixin._advance_nameplate_feedback_lifetime()

        self.assertIsNone(mixin._nameplate_feedback)
        self.assertEqual(nameplate.status, "cozy")

    def test_feedback_clock_pauses_while_speech_bubble_owns_surface(self) -> None:
        bubble = _FakeBubble(visible=False)
        mixin, nameplate = _make_mixin(nameplate_visible=True, bubble=bubble)
        mixin.set_nameplate_mood("cozy")
        mixin.show_nameplate_feedback("thanks", duration_seconds=2.0)

        with patch(
            "mochi.presence.nameplate_controls.time.monotonic",
            side_effect=[10.0, 11.0, 100.0, 101.1],
        ):
            # One visible second is consumed.
            mixin._advance_nameplate_feedback_lifetime()
            mixin._advance_nameplate_feedback_lifetime()
            self.assertAlmostEqual(
                mixin._nameplate_feedback_remaining_seconds, 1.0, places=6
            )

            # Speech takes over. No wall-clock time is consumed while hidden.
            bubble.visible = True
            mixin._advance_nameplate_feedback_lifetime()
            self.assertIsNone(mixin._nameplate_feedback_active_since)
            self.assertAlmostEqual(
                mixin._nameplate_feedback_remaining_seconds, 1.0, places=6
            )

            # Bubble yields; first tick restarts the visible clock, second tick
            # consumes the remaining second and restores the mood.
            bubble.visible = False
            mixin._advance_nameplate_feedback_lifetime()
            mixin._advance_nameplate_feedback_lifetime()

        self.assertIsNone(mixin._nameplate_feedback)
        self.assertEqual(nameplate.status, "cozy")


if __name__ == "__main__":
    unittest.main()
