import unittest

from mochi.state import MochiState
from mochi.status import (
    OverlayMode,
    OverlayTrigger,
    OverlayVisibility,
    clamp_status_value,
    friendly_state_label,
    should_show_overlay,
)


class StatusPresentationTests(unittest.TestCase):
    def test_states_have_friendly_labels(self) -> None:
        self.assertEqual(friendly_state_label(MochiState.WAKING), "Waking up")
        self.assertEqual(friendly_state_label(MochiState.SQUISHING), "Happy")
        self.assertEqual(friendly_state_label(MochiState.SLEEPING), "Sleeping")
        self.assertEqual(friendly_state_label(MochiState.PICKING_UP), "Picked up")

    def test_status_value_is_clamped(self) -> None:
        self.assertEqual(clamp_status_value(-0.5), 0.0)
        self.assertEqual(clamp_status_value(0.35), 0.35)
        self.assertEqual(clamp_status_value(2.0), 1.0)

    def test_overlay_uses_only_explicit_click_or_hover_triggers(self) -> None:
        self.assertTrue(should_show_overlay(OverlayTrigger.HOVER))

    def test_repeated_clicks_replace_stale_generation(self) -> None:
        visibility = OverlayVisibility()
        first = visibility.present(OverlayMode.PEEK)
        second = visibility.present(OverlayMode.PEEK)

        self.assertFalse(visibility.can_hide(first, OverlayMode.PEEK))
        self.assertTrue(visibility.can_hide(second, OverlayMode.PEEK))

    def test_expanded_mode_replaces_peek_mode(self) -> None:
        visibility = OverlayVisibility()
        visibility.present(OverlayMode.PEEK)
        expanded_generation = visibility.present(OverlayMode.EXPANDED)

        self.assertFalse(visibility.can_hide(expanded_generation, OverlayMode.PEEK))
        self.assertTrue(visibility.can_hide(expanded_generation, OverlayMode.EXPANDED))

    def test_hidden_is_default_and_can_dismiss_expanded(self) -> None:
        visibility = OverlayVisibility()
        self.assertIs(visibility.mode, OverlayMode.HIDDEN)
        visibility.present(OverlayMode.EXPANDED)
        visibility.hide()
        self.assertIs(visibility.mode, OverlayMode.HIDDEN)


if __name__ == "__main__":
    unittest.main()
