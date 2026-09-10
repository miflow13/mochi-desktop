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


class WindowPlacementMonitorTests(unittest.TestCase):
    def test_position_is_clamped_to_the_monitor_containing_the_window(self) -> None:
        monitors = MonitorList(
            monitor(0, 0, 1920, 1080),
            monitor(1920, 0, 2560, 1440),
        )
        window = SimpleNamespace(
            get_default_size=lambda: (128, 128),
            get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window
        placement.layer_shell_enabled = False

        position = WindowPlacement.clamp_position(placement, 2200, 300)

        self.assertEqual((position.x, position.y), (2200, 300))

    @patch("mochi.windowing.move_window")
    @patch("mochi.windowing.get_window_position", return_value=(-40, 760))
    def test_sync_from_window_pushes_out_of_bounds_window_back_inside(
        self, _get_window_position, move_window
    ) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        window = SimpleNamespace(
            get_default_size=lambda: (100, 100),
            get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window
        placement.position = SimpleNamespace(x=100, y=100)
        placement.layer_shell_enabled = False

        position = WindowPlacement.sync_from_window(placement)

        self.assertEqual((position.x, position.y), (24, 668))
        move_window.assert_called_once_with(window, 24, 668)

    @patch("mochi.windowing.move_window")
    @patch("mochi.windowing.get_window_position", return_value=(250, 300))
    def test_sync_from_window_does_not_fight_an_in_bounds_native_drag(
        self, _get_window_position, move_window
    ) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        window = SimpleNamespace(
            get_default_size=lambda: (100, 100),
            get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window
        placement.position = SimpleNamespace(x=100, y=100)
        placement.layer_shell_enabled = False

        position = WindowPlacement.sync_from_window(placement)

        self.assertEqual((position.x, position.y), (250, 300))
        move_window.assert_not_called()

    def test_clamp_keeps_visual_padding_around_screen_edges(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1000, 800))
        window = SimpleNamespace(
            get_default_size=lambda: (100, 100),
            get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window
        placement.layer_shell_enabled = False

        top_left = WindowPlacement.clamp_position(placement, -50, -50)
        bottom_right = WindowPlacement.clamp_position(placement, 990, 790)

        self.assertEqual((top_left.x, top_left.y), (24, 24))
        self.assertEqual((bottom_right.x, bottom_right.y), (876, 668))

    def test_gap_position_uses_the_nearest_monitor(self) -> None:
        monitors = MonitorList(
            monitor(0, 0, 1000, 800),
            monitor(1200, 0, 1000, 800),
        )
        window = SimpleNamespace(
            get_default_size=lambda: (100, 100),
            get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
        )
        placement = object.__new__(WindowPlacement)
        placement.window = window
        placement.layer_shell_enabled = False

        position = WindowPlacement.clamp_position(placement, 1150, 200)

        self.assertEqual((position.x, position.y), (1224, 200))


if __name__ == "__main__":
    unittest.main()
