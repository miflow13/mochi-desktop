import unittest
from unittest.mock import patch
from types import SimpleNamespace

from mochi.windowing import WindowPlacement


class MonitorList:
    def __init__(self, *monitors) -> None:
        self._monitors = monitors

    def get_n_items(self) -> int:
        return len(self._monitors)

    def get_item(self, index: int):
        return self._monitors[index]


def monitor(x: int, y: int, width: int, height: int):
    geometry = SimpleNamespace(x=x, y=y, width=width, height=height)
    return SimpleNamespace(get_geometry=lambda: geometry)


def window(monitors, width=100, height=100, scale=None):
    surface = None if scale is None else SimpleNamespace(get_scale=lambda: scale)
    return SimpleNamespace(
        get_default_size=lambda: (width, height),
        get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
        get_surface=lambda: surface,
    )


class WindowPlacementMonitorTests(unittest.TestCase):
    def test_position_is_clamped_to_the_monitor_containing_the_window(self) -> None:
        monitors = MonitorList(
            monitor(0, 0, 1920, 1080),
            monitor(1920, 0, 2560, 1440),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window(monitors, 128, 128)
        placement.layer_shell_enabled = False

        position = WindowPlacement.clamp_position(placement, 2200, 300)

        self.assertEqual((position.x, position.y), (2200, 300))

    @patch("mochi.windowing.primary_button_pressed", return_value=False)
    @patch("mochi.windowing.move_window")
    @patch("mochi.windowing.get_window_position", return_value=(-80, 790))
    def test_sync_from_window_pushes_far_out_of_bounds_window_back_to_safe_edge(
        self, _get_window_position, move_window, _primary_button_pressed
    ) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        test_window = window(monitors)
        placement = object.__new__(WindowPlacement)
        placement.window = test_window
        placement.position = SimpleNamespace(x=100, y=100)
        placement.layer_shell_enabled = False

        position = WindowPlacement.sync_from_window(placement)

        self.assertEqual((position.x, position.y), (-44, 688))
        move_window.assert_called_once_with(test_window, -44, 688)

    @patch("mochi.windowing.primary_button_pressed", return_value=True)
    @patch("mochi.windowing.move_window")
    @patch("mochi.windowing.get_window_position", return_value=(-80, 790))
    def test_sync_from_window_does_not_correct_during_active_native_drag(
        self, _get_window_position, move_window, _primary_button_pressed
    ) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        test_window = window(monitors)
        placement = object.__new__(WindowPlacement)
        placement.window = test_window
        placement.position = SimpleNamespace(x=100, y=100)
        placement.layer_shell_enabled = False

        position = WindowPlacement.sync_from_window(placement)

        self.assertEqual((position.x, position.y), (-80, 790))
        move_window.assert_not_called()

    @patch("mochi.windowing.primary_button_pressed", return_value=False)
    @patch("mochi.windowing.move_window")
    @patch("mochi.windowing.get_window_position", return_value=(250, 300))
    def test_sync_from_window_does_not_fight_an_in_bounds_native_drag(
        self, _get_window_position, move_window, _primary_button_pressed
    ) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        test_window = window(monitors)
        placement = object.__new__(WindowPlacement)
        placement.window = test_window
        placement.position = SimpleNamespace(x=100, y=100)
        placement.layer_shell_enabled = False

        position = WindowPlacement.sync_from_window(placement)

        self.assertEqual((position.x, position.y), (250, 300))
        move_window.assert_not_called()

    def test_x11_clamp_is_permissive_horizontally_but_strict_vertically(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        placement = object.__new__(WindowPlacement)
        placement.window = window(monitors)
        placement.layer_shell_enabled = False

        top_left = WindowPlacement.clamp_position(placement, -50, -50)
        bottom_right = WindowPlacement.clamp_position(placement, 990, 790)

        self.assertEqual((top_left.x, top_left.y), (-44, 8))
        self.assertEqual((bottom_right.x, bottom_right.y), (944, 688))

    def test_scaled_xwayland_position_uses_device_pixel_bounds(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1536, 864))
        placement = object.__new__(WindowPlacement)
        placement.window = window(monitors, 128, 128, scale=2.0)
        placement.layer_shell_enabled = False

        in_bounds = WindowPlacement.clamp_position(placement, 2954, 274)
        too_far = WindowPlacement.clamp_position(placement, 3100, 274)

        self.assertEqual((in_bounds.x, in_bounds.y), (2954, 274))
        self.assertEqual((too_far.x, too_far.y), (2960, 274))

    def test_scaled_xwayland_bottom_edge_keeps_full_window_visible(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1536, 864))
        placement = object.__new__(WindowPlacement)
        placement.window = window(monitors, 128, 128, scale=2.0)
        placement.layer_shell_enabled = False

        position = WindowPlacement.clamp_position(placement, 800, 1608)

        self.assertEqual((position.x, position.y), (800, 1448))

    @patch("mochi.windowing.primary_button_pressed", return_value=False)
    @patch("mochi.windowing.move_window")
    @patch("mochi.windowing.get_window_position", return_value=(2954, 274))
    def test_scaled_xwayland_release_does_not_snap_to_logical_right_edge(
        self, _get_window_position, move_window, _primary_button_pressed
    ) -> None:
        monitors = MonitorList(monitor(0, 0, 1536, 864))
        test_window = window(monitors, 128, 128, scale=2.0)
        placement = object.__new__(WindowPlacement)
        placement.window = test_window
        placement.position = SimpleNamespace(x=1400, y=274)
        placement.layer_shell_enabled = False

        position = WindowPlacement.sync_from_window(placement)

        self.assertEqual((position.x, position.y), (2954, 274))
        move_window.assert_not_called()

    def test_gap_position_uses_the_nearest_monitor(self) -> None:
        monitors = MonitorList(
            monitor(0, 0, 1000, 800),
            monitor(1200, 0, 1000, 800),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window(monitors)
        placement.layer_shell_enabled = False

        position = WindowPlacement.clamp_position(placement, 1150, 200)

        self.assertEqual((position.x, position.y), (1156, 200))


if __name__ == "__main__":
    unittest.main()
