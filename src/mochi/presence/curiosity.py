"""Brief curiosity when Mochi notices a window switch or a settled browser tab."""

from __future__ import annotations

import math
import time

import cairo
from gi.repository import GLib

from mochi.state import MochiState, PresentationState

from .signals import AppCategorySignalAdapter


def _boottime_seconds(clock=time) -> float:
    """Seconds on a clock that keeps counting while the machine is suspended.

    ``time.monotonic()`` pauses during suspend, so overnight a long habituation
    streak would never reset and cooldowns would stretch across the sleep.
    """
    clock_id = getattr(clock, "CLOCK_BOOTTIME", None)
    if clock_id is not None:
        try:
            return clock.clock_gettime(clock_id)
        except OSError:
            pass
    return clock.monotonic()


class ActiveWindowCuriosityMixin:
    """Notice attention changes without claiming Mochi's behavior state.

    AmbiSense sends a coarse app category when window focus changes and a
    payload-free pulse each time the focused browser changes tab or page after
    user input; curiosity waits for those pulses to settle. Curiosity never
    reads window titles, application IDs, or screen content.

    Standing-idle Mochi borrows the idle-look lifecycle for one ``investigate``
    beat; otherwise he shows a short overlay cue. Neither path changes
    ``MochiState``. Reactions habituate during busy sessions.
    """

    CURIOSITY_DEBOUNCE_MS = 180
    CURIOSITY_TAB_SETTLE_MS = 1500
    CURIOSITY_BEAT_COOLDOWN_SECONDS = 120.0
    CURIOSITY_BEAT_COOLDOWN_CAP_SECONDS = 600.0
    CURIOSITY_CUE_COOLDOWN_SECONDS = 20.0
    CURIOSITY_CUE_COOLDOWN_CAP_SECONDS = 120.0
    CURIOSITY_HABITUATION_FACTOR = 1.5
    CURIOSITY_HABITUATION_RESET_SECONDS = 300.0
    CURIOSITY_CUE_DURATION_SECONDS = 1.8
    CURIOSITY_LEAN_PX = 4.0
    CURIOSITY_BUBBLE_MIN_SIZE_PX = 80
    CURIOSITY_BEAT_ANIMATION = "investigate"

    # One source of truth: curiosity reacts to exactly the categories the
    # AmbiSense adapter accepts, so the two lists cannot drift apart.
    _CURIOSITY_CATEGORIES = AppCategorySignalAdapter.ALLOWED
    _CURIOSITY_CUE_STATES = frozenset(
        (
            MochiState.IDLE,
            MochiState.BLINKING,
            MochiState.WALKING,
            MochiState.TYPING,
            MochiState.COMPUTER,
        )
    )
    _CURIOSITY_SLEEP_STATES = frozenset((MochiState.SLEEPING, MochiState.WAKING))

    # Class-level defaults: every value is immutable, and some tests build
    # production buddies with ``__new__`` without running mixin initializers.
    _curiosity_source_id: int | None = None
    _curiosity_pending_reason: str | None = None
    _curiosity_cue_active = False
    _curiosity_cue_started_at = 0.0
    _curiosity_last_trigger_at = -math.inf
    _curiosity_last_reaction_at = -math.inf
    _curiosity_last_beat_at = -math.inf
    _curiosity_streak = 0

    # -- Clock and pacing ---------------------------------------------------

    def _curiosity_now(self) -> float:
        return _boottime_seconds()

    @classmethod
    def _habituated_cooldown(cls, base: float, cap: float, streak: int) -> float:
        """Stretch a cooldown for each recent reaction, up to its cap."""
        # 1.5 ** 16 is far past both caps; clamping keeps a very long streak
        # from overflowing the float power.
        exponent = min(max(0, streak), 16)
        return min(base * cls.CURIOSITY_HABITUATION_FACTOR ** exponent, cap)

    # -- Triggers -------------------------------------------------------------

    def _on_presence_app_focus_changed(self, category: str) -> None:
        super()._on_presence_app_focus_changed(category)
        if category in self._CURIOSITY_CATEGORIES:
            # A quick Alt-Tab pass should not flash a reaction.
            self._schedule_curiosity(self.CURIOSITY_DEBOUNCE_MS, f"window:{category}")

    def _on_presence_browser_tab_changed(self) -> None:
        super()._on_presence_browser_tab_changed()
        # Every pulse restarts the settle, so flicking through tabs produces
        # one reaction once the user lands.
        self._schedule_curiosity(self.CURIOSITY_TAB_SETTLE_MS, "tab")

    def _schedule_curiosity(self, delay_ms: int, reason: str) -> None:
        """Replace any pending trigger; the latest attention change wins."""
        self._cancel_curiosity_source()
        if getattr(self, "_presence_shutting_down", False) or getattr(
            self, "_preview_mode", False
        ):
            return
        self._curiosity_pending_reason = reason
        self._curiosity_source_id = GLib.timeout_add(delay_ms, self._fire_curiosity)

    def _fire_curiosity(self) -> bool:
        self._curiosity_source_id = None
        reason = self._curiosity_pending_reason
        self._curiosity_pending_reason = None
        if reason is not None:
            self._react_to_curiosity(reason)
        return GLib.SOURCE_REMOVE

    def _cancel_curiosity_source(self) -> None:
        source_id = self._curiosity_source_id
        self._curiosity_source_id = None
        self._curiosity_pending_reason = None
        if source_id is None:
            return
        try:
            GLib.source_remove(source_id)
        except Exception:
            pass

    # -- Decision -------------------------------------------------------------

    def _curiosity_suppression(self) -> str | None:
        """Name the rule that silences curiosity right now, or ``None``."""
        for attribute, cause in (
            ("_preview_mode", "preview"),
            ("_presence_shutting_down", "shutting down"),
            ("_user_idle", "user idle"),
            ("_context_menu_open", "context menu"),
            ("_drag_started", "dragging"),
        ):
            if getattr(self, attribute, False):
                return cause
        if getattr(self, "_press", None) is not None:
            return "pressed"
        # Same quiet-focus rule as other presence reactions
        # (FocusSessionMixin._focus_allows_presence_action). Focus work runs as
        # COMPUTER, a cue-allowed state, so the state checks below miss it.
        for predicate_name in ("_focus_should_work", "_focus_should_think"):
            predicate = getattr(self, predicate_name, None)
            if callable(predicate) and predicate():
                return "focus session"
        state = getattr(self, "state", None)
        if state is None:
            return "no state"
        if state.presentation is not PresentationState.NORMAL:
            return f"presentation {state.presentation.name}"
        if state.current in self._CURIOSITY_SLEEP_STATES:
            return "sleeping"
        engine = getattr(self, "_ambient_presence_engine", None)
        tuning = getattr(engine, "tuning", None)
        if tuning is None:
            return None
        if not getattr(tuning, "ambient_reactions_enabled", True):
            return "ambient reactions off"
        if getattr(tuning, "quiet_mode", False):
            return "quiet mode"
        return None

    def _curiosity_allowed(self) -> bool:
        return self._curiosity_suppression() is None

    def _curiosity_cue_allowed(self) -> bool:
        return (
            self._curiosity_allowed()
            and self.state.current in self._CURIOSITY_CUE_STATES
        )

    def _react_to_curiosity(self, reason: str) -> str:
        """Take the first allowed reaction: ``"beat"``, ``"cue"``, or ``"drop"``."""
        suppression = self._curiosity_suppression()
        if suppression is not None:
            # Suppressed triggers never count toward habituation.
            return self._curiosity_drop(reason, f"suppressed: {suppression}")

        now = self._curiosity_now()
        if (
            now - self._curiosity_last_trigger_at
            >= self.CURIOSITY_HABITUATION_RESET_SECONDS
        ):
            self._curiosity_streak = 0
        self._curiosity_last_trigger_at = now

        streak = self._curiosity_streak
        reaction_gap = self._habituated_cooldown(
            self.CURIOSITY_CUE_COOLDOWN_SECONDS,
            self.CURIOSITY_CUE_COOLDOWN_CAP_SECONDS,
            streak,
        )
        waited = now - self._curiosity_last_reaction_at
        if waited < reaction_gap:
            return self._curiosity_drop(
                reason, f"cooldown, {math.ceil(reaction_gap - waited)}s left"
            )

        beat_cooldown = self._habituated_cooldown(
            self.CURIOSITY_BEAT_COOLDOWN_SECONDS,
            self.CURIOSITY_BEAT_COOLDOWN_CAP_SECONDS,
            streak,
        )
        if now - self._curiosity_last_beat_at >= beat_cooldown and self._play_idle_beat(
            self.CURIOSITY_BEAT_ANIMATION
        ):
            self._curiosity_last_beat_at = now
            reaction = "beat"
        elif self._curiosity_cue_allowed():
            self._curiosity_cue_active = True
            self._curiosity_cue_started_at = now
            self.queue_draw()
            reaction = "cue"
        else:
            return self._curiosity_drop(reason, f"state {self.state.current.name}")

        self._curiosity_last_reaction_at = now
        self._curiosity_streak = streak + 1
        logger = getattr(self, "_logger", None)
        if logger is not None:
            logger.debug(
                "[curiosity] %s -> %s (streak=%d)",
                reason,
                reaction,
                self._curiosity_streak,
            )
        return reaction

    def _curiosity_drop(self, reason: str, cause: str) -> str:
        """Log why a trigger produced nothing, so ``--debug`` explains silence."""
        logger = getattr(self, "_logger", None)
        if logger is not None:
            logger.debug("[curiosity] %s -> drop (%s)", reason, cause)
        return "drop"

    def _clear_curiosity_cue(self) -> None:
        if not self._curiosity_cue_active:
            return
        self._curiosity_cue_active = False
        self.queue_draw()

    # -- Lifecycle hooks ------------------------------------------------------

    def _on_pressed(self, *args) -> None:
        self._cancel_curiosity_source()
        self._clear_curiosity_cue()
        super()._on_pressed(*args)

    def _tick(self) -> bool:
        result = super()._tick()
        if not self._curiosity_cue_active:
            return result
        if not self._curiosity_cue_allowed() or self._curiosity_progress() is None:
            self._clear_curiosity_cue()
            return result
        self.queue_draw()
        return result

    def shutdown_presence(self) -> None:
        self._cancel_curiosity_source()
        self._curiosity_cue_active = False
        super().shutdown_presence()

    # -- Rendering --------------------------------------------------------------

    def _curiosity_progress(self, now: float | None = None) -> float | None:
        if not self._curiosity_cue_active:
            return None
        if now is None:
            now = self._curiosity_now()
        started_at = self._curiosity_cue_started_at
        duration = self.CURIOSITY_CUE_DURATION_SECONDS
        # Compare against the deadline itself: ``now - started_at >= duration``
        # can round just below ``duration`` when ``now == started_at + duration``.
        if now >= started_at + duration:
            return None
        return max(0.0, now - started_at) / duration

    @staticmethod
    def _curiosity_alpha(progress: float) -> float:
        """Ease the cue in quickly, hold it, then let it disappear quietly."""
        if progress < 0.12:
            return max(0.0, progress / 0.12)
        if progress <= 0.68:
            return 1.0
        return max(0.0, 1.0 - ((progress - 0.68) / 0.32))

    @staticmethod
    def _curiosity_lean_factor(progress: float) -> float:
        """Small physical perk that never mutates Mochi's actual position."""
        if progress < 0.18:
            return math.sin((progress / 0.18) * (math.pi / 2))
        if progress <= 0.68:
            return 1.0
        tail = min(1.0, (progress - 0.68) / 0.32)
        return math.cos(tail * (math.pi / 2))

    def _curiosity_lean_offsets(
        self, progress: float, direction: int, scale: float
    ) -> tuple[int, int]:
        """Whole-pixel lean: SpriteAtlas samples nearest-neighbor from rounded
        placement, so a fractional translate would make the pixel art shimmer."""
        factor = self._curiosity_lean_factor(progress)
        return (
            round(direction * self.CURIOSITY_LEAN_PX * scale * factor),
            round(-1.0 * scale * factor),
        )

    def _curiosity_direction(self, width: int) -> int:
        """Lean toward screen center without requesting focused-window geometry.

        The AmbiSense contract exposes only a coarse app category. Using
        Mochi's own monitor-relative placement gives the cue a directional feel
        while preserving that privacy boundary.
        """
        placement = getattr(self, "_placement", None)
        position = getattr(placement, "position", None)
        if placement is None or position is None:
            return 1

        try:
            monitor = placement._monitor_for_position(position.x, position.y)
            if monitor is None:
                return 1
            geometry = monitor.get_geometry()
            if getattr(placement, "layer_shell_enabled", False):
                mochi_center = position.x + width / 2
                monitor_center = geometry.width / 2
            else:
                scale = placement._x11_coordinate_scale()
                mochi_center = position.x / max(scale, 0.001) + width / 2
                monitor_center = geometry.x + geometry.width / 2
            return 1 if mochi_center < monitor_center else -1
        except Exception:
            return 1

    def _draw(self, area, context, width: int, height: int) -> None:
        progress = self._curiosity_progress()
        if progress is None:
            super()._draw(area, context, width, height)
            return

        direction = self._curiosity_direction(width)
        scale = max(0.5, min(width, height) / 112.0)
        lean_x, lean_y = self._curiosity_lean_offsets(progress, direction, scale)

        context.save()
        context.translate(lean_x, lean_y)
        super()._draw(area, context, width, height)
        context.restore()

        # Below this size the glyph is an unreadable blob; the lean alone
        # still reads as a little "huh?".
        if min(width, height) >= self.CURIOSITY_BUBBLE_MIN_SIZE_PX:
            self._draw_curiosity_bubble(
                context,
                width=width,
                direction=direction,
                alpha=self._curiosity_alpha(progress),
                scale=scale,
            )

    def _draw_curiosity_bubble(
        self,
        context,
        *,
        width: int,
        direction: int,
        alpha: float,
        scale: float,
    ) -> None:
        """Thought bubble with a tiny magnifying glass that echoes the beat.

        The bubble carries its own light fill and dark outline, so it stays
        readable on any wallpaper or theme.
        """
        if alpha <= 0.0:
            return

        bubble_w = 26.0 * scale
        bubble_h = 22.0 * scale
        center_x = width * 0.5 + direction * 19.0 * scale
        x = max(3.0 * scale, min(center_x - bubble_w / 2, width - bubble_w - 3.0 * scale))
        y = 7.0 * scale

        context.save()
        self._rounded_rect(context, x, y, bubble_w, bubble_h, 7.0 * scale)
        context.set_source_rgba(0.96, 0.98, 0.94, 0.94 * alpha)
        context.fill_preserve()
        context.set_source_rgba(0.12, 0.24, 0.17, 0.78 * alpha)
        context.set_line_width(max(1.0, 1.25 * scale))
        context.stroke()

        # Two small thought dots point the cue back toward Mochi.
        tail_x = x + bubble_w * (0.35 if direction > 0 else 0.65)
        for dx, dy, radius_scale in (
            (-2.0 * direction, 4.0, 1.8),
            (-5.0 * direction, 9.0, 1.2),
        ):
            context.new_sub_path()
            context.arc(
                tail_x + dx * scale,
                y + bubble_h + dy * scale,
                radius_scale * scale,
                0,
                math.tau,
            )
            context.set_source_rgba(0.96, 0.98, 0.94, 0.90 * alpha)
            context.fill_preserve()
            context.set_source_rgba(0.12, 0.24, 0.17, 0.66 * alpha)
            context.set_line_width(max(0.8, scale))
            context.stroke()

        # Magnifying glass: a lens ring with a short handle to the lower right.
        lens_radius = 5.0 * scale
        lens_x = x + bubble_w / 2 - 1.5 * scale
        lens_y = y + bubble_h / 2 - 1.5 * scale
        context.set_source_rgba(0.09, 0.18, 0.12, 0.92 * alpha)
        context.set_line_width(max(1.0, 1.8 * scale))
        context.new_sub_path()
        context.arc(lens_x, lens_y, lens_radius, 0, math.tau)
        context.stroke()
        handle_x = lens_x + lens_radius * math.cos(math.pi / 4)
        handle_y = lens_y + lens_radius * math.sin(math.pi / 4)
        context.set_line_width(max(1.0, 2.2 * scale))
        context.set_line_cap(cairo.LINE_CAP_ROUND)
        context.move_to(handle_x, handle_y)
        context.line_to(handle_x + 4.0 * scale, handle_y + 4.0 * scale)
        context.stroke()
        context.restore()

    @staticmethod
    def _rounded_rect(
        context,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float,
    ) -> None:
        radius = min(radius, width / 2, height / 2)
        context.new_sub_path()
        context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
        context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        context.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
        context.close_path()
