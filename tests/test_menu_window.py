import inspect
import unittest
from types import SimpleNamespace

from mochi.menu_window import MenuWindow, menu_position_for_anchor


def geometry(x: int, y: int, width: int, height: int):
    return SimpleNamespace(x=x, y=y, width=width, height=height)


class MenuPositionTests(unittest.TestCase):
    def test_places_menu_on_monitor_containing_anchor(self) -> None:
        monitors = [geometry(0, 0, 1920, 1080), geometry(1920, 0, 2560, 1440)]
        x, y = menu_position_for_anchor(2200, 500, 244, 176, monitors)
        self.assertGreaterEqual(x, 1932)
        self.assertLessEqual(x + 244, 4468)
        self.assertGreaterEqual(y, 12)
        self.assertLessEqual(y + 176, 1428)

    def test_supports_vertically_stacked_monitors(self) -> None:
        monitors = [geometry(0, 0, 1920, 1080), geometry(1920, 1080, 2560, 1440)]
        x, y = menu_position_for_anchor(2500, 1400, 332, 680, monitors)
        self.assertGreaterEqual(x, 1932)
        self.assertGreaterEqual(y, 1092)
        self.assertLessEqual(y + 680, 2508)

    def test_flips_left_near_right_edge(self) -> None:
        monitors = [geometry(0, 0, 1000, 800)]
        x, _ = menu_position_for_anchor(960, 300, 244, 176, monitors)
        self.assertLess(x, 960)

    def test_menu_window_supports_optional_owner_following(self) -> None:
        source = inspect.getsource(MenuWindow)
        self.assertIn("follow_owner: bool = False", source)
        self.assertIn("GLib.timeout_add(33, self._follow_owner_tick)", source)

    def test_menu_window_uses_native_window_manager_drag(self) -> None:
        handle_source = inspect.getsource(MenuWindow.set_drag_handle)
        drag_source = inspect.getsource(MenuWindow._on_drag_pressed)
        self.assertIn("Gtk.GestureClick.new()", handle_source)
        self.assertIn("surface.begin_move", drag_source)
        self.assertNotIn("move_window(", drag_source)

    def test_menu_window_supports_focus_loss_dismissal(self) -> None:
        source = inspect.getsource(MenuWindow)
        self.assertIn("dismiss_on_focus_loss: bool = False", source)
        self.assertIn('notify::is-active', source)
        self.assertIn("_dismiss_if_still_inactive", source)


if __name__ == "__main__":
    unittest.main()
