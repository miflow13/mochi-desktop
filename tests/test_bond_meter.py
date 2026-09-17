"""Regression coverage for Mochi's passive bond meter integration."""

from __future__ import annotations

from unittest.mock import Mock

from mochi.care import BondState
from mochi.presence.bond_meter import BondMeterMixin, bond_pip_states


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


def test_meter_has_four_passive_progress_states() -> None:
    assert bond_pip_states(0) == (False, False, False, False)
    assert bond_pip_states(2) == (True, True, False, False)
    assert bond_pip_states(99) == (True, True, True, True)
    assert bond_pip_states("bad") == (False, False, False, False)


def test_bond_row_lands_between_status_and_feed() -> None:
    harness = _BondMenuHarness()

    assert harness._build_context_menu() == "menu"
    assert harness.rows == ["status", "bond", "feed", "sleep", "close"]


def test_restore_loads_persisted_relationship_state() -> None:
    harness = object.__new__(BondMeterMixin)
    harness._bond_state = BondState()
    harness._bond_meter = Mock()
    harness._bond_level_label = Mock()
    harness._config = Mock()
    harness._config.load_bond_state.return_value = BondState(level=3, points=2)

    harness._restore_bond_state()

    assert harness._bond_state == BondState(level=3, points=2)
    harness._bond_level_label.set_label.assert_called_once_with("Bond Lv. 3")
    harness._bond_meter.set_filled.assert_called_once_with(2)


def test_completed_feed_awards_persists_and_chains() -> None:
    harness = object.__new__(_BondCompletionHarness)
    harness._bond_state = BondState(level=1, points=1)
    harness._bond_meter = Mock()
    harness._bond_level_label = Mock()
    harness._config = Mock()
    harness._logger = Mock()
    harness.completion_chain_calls = 0
    harness._on_bond_level_up = Mock()

    harness._on_feed_animation_completed()

    assert harness._bond_state == BondState(level=1, points=2)
    harness._config.save_bond_state.assert_called_once_with(BondState(level=1, points=2))
    assert harness.completion_chain_calls == 1
    harness._on_bond_level_up.assert_not_called()


def test_fourth_feed_rolls_to_next_level_and_fires_hook() -> None:
    harness = object.__new__(BondMeterMixin)
    harness._bond_state = BondState(level=4, points=3)
    harness._bond_meter = Mock()
    harness._bond_level_label = Mock()
    harness._config = Mock()
    harness._logger = Mock()
    harness._on_bond_level_up = Mock()

    advance = harness._award_bond()

    assert advance.levelled_up is True
    assert harness._bond_state == BondState(level=5, points=0)
    harness._config.save_bond_state.assert_called_once_with(BondState(level=5, points=0))
    harness._on_bond_level_up.assert_called_once_with(4, 5)


def test_non_positive_award_is_a_noop() -> None:
    harness = object.__new__(BondMeterMixin)
    harness._bond_state = BondState(level=2, points=2)
    harness._bond_meter = Mock()
    harness._bond_level_label = Mock()
    harness._config = Mock()
    harness._logger = Mock()
    harness._on_bond_level_up = Mock()

    advance = harness._award_bond(-10)

    assert advance.points_awarded == 0
    assert harness._bond_state == BondState(level=2, points=2)
    harness._config.save_bond_state.assert_not_called()
    harness._on_bond_level_up.assert_not_called()
