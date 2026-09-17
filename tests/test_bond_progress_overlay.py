"""Focused regression coverage for bond HUD gain and level-up feedback."""

from __future__ import annotations

from unittest.mock import Mock, patch

from mochi.care import BondState
from mochi.presence.bond_progress_overlay import BondProgressOverlay


def _overlay_harness() -> BondProgressOverlay:
    overlay = object.__new__(BondProgressOverlay)
    overlay._active = True
    overlay._mode = None
    overlay._hide_source_id = None
    overlay._gain_source_id = None
    overlay._level_up_source_id = None
    overlay._activity = "typing together"
    overlay._gain_text = ""
    overlay._level_up_active = False
    overlay._level_up_previous_level = None
    overlay._state = BondState()

    overlay._window = Mock()
    overlay._window.get_visible.return_value = False
    overlay._popover = Mock()
    overlay._popover.get_visible.return_value = False

    overlay._card = Mock()
    overlay._popover_card = Mock()
    overlay._level_label = Mock()
    overlay._popover_level_label = Mock()
    overlay._activity_label = Mock()
    overlay._popover_activity_label = Mock()
    overlay._bar = Mock()
    overlay._popover_bar = Mock()
    overlay._xp_label = Mock()
    overlay._popover_xp_label = Mock()
    overlay._gain_label = Mock()
    overlay._popover_gain_label = Mock()
    return overlay


def test_update_shows_exact_xp_progress() -> None:
    overlay = _overlay_harness()

    overlay.update(BondState(level=3, xp=210))

    overlay._level_label.set_text.assert_called_with("Bond Lv. 3")
    overlay._activity_label.set_text.assert_called_with("typing together")
    overlay._xp_label.set_text.assert_called_with(
        f"210 / {BondState(level=3, xp=210).xp_required} XP"
    )


def test_xp_gain_shows_amount_and_schedules_brief_highlight() -> None:
    overlay = _overlay_harness()
    overlay.resume = Mock()

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=91,
    ) as timeout:
        overlay.notify_xp_gain(BondState(level=1, xp=22), 1)

    overlay._gain_label.set_text.assert_called_with("+1 XP")
    timeout.assert_called_once_with(
        BondProgressOverlay.GAIN_FLASH_MS,
        overlay._finish_gain_flash,
    )
    assert overlay._gain_source_id == 91


def test_level_up_is_explicit_and_keeps_normal_activity_for_afterward() -> None:
    overlay = _overlay_harness()
    overlay.resume = Mock()

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=92,
    ):
        overlay.show_level_up(BondState(level=2, xp=5), previous_level=1)

    overlay._activity_label.set_text.assert_called_with("LEVEL UP!")
    overlay._gain_label.set_text.assert_called_with("Lv. 1 → 2 ✦")
    assert overlay._activity == "typing together"
    assert overlay.level_up_active is True


def test_finish_activity_holds_long_enough_for_level_up_message() -> None:
    overlay = _overlay_harness()
    overlay._level_up_active = True

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=93,
    ) as timeout:
        overlay.finish_activity(1.0)

    timeout.assert_called_once_with(
        round(BondProgressOverlay.LEVEL_UP_MIN_HOLD_SECONDS * 1000),
        overlay._finish_hide,
    )
