"""Perimeter-only autonomous walking for Mochi's Edge roam mode."""

from __future__ import annotations

from dataclasses import dataclass
import math

from mochi.behavior import WalkMotion
from mochi.config import Position


@dataclass(frozen=True, slots=True)
class EdgeBounds:
    left: int
    right: int
    top: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    @property
    def perimeter(self) -> int:
        return 2 * (self.width + self.height)


def bounds_for_placement(placement, origin: Position) -> EdgeBounds | None:
    """Return the same safe monitor bounds used by WindowPlacement.clamp_position."""
    monitor = placement._monitor_for_position(origin.x, origin.y)
    if monitor is None:
        return None

    geometry = monitor.get_geometry()
    width, height = placement.window.get_default_size()
    edge_padding = placement.EDGE_PADDING_PX
    bottom_padding = placement.BOTTOM_PADDING_PX

    if placement.layer_shell_enabled:
        left = geometry.x + edge_padding
        right = geometry.x + max(edge_padding, geometry.width - width - edge_padding)
        top = bottom_padding
        bottom = max(bottom_padding, geometry.height - height - edge_padding)
    else:
        scale = placement._x11_coordinate_scale()
        left = round((geometry.x + edge_padding) * scale)
        right = round(
            (
                geometry.x
                + max(edge_padding, geometry.width - width - edge_padding)
            )
            * scale
        )
        top = round((geometry.y + edge_padding) * scale)
        bottom = round(
            (
                geometry.y
                + max(edge_padding, geometry.height - height - bottom_padding)
            )
            * scale
        )

    return EdgeBounds(round(left), round(right), round(top), round(bottom))


def nearest_edge_point(origin: Position, bounds: EdgeBounds) -> Position:
    """Project a point to the nearest safe edge without changing monitors."""
    x = max(bounds.left, min(origin.x, bounds.right))
    y = max(bounds.top, min(origin.y, bounds.bottom))
    distances = (
        (abs(y - bounds.top), Position(x, bounds.top)),
        (abs(x - bounds.right), Position(bounds.right, y)),
        (abs(y - bounds.bottom), Position(x, bounds.bottom)),
        (abs(x - bounds.left), Position(bounds.left, y)),
    )
    return min(distances, key=lambda item: item[0])[1]


def _perimeter_coordinate(point: Position, bounds: EdgeBounds) -> float:
    """Map a perimeter point to clockwise distance from the top-left corner."""
    x = max(bounds.left, min(point.x, bounds.right))
    y = max(bounds.top, min(point.y, bounds.bottom))
    w = bounds.width
    h = bounds.height

    if y == bounds.top and x < bounds.right:
        return float(x - bounds.left)
    if x == bounds.right and y < bounds.bottom:
        return float(w + y - bounds.top)
    if y == bounds.bottom and x > bounds.left:
        return float(w + h + bounds.right - x)
    return float(2 * w + h + bounds.bottom - y)


def _point_at_perimeter(distance: float, bounds: EdgeBounds) -> Position:
    perimeter = bounds.perimeter
    if perimeter <= 0:
        return Position(bounds.left, bounds.top)

    distance %= perimeter
    w = bounds.width
    h = bounds.height
    if distance < w:
        return Position(round(bounds.left + distance), bounds.top)
    distance -= w
    if distance < h:
        return Position(bounds.right, round(bounds.top + distance))
    distance -= h
    if distance < w:
        return Position(round(bounds.right - distance), bounds.bottom)
    distance -= w
    return Position(bounds.left, round(bounds.bottom - distance))


@dataclass(frozen=True, slots=True)
class EdgeWalkMotion:
    """WalkMotion-compatible path that follows the rectangular screen perimeter."""

    origin: tuple[int, int]
    target: tuple[int, int]
    bounds: EdgeBounds
    start_coordinate: float
    travel_distance: float
    clockwise: bool
    cycle_duration_ms: int
    speed_px_per_second: float = 72.0

    @property
    def distance(self) -> float:
        return self.travel_distance

    @property
    def pixels_per_cycle(self) -> float:
        return self.speed_px_per_second * self.cycle_duration_ms / 1_000

    @property
    def cycles(self) -> int:
        return max(1, round(self.distance / self.pixels_per_cycle))

    @property
    def duration_ms(self) -> int:
        return self.cycles * self.cycle_duration_ms

    def progress(self, elapsed_ms: int) -> float:
        return min(1.0, max(0.0, elapsed_ms / self.duration_ms))

    def eased_progress(self, elapsed_ms: int) -> float:
        progress = self.progress(elapsed_ms)
        return progress * progress * (3.0 - 2.0 * progress)

    def position_at(self, elapsed_ms: int) -> tuple[int, int]:
        travelled = self.travel_distance * self.eased_progress(elapsed_ms)
        direction = 1.0 if self.clockwise else -1.0
        point = _point_at_perimeter(
            self.start_coordinate + direction * travelled,
            self.bounds,
        )
        return point.x, point.y

    def animation_progress(self, elapsed_ms: int) -> float:
        travelled = self.travel_distance * self.eased_progress(elapsed_ms)
        return (travelled / self.pixels_per_cycle) % 1.0


def build_edge_roam_motion(
    placement,
    origin: Position,
    *,
    travel_distance: float,
    clockwise: bool,
    cycle_duration_ms: int,
    speed_px_per_second: float,
):
    """Build a walk to the nearest edge, or a perimeter-following walk once there."""
    bounds = bounds_for_placement(placement, origin)
    if bounds is None or bounds.perimeter <= 0:
        return None

    edge_origin = nearest_edge_point(origin, bounds)
    approach_distance = math.hypot(edge_origin.x - origin.x, edge_origin.y - origin.y)
    if approach_distance > 1.0:
        return WalkMotion(
            origin=(origin.x, origin.y),
            target=(edge_origin.x, edge_origin.y),
            cycle_duration_ms=cycle_duration_ms,
            speed_px_per_second=speed_px_per_second,
        )

    start = _perimeter_coordinate(edge_origin, bounds)
    travel = max(WalkMotion.MIN_DISTANCE, float(travel_distance))
    direction = 1.0 if clockwise else -1.0
    target = _point_at_perimeter(start + direction * travel, bounds)
    return EdgeWalkMotion(
        origin=(edge_origin.x, edge_origin.y),
        target=(target.x, target.y),
        bounds=bounds,
        start_coordinate=start,
        travel_distance=travel,
        clockwise=clockwise,
        cycle_duration_ms=cycle_duration_ms,
        speed_px_per_second=speed_px_per_second,
    )
