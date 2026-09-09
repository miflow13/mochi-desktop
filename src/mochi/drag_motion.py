"""Small, testable motion model for Mochi's dragged visual response."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


@dataclass
class DragMotionModel:
    smoothing: float = 0.28
    max_velocity: float = 700.0
    lag_seconds: float = 0.012
    max_visual_offset: float = 6.0
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

    @property
    def visual_offset_x(self) -> float:
        return _clamp(
            -self.filtered_velocity_x * self.lag_seconds,
            -self.max_visual_offset,
            self.max_visual_offset,
        )

    @property
    def visual_offset_y(self) -> float:
        return _clamp(
            -self.filtered_velocity_y * self.lag_seconds,
            -self.max_visual_offset,
            self.max_visual_offset,
        )

    def settle(self) -> None:
        self.filtered_velocity_x *= 1.0 - self.smoothing
        self.filtered_velocity_y *= 1.0 - self.smoothing

    def reset(self) -> None:
        self.filtered_velocity_x = 0.0
        self.filtered_velocity_y = 0.0
        self._previous_x = None
        self._previous_y = None
        self._previous_time = None
