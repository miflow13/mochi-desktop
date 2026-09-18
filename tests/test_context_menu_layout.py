"""Regression coverage for the shared user context-menu layout interface."""

from __future__ import annotations

import inspect
import unittest

from mochi.buddy import Buddy
from mochi.presence.edge_roam_controls import EdgeRoamMixin
from mochi.presence.integration import PresenceBuddyMixin
from mochi.presence.nameplate_controls import NameplateMixin
from mochi.quick_start import QuickStartMixin


class _FakeContent:
    def __init__(self) -> None:
        self.children: list[object] = []

    def append(self, widget: object) -> None:
        self.children.append(widget)

    def prepend(self, widget: object) -> None:
        self.children.insert(0, widget)

    def insert_child_after(self, widget: object, sibling: object) -> None:
        index = self.children.index(sibling)
        self.children.insert(index + 1, widget)


class _FakeMenu:
    def __init__(self) -> None:
        self.preferred_sizes: list[tuple[int, int]] = []

    def set_preferred_size(self, width: int, height: int) -> None:
        self.preferred_sizes.append((width, height))


class _LayoutHarness:
    CONTEXT_MENU_WIDTH = Buddy.CONTEXT_MENU_WIDTH
    CONTEXT_MENU_BASE_HEIGHT = Buddy.CONTEXT_MENU_BASE_HEIGHT
    CONTEXT_MENU_UNKNOWN_ROW_HEIGHT = Buddy.CONTEXT_MENU_UNKNOWN_ROW_HEIGHT
    CONTEXT_MENU_MIN_HEIGHTS = Buddy.CONTEXT_MENU_MIN_HEIGHTS
    CONTEXT_MENU_BASE_SIZED_ROWS = Buddy.CONTEXT_MENU_BASE_SIZED_ROWS

    _initialize_context_menu_layout = Buddy._initialize_context_menu_layout
    _register_context_menu_row = Buddy._register_context_menu_row
    _get_context_menu_row = Buddy._get_context_menu_row
    _recalculate_context_menu_layout = Buddy._recalculate_context_menu_layout


def _layout() -> tuple[_LayoutHarness, _FakeMenu, _FakeContent]:
    layout = _LayoutHarness()
    menu = _FakeMenu()
    content = _FakeContent()
    layout._initialize_context_menu_layout(menu, content)
    return layout, menu, content


class ContextMenuLayoutTests(unittest.TestCase):
    def test_before_and_after_produce_deterministic_row_order(self) -> None:
        layout, _menu, content = _layout()
        row_names = ("header", "sleep", "close", "stay", "edge", "help")
        rows = {name: object() for name in row_names}

        layout._register_context_menu_row("header", rows["header"], animated=False)
        layout._register_context_menu_row("sleep", rows["sleep"])
        layout._register_context_menu_row("close", rows["close"])
        layout._register_context_menu_row("stay-put", rows["stay"], after="sleep")
        layout._register_context_menu_row("edge-roam", rows["edge"], after="sleep")
        layout._register_context_menu_row("quick-start", rows["help"], before="close")

        self.assertEqual(
            content.children,
            [
                rows["header"],
                rows["sleep"],
                rows["edge"],
                rows["stay"],
                rows["help"],
                rows["close"],
            ],
        )

    def test_duplicate_row_id_is_rejected_without_changing_layout(self) -> None:
        layout, _menu, content = _layout()
        original = object()
        layout._register_context_menu_row("sleep", original)

        with self.assertRaisesRegex(ValueError, "already registered"):
            layout._register_context_menu_row("sleep", object())

        self.assertEqual(content.children, [original])
        self.assertIs(layout._get_context_menu_row("sleep"), original)

    def test_animated_rows_follow_visual_order_once_each(self) -> None:
        layout, _menu, _content = _layout()
        sleep = object()
        status = object()
        close = object()
        layout._register_context_menu_row("sleep", sleep)
        layout._register_context_menu_row(
            "status", status, before="sleep", animated=False
        )
        layout._register_context_menu_row("close", close)

        self.assertEqual(layout._context_menu_animated_rows, (sleep, close))

    def test_reinitializing_layout_does_not_retain_old_rows(self) -> None:
        layout, _menu, _content = _layout()
        layout._register_context_menu_row("sleep", object())

        replacement_menu = _FakeMenu()
        replacement_content = _FakeContent()
        layout._initialize_context_menu_layout(replacement_menu, replacement_content)
        replacement_sleep = object()
        layout._register_context_menu_row("sleep", replacement_sleep)

        self.assertEqual(replacement_content.children, [replacement_sleep])
        self.assertEqual(layout._context_menu_animated_rows, (replacement_sleep,))

    def test_menu_sizing_is_recalculated_from_registered_rows(self) -> None:
        layout, menu, _content = _layout()
        layout._register_context_menu_row("sleep", object())
        layout._register_context_menu_row("close", object())
        self.assertEqual(menu.preferred_sizes[-1], (244, 176))

        layout._register_context_menu_row("stay-put", object(), after="sleep")
        self.assertEqual(menu.preferred_sizes[-1], (244, 224))
        layout._register_context_menu_row("edge-roam", object(), after="sleep")
        self.assertEqual(menu.preferred_sizes[-1], (244, 268))
        layout._register_context_menu_row("quick-start", object(), before="close")
        self.assertEqual(menu.preferred_sizes[-1], (244, 312))

    def test_unknown_row_gets_a_central_size_increment(self) -> None:
        layout, menu, _content = _layout()
        layout._register_context_menu_row("sleep", object())
        layout._register_context_menu_row("close", object())
        layout._register_context_menu_row(
            "future-feature",
            object(),
            before="close",
            animated=False,
        )

        self.assertEqual(menu.preferred_sizes[-1], (244, 220))

    def test_invalid_placement_is_rejected_before_gtk_insertion(self) -> None:
        layout, _menu, content = _layout()

        with self.assertRaisesRegex(KeyError, "missing"):
            layout._register_context_menu_row("new", object(), after="missing")
        with self.assertRaisesRegex(ValueError, "both"):
            layout._register_context_menu_row(
                "new", object(), after="sleep", before="close"
            )

        self.assertEqual(content.children, [])


class ContextMenuFeatureMigrationTests(unittest.TestCase):
    def test_feature_builders_use_only_the_shared_layout_interface(self) -> None:
        forbidden = (
            "_context_menu_content",
            "_context_menu_animated_rows",
            "_preferred_height",
            ".window.set_default_size",
            "insert_child_after",
            "insert_child_before",
        )
        builders = (
            EdgeRoamMixin._build_context_menu,
            PresenceBuddyMixin._build_context_menu,
            NameplateMixin._build_context_menu,
            QuickStartMixin._build_context_menu,
        )

        for builder in builders:
            source = inspect.getsource(builder)
            self.assertIn("_register_context_menu_row", source)
            for private_detail in forbidden:
                self.assertNotIn(private_detail, source)


if __name__ == "__main__":
    unittest.main()
