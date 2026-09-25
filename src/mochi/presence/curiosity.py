"""Transient visual feedback when Mochi notices a focused app-category change."""

from __future__ import annotations

import math
import time

from gi.repository import GLib

from mochi.state import MochiState, PresentationState


class ActiveWindowCuriosityMixin:
    """Show a lightweight nonverbal curiosity cue without claiming behavior state.

    AmbiSense already receives only coarse focused-app categories. This layer keeps
    that privacy boundary intact: it never reads a window title, application ID,
    or screen content. Curiosity is presentation-only, so existing animation/state
    owners continue running underneath it.
    """

    CURIOSITY_DEBOUNCE_MS = 180
    CURIOSITY_DURATION_SECONDS = 1.8
    CURIOSITY_MIN_GAP_SECONDS = 1.2
    CURIOSITY_LEAN_PX = 4.0

    _CURIOSITY_LABELS = {
        "browser": "web",
        "vscode": "{ }",
        "terminal": ">_",
        "editor": "</>",
        "media": "♪",
        "pixel_art": "px",
        "unknown": "?",
    }
    _CURIOSITY_START_STATES = frozenset(
        (
            MochiState.IDLE,
            MochiState.BLINKING,
            MochiState.WALKING,
            MochiState.TYPING,
            MochiState.COMPUTER,
        )
    )
    _CURIOSITY_CONTINUE_STATES = _CURIOSITY_START_STATES

    def __init__(self, *args, **kwargs) -> None:
        self._curiosity_category: str | None = None
        self._curiosity_started_at = 0.0
        self._curiosity_last_started_at = float("-inf")
        self._curiosity_pending_category: str | None = None
        self._curiosity_source_id: int | None = None
        super().__init__(*args, **kwargs)

    def _on_presence_app_category_changed(self, category: str) -> None:
        previous = self._presence_app_category
        super()._on_presence_app_category_changed(category)
        # Backward-compatible fallback for older helpers that do not emit the
        # dedicated focus pulse yet.
        if category != previous:
            self._schedule_curiosity_cue(category)

    def _on_presence_app_focus_changed(self, category: str) -> None:
        super()._on_presence_app_focus_changed(category)
        self._schedule_curiosity_cue(category)

    def _cancel_curiosity_source(self) -> None:
        source_id = self._curiosity_source_id
        self._curiosity_source_id = None
        if source_id is None:
            return
        try:
            GLib.source_remove(source_id)
        except Exception:
            pass

    def _schedule_curiosity_cue(self, category: str) -> None:
        """Debounce focus churn so quick Alt-Tab passes do not flash repeatedly."""
        self._cancel_curiosity_source()
        self._curiosity_pending_category = None

        if category not in self._CURIOSITY_LABELS:
            return

        self._curiosity_pending_category = category
        self._curiosity_source_id = GLib.timeout_add(
            self.CURIOSITY_DEBOUNCE_MS,
            self._show_scheduled_curiosity,
        )

    def _show_scheduled_curiosity(self) -> bool:
        self._curiosity_source_id = None
        category = self._curiosity_pending_category
        self._curiosity_pending_category = None
        if category is not None:
            self._begin_curiosity_cue(category)
        return GLib.SOURCE_REMOVE

    def _curiosity_allowed(self, *, continuing: bool = False) -> bool:
        if (
            getattr(self, "_preview_mode", False)
            or getattr(self, "_presence_shutting_down", False)
            or getattr(self, "_user_idle", False)
            or getattr(self, "_context_menu_open", False)
            or getattr(self, "_press", None) is not None
            or getattr(self, "_drag_started", False)
        ):
            return False

        state = getattr(self, "state", None)
        if state is None:
            return False
        if state.presentation is not PresentationState.NORMAL:
            return False
        allowed_states = (
            self._CURIOSITY_CONTINUE_STATES
            if continuing
            else self._CURIOSITY_START_STATES
        )
        if state.current not in allowed_states:
            return False

        engine = getattr(self, "_ambient_presence_engine", None)
        tuning = getattr(engine, "tuning", None)
        if tuning is None:
            return True
        return bool(
            getattr(tuning, "ambient_reactions_enabled", True)
            and not getattr(tuning, "quiet_mode", False)
        )

    def _begin_curiosity_cue(self, category: str) -> bool:
        if category not in self._CURIOSITY_LABELS or not self._curiosity_allowed():
            return False

        now = time.monotonic()
        if now - self._curiosity_last_started_at < self.CURIOSITY_MIN_GAP_SECONDS:
            return False

        self._curiosity_category = category
        self._curiosity_started_at = now
        self._curiosity_last_started_at = now
        self.queue_draw()
        logger = getattr(self, "_logger", None)
        if logger is not None:
            logger.debug("[curiosity] noticed app category=%s", category)
        return True

    def _clear_curiosity_cue(self) -> None:
        if self._curiosity_category is None:
            return
        self._curiosity_category = None
        self.queue_draw()

    def _curiosity_progress(self, now: float | None = None) -> float | None:
        if self._curiosity_category is None:
            return None
        if now is None:
            now = time.monotonic()
        elapsed = max(0.0, now - self._curiosity_started_at)
        duration = self.CURIOSITY_DURATION_SECONDS
        if elapsed >= duration:
            return None
        return min(1.0, elapsed / duration)

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

    def _curiosity_direction(self, width: int) -> int:
        """Lean toward screen center without requesting focused-window geometry.

        The current AmbiSense contract intentionally exposes only a coarse app
        category. Using Mochi's own monitor-relative placement gives the cue a
        directional feel while preserving that privacy boundary.
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
        category = self._curiosity_category

        if progress is None or category is None:
            super()._draw(area, context, width, height)
            return

        alpha = self._curiosity_alpha(progress)
        direction = self._curiosity_direction(width)
        scale = max(0.5, min(width, height) / 112.0)
        lean_x = (
            direction
            * self.CURIOSITY_LEAN_PX
            * scale
            * self._curiosity_lean_factor(progress)
        )

        context.save()
        context.translate(lean_x, -1.0 * scale * self._curiosity_lean_factor(progress))
        super()._draw(area, context, width, height)
        context.restore()

        self._draw_curiosity_bubble(
            context,
            width=width,
            height=height,
            category=category,
            direction=direction,
            alpha=alpha,
            scale=scale,
        )

    def _draw_curiosity_bubble(
        self,
        context,
        *,
        width: int,
        height: int,
        category: str,
        direction: int,
        alpha: float,
        scale: float,
    ) -> None:
        if alpha <= 0.0:
            return

        label = self._CURIOSITY_LABELS[category]
        bubble_w = 34.0 * scale
        bubble_h = 24.0 * scale
        radius = 7.0 * scale
        center_x = width * 0.5 + direction * 19.0 * scale
        x = max(
            3.0 * scale,
            min(center_x - bubble_w / 2, width - bubble_w - 3.0 * scale),
        )
        y = max(3.0 * scale, 7.0 * scale)

        context.save()
        self._rounded_rect(context, x, y, bubble_w, bubble_h, radius)
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

        context.select_font_face("Sans")
        context.set_font_size(max(7.0, 9.5 * scale))
        extents = context.text_extents(label)
        try:
            text_width = extents.width
            text_height = extents.height
            x_bearing = extents.x_bearing
            y_bearing = extents.y_bearing
        except AttributeError:
            x_bearing, y_bearing, text_width, text_height = extents[:4]
        text_x = x + (bubble_w - text_width) / 2 - x_bearing
        text_y = y + (bubble_h - text_height) / 2 - y_bearing
        context.move_to(text_x, text_y)
        context.set_source_rgba(0.09, 0.18, 0.12, 0.92 * alpha)
        context.show_text(label)
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

    def _tick(self) -> bool:
        result = super()._tick()
        if self._curiosity_category is None:
            return result

        if not self._curiosity_allowed(continuing=True):
            self._clear_curiosity_cue()
            return result

        if self._curiosity_progress() is None:
            self._clear_curiosity_cue()
            return result

        self.queue_draw()
        return result

    def shutdown_presence(self) -> None:
        self._cancel_curiosity_source()
        self._curiosity_pending_category = None
        self._curiosity_category = None
        super().shutdown_presence()
