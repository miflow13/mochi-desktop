"""Regression coverage for Mochi's compact bond meter UI slice."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock

from mochi.presence.bond_meter import (
    BOND_PHASE_COUNT,
    DEFAULT_BOND_PHASES_FILLED,
    BondMeterMixin,
    bond_pip_states,
    normalize_bond_pips,
)


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


class _BondHarness(BondMeterMixin, _LayoutBase):
    def _build_bond_meter_row(self):
        return "bond-row"


class _FeedOuterMixin:
    def _build_context_menu(self):
        menu = super()._build_context_menu()
        self._register_context_menu_row(
            "feed",
            "feed-row",
            before="sleep",
        )
        return menu


class _CombinedMenuHarness(_FeedOuterMixin, _BondHarness):
    pass


class BondMeterTests(unittest.TestCase):
    def test_meter_has_exactly_four_phases(self) -> None:
        self.assertEqual(BOND_PHASE_COUNT, 4)
        self.assertEqual(len(bond_pip_states(2)), 4)

    def test_default_placeholder_is_two_of_four(self) -> None:
        self.assertEqual(DEFAULT_BOND_PHASES_FILLED, 2)
        self.assertEqual(
            bond_pip_states(DEFAULT_BOND_PHASES_FILLED),
            (True, True, False, False),
        )

    def test_pip_count_clamps_safely(self) -> None:
        self.assertEqual(normalize_bond_pips(-10), 0)
        self.assertEqual(normalize_bond_pips(0), 0)
        self.assertEqual(normalize_bond_pips(3), 3)
        self.assertEqual(normalize_bond_pips(99), 4)
        self.assertEqual(normalize_bond_pips("bad"), 0)

    def test_bond_row_lands_between_status_and_feed(self) -> None:
        harness = _CombinedMenuHarness()

        self.assertEqual(harness._build_context_menu(), "menu")
        self.assertEqual(
            harness.rows,
            ["status", "bond", "feed", "sleep", "close"],
        )

    def test_future_logic_seam_updates_only_display_state(self) -> None:
        harness = object.__new__(BondMeterMixin)
        harness._bond_ui_filled = DEFAULT_BOND_PHASES_FILLED
        harness._bond_meter = Mock()

        harness.set_bond_progress_for_ui(8)

        self.assertEqual(harness._bond_ui_filled, 4)
        harness._bond_meter.set_filled.assert_called_once_with(4)

    def test_bond_ui_stays_passive_and_reuses_existing_menu(self) -> None:
        source = inspect.getsource(BondMeterMixin._build_context_menu)
        row_source = inspect.getsource(BondMeterMixin._build_bond_meter_row)

        self.assertIn("super()._build_context_menu()", source)
        self.assertIn("_register_context_menu_row", source)
        self.assertIn('before="sleep"', source)
        self.assertIn("set_can_target(False)", row_source)
        self.assertNotIn("Gtk.Popover", source)
        self.assertNotIn("MenuWindow(", source)
        self.assertNotIn("connect(", source)
        self.assertNotIn("GestureClick", source)


if __name__ == "__main__":
    unittest.main()
