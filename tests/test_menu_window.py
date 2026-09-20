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

    def test_scaled_x11_coordinates_keep_right_edge_menu_attached(self) -> None:
        monitors = [geometry(0, 0, 1000, 800)]
        x, y = menu_position_for_anchor(
            1900,
            600,
            244,
            176,
            monitors,
            coordinate_scale=2.0,
        )
        self.assertEqual(x, 1388)
        self.assertEqual(y, 552)
        self.assertGreater(x, 1000)
        self.assertLessEqual(x + 244 * 2, (1000 - 12) * 2)

    def test_full_mochi_bounds_keep_menu_completely_to_the_right(self) -> None:
        monitors = [geometry(0, 0, 1200, 800)]
        x, _ = menu_position_for_anchor(
            500,
            300,
            244,
            176,
            monitors,
            anchor_width=128,
        )
        self.assertGreaterEqual(x, 500 + 64 + 12)

    def test_full_mochi_bounds_flip_menu_completely_left_near_right_edge(self) -> None:
        monitors = [geometry(0, 0, 1000, 800)]
        x, _ = menu_position_for_anchor(
            930,
            300,
            244,
            176,
            monitors,
            anchor_width=128,
        )
        self.assertLessEqual(x + 244, 930 - 64 - 12)

    def test_scaled_x11_coordinates_preserve_left_edge_behavior(self) -> None:
        monitors = [geometry(0, 0, 1000, 800)]
        x, _ = menu_position_for_anchor(
            100,
            300,
            244,
            176,
            monitors,
            coordinate_scale=2.0,
        )
        self.assertEqual(x, 124)

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
        self.assertEqual(source.count('connect("notify::is-active"'), 1)
        self.assertIn("_dismiss_if_still_inactive", source)

    def test_focus_dismiss_callbacks_are_scoped_to_popup_generation(self) -> None:
        popup_source = inspect.getsource(MenuWindow.popup)
        arm_source = inspect.getsource(MenuWindow._arm_outside_dismiss)
        active_source = inspect.getsource(MenuWindow._on_active_changed)
        dismiss_source = inspect.getsource(MenuWindow._dismiss_if_still_inactive)
        self.assertIn("self._arm_outside_dismiss, serial", popup_source)
        self.assertIn("serial == self._position_serial", arm_source)
        self.assertIn("self._position_serial", active_source)
        self.assertIn("serial == self._position_serial", dismiss_source)


if __name__ == "__main__":
    unittest.main()
