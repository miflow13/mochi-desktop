import unittest
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

        self.assertEqual((position.x, position.y), (1200, 200))


if __name__ == "__main__":
    unittest.main()
