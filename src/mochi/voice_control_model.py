"""Pure logic for the "Talk to Mochi" control: motion, placement, visibility.

Kept free of GTK so the timing, geometry, and hit-testing rules from the
voice-control design spec are unit-testable. All sizes are logical pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


BUTTON_SIZE = 48
BUTTON_RADIUS = BUTTON_SIZE / 2
GAP_PX = 12
INSET_PX = 8

BAR_CENTERS_X = (14.0, 19.0, 24.0, 29.0, 34.0)
BAR_WIDTH = 3.0
IDLE_HEIGHTS = (6.0, 12.0, 20.0, 12.0, 6.0)

HOVER_LOOP_MS = 960
_HOVER_KEYFRAMES = (
    (0, IDLE_HEIGHTS),
    (240, (10.0, 18.0, 12.0, 8.0, 14.0)),
    (480, (16.0, 10.0, 8.0, 18.0, 10.0)),
    (720, (8.0, 14.0, 18.0, 10.0, 6.0)),
    (960, IDLE_HEIGHTS),
)
SETTLE_MS = 160


def _ease(fraction: float) -> float:
    return (1 - math.cos(math.pi * fraction)) / 2


def _mix(start: tuple[float, ...], end: tuple[float, ...], amount: float) -> tuple[float, ...]:
    return tuple(a + (b - a) * amount for a, b in zip(start, end))


def bar_heights_at(elapsed_ms: float) -> tuple[float, ...]:
    """Bar heights at a point in the repeating 960 ms hover loop."""
    position = elapsed_ms % HOVER_LOOP_MS
    if elapsed_ms > 0 and position == 0:
        return IDLE_HEIGHTS
    for (start_ms, start), (end_ms, end) in zip(_HOVER_KEYFRAMES, _HOVER_KEYFRAMES[1:]):
        if start_ms <= position <= end_ms:
            return _mix(start, end, _ease((position - start_ms) / (end_ms - start_ms)))
    return IDLE_HEIGHTS


def settle_heights(current: tuple[float, ...], fraction: float) -> tuple[float, ...]:
    """Ease from the pose hover left off at back to the idle pose."""
    return _mix(current, IDLE_HEIGHTS, _ease(min(max(fraction, 0.0), 1.0)))


def inside_button(x: float, y: float) -> bool:
    """True when a point in the 48 x 48 box lies on the visible circle."""
    return math.hypot(x - BUTTON_RADIUS, y - BUTTON_RADIUS) <= BUTTON_RADIUS


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class Placement:
    x: float
    y: float
    side: str


def place_control(
    sprite: Rect,
    work_area: Rect,
    *,
    reserve_below: float = 0.0,
    side: str | None = None,
) -> Placement:
    """Top-left of the button: under Mochi, else beside him, inside the work area.

    ``reserve_below`` is extra room needed under the button (its label), so
    "under" is only chosen when the label fits too. Passing ``side`` keeps a
    previously chosen side, so a walking Mochi does not make it flip.
    """
    size = BUTTON_SIZE
    left_limit = work_area.x + INSET_PX
    right_limit = work_area.right - INSET_PX - size
    top_limit = work_area.y + INSET_PX
    bottom_limit = work_area.bottom - INSET_PX - size

    under_y = sprite.bottom + GAP_PX
    beside_y = _clamp(sprite.y + sprite.height / 3 - size / 2, top_limit, bottom_limit)
    right_x = sprite.right + GAP_PX
    left_x = sprite.x - GAP_PX - size

    if side is None:
        if under_y + size + reserve_below <= work_area.bottom - INSET_PX:
            side = "under"
        elif right_x <= right_limit:
            side = "right"
        else:
            side = "left"

    if side == "under":
        x = sprite.x + sprite.width / 2 - size / 2
        return Placement(
            _clamp(x, left_limit, right_limit),
            _clamp(under_y, top_limit, bottom_limit),
            "under",
        )
    if side == "right":
        return Placement(_clamp(right_x, left_limit, right_limit), beside_y, "right")
    return Placement(_clamp(left_x, left_limit, right_limit), beside_y, "left")


PANEL_GAP_PX = 10


def place_panel(
    button: Rect, size: tuple[float, float], work_area: Rect
) -> tuple[float, float]:
    """Top-left of the coming-soon panel: beside the button, toward free space.

    Tries below, right, left, then above the button with a 10 px gap, and
    takes the first that fits inside the work area; otherwise clamps "below".
    """
    width, height = size
    center_x = button.x + button.width / 2
    center_y = button.y + button.height / 2
    candidates = (
        (center_x - width / 2, button.bottom + PANEL_GAP_PX),
        (button.right + PANEL_GAP_PX, center_y - height / 2),
        (button.x - PANEL_GAP_PX - width, center_y - height / 2),
        (center_x - width / 2, button.y - PANEL_GAP_PX - height),
    )
    left = work_area.x + INSET_PX
    top = work_area.y + INSET_PX
    right = work_area.right - INSET_PX - width
    bottom = work_area.bottom - INSET_PX - height

    def fits_after_clamping(x: float, y: float) -> bool:
        # Sliding along the edge is fine; overlapping the button is not.
        x, y = _clamp(x, left, right), _clamp(y, top, bottom)
        return (
            x + width <= button.x
            or x >= button.right
            or y + height <= button.y
            or y >= button.bottom
        ) and left <= x <= right and top <= y <= bottom

    for x, y in candidates:
        if fits_after_clamping(x, y):
            return _clamp(x, left, right), _clamp(y, top, bottom)
    x, y = candidates[0]
    return _clamp(x, left, right), _clamp(y, top, bottom)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


class VisibilityTracker:
    """Show while any interaction source is active, plus a short grace period.

    The grace period is the "transit corridor": leaving Mochi to reach the
    button, 12 px away, must not hide the button on the way.
    """

    def __init__(self, *, grace_seconds: float = 0.35) -> None:
        self._grace = grace_seconds
        self._active: set[str] = set()
        self._last_active: float | None = None
        self._dragging = False

    def set_source(self, source: str, active: bool, *, now: float) -> None:
        if active:
            self._active.add(source)
        elif source in self._active:
            self._active.discard(source)
            if not self._active:
                self._last_active = now

    def set_dragging(self, dragging: bool) -> None:
        self._dragging = dragging

    def visible(self, *, now: float) -> bool:
        if self._dragging:
            return False
        if self._active:
            return True
        return self._last_active is not None and now - self._last_active < self._grace

    def clear(self) -> None:
        self._active.clear()
        self._last_active = None
