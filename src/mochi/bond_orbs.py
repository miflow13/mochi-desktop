"""Tiny XP particles drawn inside Mochi's existing sprite surface.

The particle field is presentation-only. It never creates a GTK window, widget,
controller, hit target, or state-machine transition. One queued XP always maps
to one orb.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import cairo


ORB_EMIT_INTERVAL_SECONDS = 0.04
MAX_ACTIVE_ORBS = 24
MIN_ORB_DURATION_SECONDS = 0.72
MAX_ORB_DURATION_SECONDS = 0.95


def _coerce_positive_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass
class XpOrb:
    """One XP particle travelling from Mochi's perimeter into the body."""

    start_x: float
    start_y: float
    sway: float
    age_seconds: float
    duration_seconds: float
    radius: float

    @property
    def complete(self) -> bool:
        return self.age_seconds >= self.duration_seconds

    @property
    def progress(self) -> float:
        if self.duration_seconds <= 0:
            return 1.0
        return min(1.0, max(0.0, self.age_seconds / self.duration_seconds))

    def position(self, target_x: float, target_y: float) -> tuple[float, float]:
        """Return a curved, accelerating attraction path toward Mochi."""
        t = self.progress
        attraction = t * t
        dx = target_x - self.start_x
        dy = target_y - self.start_y
        distance = max(1.0, math.hypot(dx, dy))

        # Perpendicular curve that peaks halfway through the trip and returns
        # exactly to the target, giving the orb a soft float instead of a line.
        perpendicular_x = -dy / distance
        perpendicular_y = dx / distance
        curve = math.sin(math.pi * t) * self.sway

        x = self.start_x + dx * attraction + perpendicular_x * curve
        y = self.start_y + dy * attraction + perpendicular_y * curve
        return x, y

    @property
    def alpha(self) -> float:
        """Stay readable until collection, then softly disappear into Mochi."""
        t = self.progress
        if t >= 1.0:
            return 0.0
        if t < 0.78:
            return 0.92
        return max(0.0, 0.92 * (1.0 - (t - 0.78) / 0.22))

    @property
    def rendered_radius(self) -> float:
        """Shrink slightly as the orb is absorbed."""
        t = self.progress
        return max(0.7, self.radius * (1.0 - 0.45 * t))


class XpOrbField:
    """Queue and animate one visual orb for every awarded bond XP."""

    def __init__(self, *, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._pending_xp = 0
        self._active: list[XpOrb] = []
        self._emit_accumulator = 0.0
        self._total_emitted = 0

    @property
    def pending_xp(self) -> int:
        return self._pending_xp

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def total_emitted(self) -> int:
        return self._total_emitted

    @property
    def has_activity(self) -> bool:
        return bool(self._pending_xp or self._active)

    def queue_xp(self, amount: int) -> int:
        """Queue exactly one future orb per positive XP and return that amount."""
        queued = _coerce_positive_int(amount)
        if queued <= 0:
            return 0
        self._pending_xp += queued

        # The first XP should feel immediate rather than waiting for the first
        # emission interval. Larger rewards still stream in at a bounded rate.
        if not self._active:
            self._emit_accumulator = max(
                self._emit_accumulator,
                ORB_EMIT_INTERVAL_SECONDS,
            )
        return queued

    def advance(
        self,
        elapsed_seconds: float,
        *,
        width: float,
        height: float,
        target_x: float,
        target_y: float,
    ) -> bool:
        """Advance particles and emit a bounded number from the XP queue."""
        elapsed = max(0.0, float(elapsed_seconds))
        changed = False

        if self._active:
            for orb in self._active:
                orb.age_seconds += elapsed
            before = len(self._active)
            self._active = [orb for orb in self._active if not orb.complete]
            changed = changed or len(self._active) != before or elapsed > 0.0

        if self._pending_xp > 0:
            self._emit_accumulator += elapsed

        while (
            self._pending_xp > 0
            and len(self._active) < MAX_ACTIVE_ORBS
            and self._emit_accumulator >= ORB_EMIT_INTERVAL_SECONDS
        ):
            self._emit_accumulator -= ORB_EMIT_INTERVAL_SECONDS
            self._active.append(
                self._spawn_orb(
                    width=width,
                    height=height,
                    target_x=target_x,
                    target_y=target_y,
                )
            )
            self._pending_xp -= 1
            self._total_emitted += 1
            changed = True

        if not self.has_activity:
            self._emit_accumulator = 0.0

        return changed

    def draw(
        self,
        context: cairo.Context,
        *,
        target_x: float,
        target_y: float,
    ) -> None:
        """Paint soft green XP lights over the existing Mochi sprite."""
        for orb in self._active:
            x, y = orb.position(target_x, target_y)
            alpha = orb.alpha
            radius = orb.rendered_radius

            # Gentle halo.
            context.set_source_rgba(0.48, 0.86, 0.58, alpha * 0.25)
            context.arc(x, y, radius * 2.15, 0, 2 * math.pi)
            context.fill()

            # Bright XP body.
            context.set_source_rgba(0.77, 0.96, 0.62, alpha)
            context.arc(x, y, radius, 0, 2 * math.pi)
            context.fill()

            # Tiny highlight keeps small orbs legible at 64 px.
            context.set_source_rgba(1.0, 1.0, 0.90, alpha * 0.88)
            context.arc(
                x - radius * 0.28,
                y - radius * 0.28,
                max(0.55, radius * 0.28),
                0,
                2 * math.pi,
            )
            context.fill()

    def _spawn_orb(
        self,
        *,
        width: float,
        height: float,
        target_x: float,
        target_y: float,
    ) -> XpOrb:
        size = max(16.0, min(float(width), float(height)))
        angle = self._rng.uniform(0.0, 2 * math.pi)
        distance = self._rng.uniform(size * 0.30, size * 0.44)

        start_x = target_x + math.cos(angle) * distance
        start_y = target_y + math.sin(angle) * distance
        margin = max(2.0, size * 0.025)
        start_x = max(margin, min(float(width) - margin, start_x))
        start_y = max(margin, min(float(height) - margin, start_y))

        return XpOrb(
            start_x=start_x,
            start_y=start_y,
            sway=self._rng.uniform(-size * 0.11, size * 0.11),
            age_seconds=0.0,
            duration_seconds=self._rng.uniform(
                MIN_ORB_DURATION_SECONDS,
                MAX_ORB_DURATION_SECONDS,
            ),
            radius=max(1.6, size * self._rng.uniform(0.018, 0.026)),
        )
