"""Small, testable motion model for Mochi's dragged visual response."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from mochi.interaction_tuning import (
    DRAG_HEAVY_VELOCITY_PX_PER_SECOND,
    DRAG_MEDIUM_ENTER_THRESHOLD,
    DRAG_MEDIUM_EXIT_THRESHOLD,
    DRAG_SOFT_ENTER_THRESHOLD,
    DRAG_STATE_DWELL_MS,
    DRAG_VELOCITY_SMOOTHING,
)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


@dataclass
class DragPoseSelector:
    """Stateful pose selection with a quiet soft/medium hysteresis band."""

    soft_enter_threshold: float = DRAG_SOFT_ENTER_THRESHOLD
    medium_enter_threshold: float = DRAG_MEDIUM_ENTER_THRESHOLD
    medium_exit_threshold: float = DRAG_MEDIUM_EXIT_THRESHOLD
    dwell_ms: int = DRAG_STATE_DWELL_MS
    strength: str = "neutral"
    _last_strength_change: float | None = None

    def select(self, horizontal_intensity: float, timestamp: float) -> str:
        magnitude = abs(horizontal_intensity)
        if magnitude < self.soft_enter_threshold:
            candidate = "neutral"
        elif self.strength == "medium":
            candidate = (
                "medium" if magnitude >= self.medium_exit_threshold else "soft"
            )
        else:
            candidate = (
                "medium" if magnitude >= self.medium_enter_threshold else "soft"
            )

        changing_drag_strength = {candidate, self.strength} == {"soft", "medium"}
        inside_dwell = (
            self._last_strength_change is not None
            and (timestamp - self._last_strength_change) * 1_000 < self.dwell_ms
        )
        if changing_drag_strength and inside_dwell:
            candidate = self.strength
        elif candidate != self.strength:
            self.strength = candidate
            self._last_strength_change = timestamp

        if self.strength == "neutral":
            return "drag/drag_neutral.png"
        direction = "left" if horizontal_intensity > 0 else "right"
        return f"drag/drag_{direction}_{self.strength}.png"

    def reset(self) -> None:
        self.strength = "neutral"
        self._last_strength_change = None


def drag_settle_sprite(pose_sprite: str) -> str:
    """Choose the release pose that corresponds to the current drag pose."""
    if pose_sprite.startswith("drag/drag_left_"):
        return "drag/drag_settle_left.png"
    if pose_sprite.startswith("drag/drag_right_"):
        return "drag/drag_settle_right.png"
    return "drag/drag_settle_neutral.png"


@dataclass
class DragMotionModel:
    smoothing: float = DRAG_VELOCITY_SMOOTHING
    max_velocity: float = DRAG_HEAVY_VELOCITY_PX_PER_SECOND
    filtered_velocity_x: float = 0.0
    filtered_velocity_y: float = 0.0
    _previous_x: float | None = None
    _previous_y: float | None = None
    _previous_time: float | None = None
    pose_selector: DragPoseSelector = field(default_factory=DragPoseSelector)

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

    def pose_sprite(self) -> str:
        return self.pose_selector.select(
            self.horizontal_intensity,
            self._previous_time or 0.0,
        )

    def reset(self) -> None:
        self.filtered_velocity_x = 0.0
        self.filtered_velocity_y = 0.0
        self._previous_x = None
        self._previous_y = None
        self._previous_time = None
        self.pose_selector.reset()
