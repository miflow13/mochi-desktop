import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.config import Position
from mochi.edge_roam import (
    EdgeBounds,
    EdgeWalkMotion,
    build_edge_roam_motion,
    nearest_edge_point,
)
from mochi.presence.edge_roam_controls import EdgeRoamMixin
from mochi.state import MochiState


class _Placement:
    EDGE_PADDING_PX = 8
    BOTTOM_PADDING_PX = 12

    def __init__(self, *, width=100, height=100, scale=1.0) -> None:
        geometry = SimpleNamespace(x=0, y=0, width=1000, height=800)
        monitor = SimpleNamespace(get_geometry=lambda: geometry)
        self.window = SimpleNamespace(get_default_size=lambda: (width, height))
        self.layer_shell_enabled = False
        self._scale = scale
        self._monitor = monitor

    def _monitor_for_position(self, _x, _y):
        return self._monitor

    def _x11_coordinate_scale(self):
        return self._scale


class _TogglePlacement(_Placement):
    def __init__(self, position: Position) -> None:
        super().__init__()
        self.position = position
        self.move_to = Mock(side_effect=self._move_to)

    def sync_from_window(self) -> Position:
        return self.position

    def _move_to(self, x: int, y: int) -> Position:
        self.position = Position(x, y)
        return self.position


class _EdgeRoamHarness(EdgeRoamMixin):
    def __init__(self, position: Position, state: MochiState) -> None:
        self._edge_roam = False
        self._edge_roam_switch = Mock()
        self._edge_roam_clockwise = True
        self._placement = _TogglePlacement(position)
        self._config = SimpleNamespace(
            save_edge_roam=Mock(),
            save_position=Mock(),
        )
        self.state = SimpleNamespace(current=state)
        self._cancel_walk = Mock()
        self._transition_to = Mock(return_value=True)
        self._play_animation = Mock()
        self._logger = Mock()


class EdgeRoamTests(unittest.TestCase):
    def test_center_position_projects_to_nearest_edge(self) -> None:
        bounds = EdgeBounds(8, 892, 8, 688)
        point = nearest_edge_point(Position(450, 300), bounds)
        self.assertEqual(point, Position(450, 8))

    def test_first_edge_roam_walk_heads_to_nearest_edge(self) -> None:
        motion = build_edge_roam_motion(
            _Placement(),
            Position(450, 300),
            travel_distance=160,
            clockwise=True,
            cycle_duration_ms=800,
            speed_px_per_second=72,
        )
        self.assertIsNotNone(motion)
        self.assertNotIsInstance(motion, EdgeWalkMotion)
        self.assertEqual(motion.target, (450, 8))

    def test_perimeter_motion_rounds_corner_without_crossing_interior(self) -> None:
        motion = build_edge_roam_motion(
            _Placement(),
            Position(850, 8),
            travel_distance=160,
            clockwise=True,
            cycle_duration_ms=800,
            speed_px_per_second=72,
        )
        self.assertIsInstance(motion, EdgeWalkMotion)
        samples = [
            motion.position_at(round(motion.duration_ms * fraction / 10))
            for fraction in range(11)
        ]
        for x, y in samples:
            self.assertTrue(
                x in (motion.bounds.left, motion.bounds.right)
                or y in (motion.bounds.top, motion.bounds.bottom),
                f"edge roam entered the interior at {(x, y)}",
            )

    def test_counterclockwise_motion_stays_on_perimeter(self) -> None:
        motion = build_edge_roam_motion(
            _Placement(),
            Position(300, 688),
            travel_distance=220,
            clockwise=False,
            cycle_duration_ms=800,
            speed_px_per_second=72,
        )
        self.assertIsInstance(motion, EdgeWalkMotion)
        for elapsed in range(0, motion.duration_ms + 1, max(1, motion.duration_ms // 12)):
            x, y = motion.position_at(elapsed)
            self.assertTrue(
                x in (motion.bounds.left, motion.bounds.right)
                or y in (motion.bounds.top, motion.bounds.bottom)
            )

    def test_scaled_xwayland_approach_uses_device_pixel_edge(self) -> None:
        motion = build_edge_roam_motion(
            _Placement(scale=2.0),
            Position(900, 500),
            travel_distance=120,
            clockwise=True,
            cycle_duration_ms=800,
            speed_px_per_second=72,
        )
        self.assertIsNotNone(motion)
        self.assertNotIsInstance(motion, EdgeWalkMotion)
        self.assertEqual(motion.target, (900, 16))

    def test_scaled_xwayland_perimeter_uses_device_pixel_bounds(self) -> None:
        motion = build_edge_roam_motion(
            _Placement(scale=2.0),
            Position(900, 16),
            travel_distance=120,
            clockwise=True,
            cycle_duration_ms=800,
            speed_px_per_second=72,
        )
        self.assertIsInstance(motion, EdgeWalkMotion)
        self.assertEqual(motion.bounds, EdgeBounds(16, 1784, 16, 1376))

    def test_enabling_edge_roam_moves_mochi_to_nearest_edge(self) -> None:
        buddy = _EdgeRoamHarness(Position(450, 300), MochiState.IDLE)

        with patch("mochi.presence.edge_roam_controls.random.choice", return_value=True):
            buddy._toggle_edge_roam(None)

        self.assertTrue(buddy._edge_roam)
        buddy._placement.move_to.assert_called_once_with(450, 8)
        buddy._config.save_position.assert_called_once_with(Position(450, 8))
        buddy._cancel_walk.assert_not_called()

    def test_enabling_edge_roam_cancels_walk_before_moving_to_edge(self) -> None:
        buddy = _EdgeRoamHarness(Position(450, 300), MochiState.WALKING)

        with patch("mochi.presence.edge_roam_controls.random.choice", return_value=False):
            buddy._toggle_edge_roam(None)

        buddy._cancel_walk.assert_called_once()
        buddy._transition_to.assert_called_once_with(MochiState.IDLE)
        buddy._play_animation.assert_called_once_with("idle")
        buddy._placement.move_to.assert_called_once_with(450, 8)


if __name__ == "__main__":
    unittest.main()
