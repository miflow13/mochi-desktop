"""Visual-only bond XP particles rendered inside Mochi's sprite surface.

No extra GTK windows, widgets, controllers, or hit targets are created here.
Normal awards map one XP to one orb. Repeated dense rewards may coalesce their
visual backlog so spam cannot leave Mochi emitting particles long after the
interaction ends. Collection pulses and the level-up bloom are feedback only.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import cairo


ORB_EMIT_INTERVAL_SECONDS = 0.055
MAX_ACTIVE_ORBS = 12
MAX_ACTIVE_PULSES = 6
MAX_COLLECTION_PULSES_PER_FRAME = 2
DENSE_ORB_THRESHOLD = 7
GOLDEN_ANGLE_RADIANS = math.pi * (3.0 - math.sqrt(5.0))
MIN_ORB_DURATION_SECONDS = 0.72
MAX_ORB_DURATION_SECONDS = 0.95
COLLECTION_PULSE_DURATION_SECONDS = 0.34
LEVEL_UP_BLOOM_DURATION_SECONDS = 1.25
GAIN_MARKER_DURATION_SECONDS = 0.95
MAX_ACTIVE_GAIN_MARKERS = 3


def _coerce_positive_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass(slots=True)
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

        # Perpendicular curve peaks halfway through the trip and returns
        # exactly to the target, so XP feels gently pulled in rather than shot.
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
            return 0.98
        return max(0.0, 0.98 * (1.0 - (t - 0.78) / 0.22))

    @property
    def rendered_radius(self) -> float:
        """Shrink slightly as the orb is absorbed."""
        t = self.progress
        return max(0.9, self.radius * (1.0 - 0.38 * t))


@dataclass(slots=True)
class XpGainMarker:
    """Short floating text marker for one awarded XP event."""

    amount: int
    age_seconds: float
    duration_seconds: float
    drift: float

    @property
    def complete(self) -> bool:
        return self.age_seconds >= self.duration_seconds

    @property
    def progress(self) -> float:
        if self.duration_seconds <= 0:
            return 1.0
        return min(1.0, max(0.0, self.age_seconds / self.duration_seconds))

    @property
    def alpha(self) -> float:
        # Hold almost fully readable for the first beat, then fade away.
        t = self.progress
        if t < 0.22:
            return 1.0
        return max(0.0, 1.0 - (t - 0.22) / 0.78)

    def position(self, target_x: float, target_y: float, size: float) -> tuple[float, float]:
        """Float upward with a tiny sideways drift while fading."""
        t = self.progress
        eased = 1.0 - (1.0 - t) * (1.0 - t)
        x = target_x + size * (0.08 + self.drift * math.sin(math.pi * t))
        y = target_y - size * (0.20 + 0.16 * eased)
        return x, y


@dataclass(slots=True)
class XpCollectionPulse:
    """Short glow produced when one real XP orb reaches Mochi."""

    age_seconds: float
    duration_seconds: float
    base_radius: float

    @property
    def complete(self) -> bool:
        return self.age_seconds >= self.duration_seconds

    @property
    def progress(self) -> float:
        if self.duration_seconds <= 0:
            return 1.0
        return min(1.0, max(0.0, self.age_seconds / self.duration_seconds))

    @property
    def alpha(self) -> float:
        return max(0.0, 0.42 * (1.0 - self.progress))

    @property
    def radius(self) -> float:
        # Ease-out expansion makes collection feel crisp at the center and
        # softer at the edge.
        t = self.progress
        eased = 1.0 - (1.0 - t) * (1.0 - t)
        return self.base_radius * (1.0 + 2.4 * eased)


class XpOrbField:
    """Queue and animate bounded visual feedback for awarded bond XP."""

    def __init__(self, *, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._pending_xp = 0
        self._active: list[XpOrb] = []
        self._pulses: list[XpCollectionPulse] = []
        self._gain_markers: list[XpGainMarker] = []
        self._emit_accumulator = 0.0
        self._total_emitted = 0
        self._spawn_index = 0
        self._level_up_age: float | None = None

    @property
    def pending_xp(self) -> int:
        return self._pending_xp

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def outstanding_orb_count(self) -> int:
        """Particles still travelling or waiting to be emitted."""
        return len(self._active) + self._pending_xp

    @property
    def pulse_count(self) -> int:
        return len(self._pulses)

    @property
    def marker_count(self) -> int:
        return len(self._gain_markers)

    @property
    def total_emitted(self) -> int:
        return self._total_emitted

    @property
    def level_up_active(self) -> bool:
        return self._level_up_age is not None

    @property
    def has_activity(self) -> bool:
        return bool(
            self._pending_xp
            or self._active
            or self._pulses
            or self._gain_markers
            or self._level_up_age is not None
        )

    def queue_xp(self, amount: int) -> int:
        """Queue exactly one future orb per positive XP and return that amount."""
        queued = _coerce_positive_int(amount)
        if queued <= 0:
            return 0
        self._pending_xp += queued

        # The first XP should feel immediate rather than waiting for the first
        # emission interval. Large rewards still stream in at a bounded rate.
        if not self._active:
            self._emit_accumulator = max(
                self._emit_accumulator,
                ORB_EMIT_INTERVAL_SECONDS,
            )
        return queued

    def queue_xp_bounded(self, amount: int, *, max_outstanding: int) -> int:
        """Queue visual XP without letting repeated dense rewards grow forever.

        The returned value is the number of *visual* orbs accepted. Bond XP is
        owned by the caller and is never reduced by this presentation cap.
        """
        requested = _coerce_positive_int(amount)
        limit = _coerce_positive_int(max_outstanding)
        if requested <= 0 or limit <= 0:
            return 0

        available = max(0, limit - self.outstanding_orb_count)
        queued = min(requested, available)
        if queued <= 0:
            return 0
        return self.queue_xp(queued)

    def show_gain_marker(self, amount: int) -> int:
        """Show one floating label for this award without inventing extra XP."""
        shown = _coerce_positive_int(amount)
        if shown <= 0:
            return 0

        self._gain_markers.append(
            XpGainMarker(
                amount=shown,
                age_seconds=0.0,
                duration_seconds=GAIN_MARKER_DURATION_SECONDS,
                drift=self._rng.uniform(-0.045, 0.045),
            )
        )
        if len(self._gain_markers) > MAX_ACTIVE_GAIN_MARKERS:
            self._gain_markers = self._gain_markers[-MAX_ACTIVE_GAIN_MARKERS:]
        return shown

    def trigger_level_up(self) -> None:
        """Start a clean milestone bloom and retire stale dense-reward visual debt.

        Bond XP is already committed by the caller. Any pending swarm is only
        presentation debt, so carrying it into a milestone wastes frame budget
        and makes the level-up visually compete with old rewards.
        """
        self._pending_xp = 0
        self._active.clear()
        self._pulses.clear()
        self._gain_markers.clear()
        self._emit_accumulator = 0.0
        self._level_up_age = 0.0

    def advance(
        self,
        elapsed_seconds: float,
        *,
        width: float,
        height: float,
        target_x: float,
        target_y: float,
    ) -> bool:
        """Advance particles, collection pulses, and the level-up bloom."""
        elapsed = max(0.0, float(elapsed_seconds))
        changed = False

        # Advance pulses that already existed at the start of this frame.
        # Pulses created by orb collection below intentionally begin at age 0
        # and survive until the next tick, so even a delayed frame cannot skip
        # the visible "XP landed" moment entirely.
        if self._pulses:
            for pulse in self._pulses:
                pulse.age_seconds += elapsed
            before = len(self._pulses)
            self._pulses = [pulse for pulse in self._pulses if not pulse.complete]
            changed = changed or len(self._pulses) != before or elapsed > 0.0

        if self._active:
            completed: list[XpOrb] = []
            remaining: list[XpOrb] = []
            for orb in self._active:
                orb.age_seconds += elapsed
                if orb.complete:
                    completed.append(orb)
                else:
                    remaining.append(orb)
            self._active = remaining

            if completed:
                # A large reward can finish several orbs on the same frame.
                # The orbs still remain one-per-XP, but their decorative landing
                # rings are sampled so the center does not turn into a strobe.
                pulse_sources = completed[:MAX_COLLECTION_PULSES_PER_FRAME]
                for orb in pulse_sources:
                    self._pulses.append(
                        XpCollectionPulse(
                            age_seconds=0.0,
                            duration_seconds=COLLECTION_PULSE_DURATION_SECONDS,
                            base_radius=max(2.4, orb.radius * 0.95),
                        )
                    )
                if len(self._pulses) > MAX_ACTIVE_PULSES:
                    self._pulses = self._pulses[-MAX_ACTIVE_PULSES:]
            changed = bool(completed) or elapsed > 0.0

        if self._gain_markers:
            for marker in self._gain_markers:
                marker.age_seconds += elapsed
            before = len(self._gain_markers)
            self._gain_markers = [
                marker for marker in self._gain_markers if not marker.complete
            ]
            changed = changed or len(self._gain_markers) != before or elapsed > 0.0

        if self._level_up_age is not None:
            self._level_up_age += elapsed
            if self._level_up_age >= LEVEL_UP_BLOOM_DURATION_SECONDS:
                self._level_up_age = None
            changed = True

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
        size: float,
    ) -> None:
        """Paint satisfying but compact XP feedback over Mochi's sprite."""
        size = max(16.0, float(size))

        # A real level-up gets one larger bloom around Mochi. It is deliberately
        # a ring/glow rather than additional orbs so the 1 XP == 1 orb language
        # remains truthful.
        if self._level_up_age is not None:
            t = min(1.0, self._level_up_age / LEVEL_UP_BLOOM_DURATION_SECONDS)
            eased = 1.0 - (1.0 - t) * (1.0 - t)
            alpha = max(0.0, 0.52 * (1.0 - t))
            radius = size * (0.10 + 0.24 * eased)

            context.set_source_rgba(0.66, 1.0, 0.70, alpha * 0.22)
            context.arc(target_x, target_y, radius * 1.22, 0, 2 * math.pi)
            context.fill()

            context.set_source_rgba(0.82, 1.0, 0.72, alpha)
            context.set_line_width(max(1.2, size * 0.012))
            context.arc(target_x, target_y, radius, 0, 2 * math.pi)
            context.stroke()

        # Collection pulses make each orb visibly "land" without adding clutter
        # elsewhere on the desktop.
        for pulse in self._pulses:
            context.set_source_rgba(0.75, 1.0, 0.70, pulse.alpha * 0.26)
            context.arc(
                target_x,
                target_y,
                pulse.radius * 1.35,
                0,
                2 * math.pi,
            )
            context.fill()

            context.set_source_rgba(0.88, 1.0, 0.76, pulse.alpha)
            context.set_line_width(max(1.0, size * 0.008))
            context.arc(target_x, target_y, pulse.radius, 0, 2 * math.pi)
            context.stroke()

        dense_range = max(1, MAX_ACTIVE_ORBS - DENSE_ORB_THRESHOLD)
        density = min(
            1.0,
            max(0.0, (len(self._active) - DENSE_ORB_THRESHOLD) / dense_range),
        )
        radius_scale = 1.0 - 0.14 * density
        halo_scale = 2.80 - 0.42 * density
        halo_alpha = 0.36 - 0.13 * density
        rim_alpha = 0.55 - 0.10 * density

        for orb in self._active:
            x, y = orb.position(target_x, target_y)
            alpha = orb.alpha
            radius = orb.rendered_radius * radius_scale

            # Sparse rewards keep the plush glow. Dense rewards automatically
            # tighten halos and particles so the swarm stays legible instead of
            # becoming one bright green cloud.
            context.set_source_rgba(0.44, 0.90, 0.56, alpha * halo_alpha)
            context.arc(x, y, radius * halo_scale, 0, 2 * math.pi)
            context.fill()

            # A faint rim gives the particle a deliberate collectible shape.
            context.set_source_rgba(0.70, 1.0, 0.68, alpha * rim_alpha)
            context.set_line_width(max(0.8, radius * 0.24))
            context.arc(x, y, radius * 1.18, 0, 2 * math.pi)
            context.stroke()

            # Keep the body bright even when a large reward is on screen.
            context.set_source_rgba(0.80, 1.0, 0.66, alpha)
            context.arc(x, y, radius, 0, 2 * math.pi)
            context.fill()

            # Small highlight keeps orbs dimensional even at Mochi's 64px size.
            context.set_source_rgba(1.0, 1.0, 0.94, alpha * 0.96)
            context.arc(
                x - radius * 0.25,
                y - radius * 0.27,
                max(0.70, radius * 0.30),
                0,
                2 * math.pi,
            )
            context.fill()

        # Award text floats upward from Mochi and fades. It lives in the same
        # Cairo surface as the sprite, so it cannot steal focus or pointer input.
        for marker in self._gain_markers:
            text = f"+{marker.amount} XP"
            x, y = marker.position(target_x, target_y, size)
            alpha = marker.alpha
            font_size = max(8.0, min(14.0, size * 0.085))

            context.save()
            context.select_font_face(
                "Sans",
                cairo.FONT_SLANT_NORMAL,
                cairo.FONT_WEIGHT_BOLD,
            )
            context.set_font_size(font_size)
            extents = context.text_extents(text)
            try:
                x_bearing = extents.x_bearing
                width = extents.width
            except AttributeError:
                x_bearing, _, width, _, _, _ = extents

            context.move_to(x - width / 2 - x_bearing, y)
            context.text_path(text)
            context.set_line_width(max(1.0, size * 0.010))
            context.set_source_rgba(0.05, 0.12, 0.07, alpha * 0.58)
            context.stroke_preserve()
            context.set_source_rgba(0.82, 1.0, 0.70, alpha * 0.98)
            context.fill()
            context.restore()

    def _spawn_orb(
        self,
        *,
        width: float,
        height: float,
        target_x: float,
        target_y: float,
    ) -> XpOrb:
        size = max(16.0, min(float(width), float(height)))
        # Golden-angle spacing prevents a 60-XP reward from randomly bunching
        # most of its particles on one side of Mochi. Small jitter keeps the
        # stream organic instead of looking like a perfect geometric pattern.
        angle = (
            self._spawn_index * GOLDEN_ANGLE_RADIANS
            + self._rng.uniform(-0.10, 0.10)
        ) % (2 * math.pi)
        self._spawn_index += 1
        distance = self._rng.uniform(size * 0.33, size * 0.47)

        start_x = target_x + math.cos(angle) * distance
        start_y = target_y + math.sin(angle) * distance
        margin = max(2.0, size * 0.025)
        start_x = max(margin, min(float(width) - margin, start_x))
        start_y = max(margin, min(float(height) - margin, start_y))

        return XpOrb(
            start_x=start_x,
            start_y=start_y,
            sway=self._rng.uniform(-size * 0.12, size * 0.12),
            age_seconds=0.0,
            duration_seconds=self._rng.uniform(
                MIN_ORB_DURATION_SECONDS,
                MAX_ORB_DURATION_SECONDS,
            ),
            radius=max(2.2, size * self._rng.uniform(0.026, 0.040)),
        )
