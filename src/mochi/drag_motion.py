"""Two-dimensional, testable velocity model for Mochi's dragged visuals."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


@dataclass(frozen=True)
class DragVisual:
    pose: str
    speed: float
    direction_x: float
    direction_y: float


@dataclass
class DragMotionModel:
    """Smooth noisy samples and expose a stable, quantized 2D drag pose."""

    response_seconds: float = 0.075
    decay_seconds: float = 0.14
    dead_zone: float = 45.0
    medium_threshold: float = 0.24
    strong_threshold: float = 0.56
    max_velocity: float = 1_200.0
    filtered_velocity_x: float = 0.0
    filtered_velocity_y: float = 0.0
    _previous_x: float | None = None
    _previous_y: float | None = None
    _previous_time: float | None = None
    _level: int = 0

    def begin(self, x: float, y: float, timestamp: float) -> None:
        self._previous_x = x
        self._previous_y = y
        self._previous_time = timestamp
        self.filtered_velocity_x = 0.0
        self.filtered_velocity_y = 0.0
        self._level = 0

    def update(self, x: float, y: float, timestamp: float) -> None:
        if self._previous_time is None:
            self.begin(x, y, timestamp)
            return
        elapsed = timestamp - self._previous_time
        if elapsed <= 0:
            return
        velocity_x = (x - self._previous_x) / elapsed
        velocity_y = (y - self._previous_y) / elapsed
        magnitude = math.hypot(velocity_x, velocity_y)
        if magnitude > self.max_velocity:
            scale = self.max_velocity / magnitude
            velocity_x *= scale
            velocity_y *= scale
        alpha = 1.0 - math.exp(-elapsed / self.response_seconds)
        self.filtered_velocity_x += alpha * (velocity_x - self.filtered_velocity_x)
        self.filtered_velocity_y += alpha * (velocity_y - self.filtered_velocity_y)
        self._previous_x = x
        self._previous_y = y
        self._previous_time = timestamp

    @property
    def speed(self) -> float:
        magnitude = math.hypot(self.filtered_velocity_x, self.filtered_velocity_y)
        return _clamp(
            (magnitude - self.dead_zone) / (self.max_velocity - self.dead_zone),
            0.0,
            1.0,
        )

    @property
    def direction(self) -> tuple[float, float]:
        magnitude = math.hypot(self.filtered_velocity_x, self.filtered_velocity_y)
        if magnitude <= self.dead_zone:
            return (0.0, 0.0)
        return (
            self.filtered_velocity_x / magnitude,
            self.filtered_velocity_y / magnitude,
        )

    def visual(self) -> DragVisual:
        speed = self.speed
        if self._level == 0:
            self._level = (
                3
                if speed >= self.strong_threshold
                else 2
                if speed >= self.medium_threshold
                else 1
                if speed >= 0.07
                else 0
            )
        elif self._level == 1:
            if speed < 0.045:
                self._level = 0
            elif speed >= self.medium_threshold:
                self._level = 2
        elif self._level == 2:
            if speed < self.medium_threshold - 0.07:
                self._level = 1
            elif speed >= self.strong_threshold:
                self._level = 3
        elif speed < self.strong_threshold - 0.10:
            self._level = 2

        direction_x, direction_y = self.direction
        if self._level == 0:
            return DragVisual("neutral", speed, direction_x, direction_y)

        sector = round(math.atan2(direction_y, direction_x) / (math.pi / 4)) % 8
        directions = (
            "right", "down_right", "down", "down_left",
            "left", "up_left", "up", "up_right",
        )
        strength = ("gentle", "medium", "strong")[self._level - 1]
        return DragVisual(
            f"move_{directions[sector]}_{strength}",
            speed,
            direction_x,
            direction_y,
        )

    def settle(self, elapsed: float = 0.016) -> None:
        decay = math.exp(-elapsed / self.decay_seconds)
        self.filtered_velocity_x *= decay
        self.filtered_velocity_y *= decay

    def reset(self) -> None:
        self.filtered_velocity_x = 0.0
        self.filtered_velocity_y = 0.0
        self._previous_x = None
        self._previous_y = None
        self._previous_time = None
        self._level = 0
