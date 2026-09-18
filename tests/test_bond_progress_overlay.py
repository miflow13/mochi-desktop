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
    overlay._emote_unlock_active = False
    overlay._level_up_previous_level = None
    overlay._state = BondState()
    overlay._on_level_up_finished = Mock()

    overlay._window = Mock()
    overlay._window.get_visible.return_value = False
    overlay._popover = Mock()
    overlay._popover.get_visible.return_value = False

    overlay._card = Mock()
    overlay._popover_card = Mock()
    overlay._normal_content = Mock()
    overlay._popover_normal_content = Mock()
    overlay._level_up_content = Mock()
    overlay._popover_level_up_content = Mock()
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
    overlay._level_up_title = Mock()
    overlay._popover_level_up_title = Mock()
    overlay._level_up_level = Mock()
    overlay._popover_level_up_level = Mock()
    overlay._level_up_subtitle = Mock()
    overlay._popover_level_up_subtitle = Mock()
    return overlay


def test_update_shows_exact_xp_progress() -> None:
    overlay = _overlay_harness()

    overlay.update(BondState(level=3, xp=210))

    overlay._level_label.set_text.assert_called_with("Bond Lv. 3")
    overlay._activity_label.set_text.assert_called_with("typing together")
    overlay._xp_label.set_text.assert_called_with(
        f"210 / {BondState(level=3, xp=210).xp_required} XP"
    )


def test_xp_gain_keeps_hud_text_quiet_and_schedules_brief_highlight() -> None:
    overlay = _overlay_harness()
    overlay.resume = Mock()

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=91,
    ) as timeout:
        overlay.notify_xp_gain(BondState(level=1, xp=22), 1)

    overlay._gain_label.set_text.assert_called_with("")
    timeout.assert_called_once_with(
        BondProgressOverlay.GAIN_FLASH_MS,
        overlay._finish_gain_flash,
    )
    assert overlay._gain_source_id == 91


def test_level_up_switches_to_dedicated_celebration_card() -> None:
    overlay = _overlay_harness()
    overlay.resume = Mock()

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=92,
    ):
        overlay.show_level_up(BondState(level=2, xp=5), previous_level=1)

    overlay._normal_content.set_visible.assert_called_with(False)
    overlay._level_up_content.set_visible.assert_called_with(True)
    overlay._level_up_level.set_text.assert_called_with("Bond Level 2")
    assert overlay._activity == "typing together"
    assert overlay.level_up_active is True


def test_finish_activity_does_not_create_duplicate_level_up_hide_timer() -> None:
    overlay = _overlay_harness()
    overlay._level_up_active = True

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=93,
    ) as timeout:
        overlay.finish_activity(1.0)

    timeout.assert_not_called()
    assert overlay._hide_source_id is None


def test_dismiss_immediately_retires_hud_and_level_up_state() -> None:
    overlay = _overlay_harness()
    overlay._level_up_active = True
    overlay._level_up_previous_level = 1
    overlay._gain_text = "+1 XP"
    overlay._hide_surfaces = Mock()
    overlay._set_gain_highlight = Mock()
    overlay._set_level_up_highlight = Mock()
    overlay._set_level_up_content = Mock()

    overlay.dismiss()

    assert overlay.active is False
    assert overlay.level_up_active is False
    assert overlay._level_up_previous_level is None
    assert overlay._gain_text == ""
    overlay._hide_surfaces.assert_called_once_with()
    overlay._set_gain_highlight.assert_called_once_with(False)
    overlay._set_level_up_highlight.assert_called_once_with(False)
    overlay._set_level_up_content.assert_called_once_with(False)
    overlay._on_level_up_finished.assert_called_once_with()


def test_level_up_card_finishes_by_hiding_instead_of_restoring_meter() -> None:
    overlay = _overlay_harness()
    overlay._level_up_active = True
    overlay._level_up_previous_level = 1
    overlay._hide_surfaces = Mock()
    overlay._set_level_up_highlight = Mock()
    overlay._set_level_up_content = Mock()

    result = overlay._finish_level_up()

    assert result == 0
    assert overlay.active is False
    assert overlay.level_up_active is False
    overlay._set_level_up_content.assert_called_once_with(False)
    overlay._hide_surfaces.assert_called_once_with()
    overlay._on_level_up_finished.assert_called_once_with()


def test_level_up_cancels_stale_gain_timer_before_celebration() -> None:
    overlay = _overlay_harness()
    overlay._gain_source_id = 77
    overlay.resume = Mock()
    overlay._set_gain_highlight = Mock()

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.source_remove"
    ) as remove, patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=94,
    ):
        overlay.show_level_up(BondState(level=2, xp=0), previous_level=1)

    remove.assert_called_once_with(77)
    overlay._set_gain_highlight.assert_called_with(False)
    assert overlay._gain_source_id is None
    assert overlay._level_up_source_id == 94


def test_emote_unlock_switches_to_special_reveal_card() -> None:
    from mochi.emotes import EMOTES_BY_ID

    overlay = _overlay_harness()
    overlay.resume = Mock()

    with patch(
        "mochi.presence.bond_progress_overlay.GLib.timeout_add",
        return_value=95,
    ):
        overlay.show_emote_unlock(EMOTES_BY_ID["side-eye"])

    overlay._level_up_title.set_text.assert_called_with(
        "✦  NEW EMOTE UNLOCKED!  ✦"
    )
    overlay._level_up_level.set_text.assert_called_with("Side Eye")
    overlay._level_up_subtitle.set_text.assert_called_with(
        "UNCOMMON · Mochi learned a new idle mood"
    )
    assert overlay.emote_unlock_active is True
    assert overlay.presentation_active is True
    assert overlay._level_up_source_id == 95


def test_emote_unlock_finish_notifies_bond_queue() -> None:
    overlay = _overlay_harness()
    overlay._emote_unlock_active = True
    overlay._hide_surfaces = Mock()
    overlay._set_level_up_highlight = Mock()
    overlay._set_level_up_content = Mock()

    result = overlay._finish_emote_unlock()

    assert result == 0
    assert overlay.emote_unlock_active is False
    overlay._on_level_up_finished.assert_called_once_with()
