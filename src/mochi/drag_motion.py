"""Small, testable motion model for Mochi's dragged visual response."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def drag_pose_sprite(horizontal_intensity: float) -> str:
    """Choose a drag pose without depending on manifest frame positions."""
    magnitude = abs(horizontal_intensity)
    if magnitude < 0.20:
        return "drag/drag_neutral.png"
    direction = "left" if horizontal_intensity > 0 else "right"
    strength = "soft" if magnitude < 0.35 else "medium"
    return f"drag/drag_{direction}_{strength}.png"


def drag_settle_sprite(pose_sprite: str) -> str:
    """Choose the release pose that corresponds to the current drag pose."""
    if pose_sprite.startswith("drag/drag_left_"):
        return "drag/drag_settle_left.png"
    if pose_sprite.startswith("drag/drag_right_"):
        return "drag/drag_settle_right.png"
    return "drag/drag_settle_neutral.png"


@dataclass
class DragMotionModel:
    smoothing: float = 0.28
    max_velocity: float = 700.0
    filtered_velocity_x: float = 0.0
    filtered_velocity_y: float = 0.0
    _previous_x: float | None = None
    _previous_y: float | None = None
    _previous_time: float | None = None

    def begin(self, x: float, y: float, timestamp: float) -> None:
        self._previous_x = x
        self._previous_y = y
        self._previous_time = timestamp
        self.filtered_velocity_x = 0.0
        self.filtered_velocity_y = 0.0

    def update(self, x: float, y: float, timestamp: float) -> None:
        if self._previous_time is None:
            self.begin(x, y, timestamp)
            return
        elapsed = timestamp - self._previous_time
        if elapsed <= 0:
            return
        velocity_x = (x - self._previous_x) / elapsed
        velocity_y = (y - self._previous_y) / elapsed
        self.filtered_velocity_x += self.smoothing * (
            velocity_x - self.filtered_velocity_x
        )
        self.filtered_velocity_y += self.smoothing * (
            velocity_y - self.filtered_velocity_y
        )
        self._previous_x = x
        self._previous_y = y
        self._previous_time = timestamp

    @property
    def horizontal_intensity(self) -> float:
        return _clamp(self.filtered_velocity_x / self.max_velocity, -1.0, 1.0)

    @property
    def leg_sway(self) -> float:
        return -self.horizontal_intensity

    @property
    def body_sway(self) -> float:
        return self.leg_sway * 0.45

    @property
    def speed(self) -> float:
        return math.hypot(self.filtered_velocity_x, self.filtered_velocity_y)

    def settle(self) -> None:
        self.filtered_velocity_x *= 1.0 - self.smoothing
        self.filtered_velocity_y *= 1.0 - self.smoothing

    def reset(self) -> None:
        self.filtered_velocity_x = 0.0
        self.filtered_velocity_y = 0.0
        self._previous_x = None
        self._previous_y = None
        self._previous_time = None
