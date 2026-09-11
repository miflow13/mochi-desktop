"""Regression tests for nameplate/speech-bubble mutual exclusivity.

The nameplate and Mochi Sense's speech bubble share the same anchor point
above Mochi, so only one may be visible at a time. These tests exercise
`NameplateMixin._sync_nameplate_with_speech()` directly against lightweight
stand-ins, without constructing a real Buddy/GTK application.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from mochi.presence.nameplate_controls import NameplateMixin


class _FakeNameplate:
    def __init__(self) -> None:
        self.visible = False
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


class _FakeBubble:
    def __init__(self, *, visible: bool) -> None:
        self.visible = visible


def _make_mixin(*, nameplate_visible: bool, bubble) -> tuple[NameplateMixin, _FakeNameplate]:
    mixin = object.__new__(NameplateMixin)
    nameplate = _FakeNameplate()
    nameplate.visible = nameplate_visible
    mixin._nameplate = nameplate
    mixin._presence_bubble = bubble
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

        # Nameplate shows first (no speech yet).
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)

        # Speech bubble starts talking -- nameplate must yield.
        bubble.visible = True
        mixin._sync_nameplate_with_speech()
        self.assertFalse(nameplate.visible)

        # Speech bubble finishes -- nameplate reappears.
        bubble.visible = False
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)

    def test_no_bubble_attribute_falls_back_to_showing_nameplate(self) -> None:
        # Some Buddy subclasses may not define _presence_bubble at all
        # (e.g. preview mode paths); absence must not raise or hide it.
        mixin = object.__new__(NameplateMixin)
        nameplate = _FakeNameplate()
        mixin._nameplate = nameplate
        mixin._sync_nameplate_with_speech()
        self.assertTrue(nameplate.visible)

    def test_no_nameplate_is_a_safe_no_op(self) -> None:
        mixin = object.__new__(NameplateMixin)
        mixin._nameplate = None
        mixin._presence_bubble = _FakeBubble(visible=True)
        mixin._sync_nameplate_with_speech()  # Must not raise.


if __name__ == "__main__":
    unittest.main()
