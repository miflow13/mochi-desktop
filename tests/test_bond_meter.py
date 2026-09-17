"""Regression coverage for Mochi's bond progress integration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.care import BOND_FEED_XP, BondState
from mochi.presence.bond_meter import (
    BOND_PERSIST_INTERVAL_XP,
    BondMeterMixin,
)
from mochi.state import MochiState


class _LayoutBase:
    def __init__(self) -> None:
        self.rows = ["status", "sleep", "close"]

    def _build_context_menu(self):
        return "menu"

    def _register_context_menu_row(
        self,
        row_id,
        _widget,
        *,
        before=None,
        after=None,
        animated=True,
    ) -> None:
        if before is not None:
            self.rows.insert(self.rows.index(before), row_id)
        elif after is not None:
            self.rows.insert(self.rows.index(after) + 1, row_id)
        else:
            self.rows.append(row_id)


class _FeedMenuMixin:
    def _build_context_menu(self):
        menu = super()._build_context_menu()
        self._register_context_menu_row("feed", "feed-row", before="sleep")
        return menu


class _BondMenuHarness(BondMeterMixin, _FeedMenuMixin, _LayoutBase):
    def _build_bond_meter_row(self):
        return "bond-row"


class _CompletionBase:
    def _on_feed_animation_completed(self) -> None:
        self.completion_chain_calls += 1


class _BondCompletionHarness(BondMeterMixin, _CompletionBase):
    pass


def _runtime_harness(state: BondState | None = None):
    harness = object.__new__(BondMeterMixin)
    harness._bond_state = state or BondState()
    harness._bond_meter = Mock()
    harness._bond_level_label = Mock()
    harness._bond_progress_overlay = Mock()
    harness._bond_progress_overlay.active = True
    harness._bond_typing_source_id = None
    harness._bond_unsaved_xp = 0
    harness._config = Mock()
    harness._logger = Mock()
    harness.state = SimpleNamespace(current=MochiState.TYPING)
    harness._on_bond_level_up = Mock()
    return harness


def test_bond_row_lands_between_status_and_feed() -> None:
    harness = _BondMenuHarness()

    assert harness._build_context_menu() == "menu"
    assert harness.rows == ["status", "bond", "feed", "sleep", "close"]


def test_restore_loads_persisted_relationship_state() -> None:
    harness = _runtime_harness()
    harness._config.load_bond_state.return_value = BondState(level=3, xp=210)

    harness._restore_bond_state()

    assert harness._bond_state == BondState(level=3, xp=210)
    harness._bond_level_label.set_label.assert_called_once_with("Bond Lv. 3")
    harness._bond_meter.set_state.assert_called_once_with(BondState(level=3, xp=210))
    harness._bond_progress_overlay.update.assert_called_once_with(
        BondState(level=3, xp=210)
    )


def test_completed_feed_awards_large_boost_persists_and_shows_bar() -> None:
    harness = object.__new__(_BondCompletionHarness)
    runtime = _runtime_harness(BondState(level=1, xp=10))
    harness.__dict__.update(runtime.__dict__)
    harness.completion_chain_calls = 0

    harness._on_feed_animation_completed()

    assert harness._bond_state == BondState(level=1, xp=10 + BOND_FEED_XP)
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
    harness._bond_progress_overlay.show_activity.assert_called_once_with(
        harness._bond_state,
        "sharing a snack",
    )
    harness._bond_progress_overlay.finish_activity.assert_called_once()
    assert harness.completion_chain_calls == 1


def test_typing_tick_adds_one_xp_without_writing_every_second() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))

    assert harness._bond_typing_tick()

    assert harness._bond_state == BondState(level=1, xp=101)
    assert harness._bond_unsaved_xp == 1
    harness._config.save_bond_state.assert_not_called()


def test_typing_progress_batches_disk_writes() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))
    harness._bond_unsaved_xp = BOND_PERSIST_INTERVAL_XP - 1

    harness._bond_typing_tick()

    assert harness._bond_state == BondState(level=1, xp=101)
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
    assert harness._bond_unsaved_xp == 0


def test_typing_activity_starts_one_timer_and_live_overlay() -> None:
    harness = _runtime_harness()
    harness._bond_progress_overlay.active = False

    with patch(
        "mochi.presence.bond_meter.GLib.timeout_add_seconds",
        return_value=44,
    ) as timeout:
        harness._start_bond_typing_session()
        harness._start_bond_typing_session()

    timeout.assert_called_once()
    assert harness._bond_typing_source_id == 44
    assert harness._bond_progress_overlay.show_activity.call_count == 2
    harness._bond_progress_overlay.show_activity.assert_called_with(
        harness._bond_state,
        "typing together",
    )


def test_typing_stop_flushes_pending_xp_and_holds_progress_briefly() -> None:
    harness = _runtime_harness(BondState(level=1, xp=123))
    harness._bond_typing_source_id = 77
    harness._bond_unsaved_xp = 3

    with patch("mochi.presence.bond_meter.GLib.source_remove") as remove:
        harness._finish_bond_typing_session()

    remove.assert_called_once_with(77)
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
    harness._bond_progress_overlay.finish_activity.assert_called_once()
    assert harness._bond_typing_source_id is None
    assert harness._bond_unsaved_xp == 0


def test_typing_tick_stops_if_mochi_is_no_longer_typing() -> None:
    harness = _runtime_harness(BondState(level=1, xp=200))
    harness.state.current = MochiState.HEART

    result = harness._bond_typing_tick()

    assert result == 0
    assert harness._bond_state == BondState(level=1, xp=200)
    harness._bond_progress_overlay.finish_activity.assert_called_once()
