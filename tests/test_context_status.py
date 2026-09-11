"""Regression coverage for Mochi state/mood in the user right-click menu.

The historical context-menu regressions came from competing popup/input
surfaces. These tests keep the new status cue deliberately passive: it extends
the existing menu, refreshes on open, and never makes persistent mood text part
of the always-visible nameplate.
"""

from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.presence.nameplate_controls import NameplateMixin
from mochi.state import MochiState


class _FakeLabel:
    def __init__(self) -> None:
        self.text = None

    def set_text(self, text: str) -> None:
        self.text = text


class _FakeNameplate:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.statuses: list[str | None] = []

    def set_name(self, text: str) -> None:
        self.names.append(text)

    def set_status(self, text: str | None) -> None:
        self.statuses.append(text)


class _MenuBase:
    def _show_context_menu(self, *args) -> None:
        self.delegated_context_args = args


class _MenuHarness(NameplateMixin, _MenuBase):
    pass


class ContextStatusTests(unittest.TestCase):
    def test_status_snapshot_uses_current_state_and_tracked_mood(self) -> None:
        harness = object.__new__(NameplateMixin)
        harness.state = SimpleNamespace(current=MochiState.TYPING)
        harness._nameplate_mood = "curious"
        harness._context_state_value = _FakeLabel()
        harness._context_mood_value = _FakeLabel()

        NameplateMixin._refresh_context_status(harness)

        self.assertEqual(harness._context_state_value.text, "TYPING")
        self.assertEqual(harness._context_mood_value.text, "curious")

    def test_missing_mood_uses_neutral_placeholder(self) -> None:
        harness = object.__new__(NameplateMixin)
        harness.state = SimpleNamespace(current=MochiState.IDLE)
        harness._nameplate_mood = None
        harness._context_state_value = _FakeLabel()
        harness._context_mood_value = _FakeLabel()

        NameplateMixin._refresh_context_status(harness)

        self.assertEqual(harness._context_state_value.text, "IDLE")
        self.assertEqual(harness._context_mood_value.text, "—")

    def test_persistent_mood_is_not_rendered_below_name(self) -> None:
        harness = object.__new__(NameplateMixin)
        plate = _FakeNameplate()
        harness._nameplate = plate
        harness._nameplate_name = "Mochi"
        harness._nameplate_mood = "sleepy"
        harness._nameplate_feedback = None

        NameplateMixin._refresh_nameplate_content(harness)

        self.assertEqual(plate.names[-1], "Mochi")
        self.assertIsNone(plate.statuses[-1])

    def test_temporary_feedback_can_still_use_second_line(self) -> None:
        harness = object.__new__(NameplateMixin)
        plate = _FakeNameplate()
        harness._nameplate = plate
        harness._nameplate_name = "Mochi"
        harness._nameplate_mood = "content"
        harness._nameplate_feedback = "♥ thank you"

        NameplateMixin._refresh_nameplate_content(harness)

        self.assertEqual(plate.names[-1], "Mochi")
        self.assertEqual(plate.statuses[-1], "♥ thank you")

    def test_open_refreshes_status_then_delegates_to_existing_menu_path(self) -> None:
        harness = object.__new__(_MenuHarness)
        harness._context_menu = SimpleNamespace(get_visible=Mock(return_value=False))
        harness._refresh_context_status = Mock()

        NameplateMixin._show_context_menu(harness, "gesture", 1, 12.0, 18.0)

        harness._refresh_context_status.assert_called_once_with()
        self.assertEqual(
            harness.delegated_context_args,
            ("gesture", 1, 12.0, 18.0),
        )

    def test_second_right_click_does_not_refresh_before_toggle_close(self) -> None:
        harness = object.__new__(_MenuHarness)
        harness._context_menu = SimpleNamespace(get_visible=Mock(return_value=True))
        harness._refresh_context_status = Mock()

        NameplateMixin._show_context_menu(harness, "gesture", 1, 12.0, 18.0)

        harness._refresh_context_status.assert_not_called()
        self.assertEqual(
            harness.delegated_context_args,
            ("gesture", 1, 12.0, 18.0),
        )

    def test_status_extension_creates_no_second_popup_or_input_controller(self) -> None:
        source = inspect.getsource(NameplateMixin._build_context_menu)

        self.assertIn("super()._build_context_menu()", source)
        self.assertIn("set_can_target(False)", source)
        self.assertNotIn("Gtk.Popover", source)
        self.assertNotIn("MenuWindow(", source)
        self.assertNotIn("GestureClick", source)
        self.assertNotIn("EventController", source)
        self.assertNotIn("connect(", source)


if __name__ == "__main__":
    unittest.main()
