"""Promo-only cinematic entrance for Mochi."""

from __future__ import annotations

import time

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

from mochi.behavior import WalkMotion, choose_walk_animation
from mochi.state import MochiState


class TrailerEntranceController:
    """Drive a one-shot walk-in without changing normal movement bounds."""

    DELAY_MS = 800
    TICK_MS = 16
    MAX_TICK_CATCHUP_MS = 64
    WALK_SPEED_PX_PER_SECOND = 56.0
    ARRIVAL_HOLD_MS = 1_500

    def __init__(self, buddy, placement) -> None:
        self._buddy = buddy
        self._placement = placement
        self._motion: WalkMotion | None = None
        self._elapsed_ms = 0
        self._last_tick_monotonic: float | None = None
        self._source_id: int | None = None
        self._hold_source_id: int | None = None

    def schedule(self) -> None:
        """Start the entrance shortly after the window becomes visible."""
        if self._source_id is None and self._motion is None:
            self._source_id = GLib.timeout_add(self.DELAY_MS, self._start)

    def cancel(self) -> None:
        for source_id in (self._source_id, self._hold_source_id):
            if source_id is not None:
                GLib.source_remove(source_id)
        self._source_id = None
        self._hold_source_id = None
        self._motion = None

    def _start(self) -> bool:
        self._source_id = None
        if self._buddy.state.current is not MochiState.IDLE:
            # Launching from a terminal can briefly trigger the typing/search
            # presence monitors. Clear only cancellable ambient reactions so
            # the promo entrance stays deterministic without overriding sleep,
            # drag, feeding, or other high-priority ownership.
            self._buddy._cancel_active_emote()
        if self._buddy.state.current is not MochiState.IDLE:
            return GLib.SOURCE_REMOVE

        origin, target = self._placement.left_entrance_positions()
        walk_name = choose_walk_animation(
            (origin.x, origin.y),
            (target.x, target.y),
        )
        walk_animation = self._buddy._animation_for(walk_name)
        cycle_duration_ms = sum(
            frame.duration_ms or walk_animation.frame_duration_ms
            for frame in walk_animation.frames
        )

        self._placement.move_unclamped(origin.x, origin.y)
        self._motion = WalkMotion(
            origin=(origin.x, origin.y),
            target=(target.x, target.y),
            cycle_duration_ms=cycle_duration_ms,
            speed_px_per_second=self.WALK_SPEED_PX_PER_SECOND,
        )
        self._elapsed_ms = 0
        self._last_tick_monotonic = time.monotonic()

        if not self._buddy._transition_to(MochiState.WALKING):
            self._placement.move_to(target.x, target.y)
            self._motion = None
            return GLib.SOURCE_REMOVE

        self._buddy._play_animation(walk_name)
        self._source_id = GLib.timeout_add(self.TICK_MS, self._tick)
        return GLib.SOURCE_REMOVE

    def _tick(self) -> bool:
        if (
            self._motion is None
            or self._buddy.state.current is not MochiState.WALKING
        ):
            self._source_id = None
            self._motion = None
            return GLib.SOURCE_REMOVE

        now = time.monotonic()
        previous = self._last_tick_monotonic or now
        self._last_tick_monotonic = now
        elapsed_ms = max(1, round((now - previous) * 1_000))
        self._elapsed_ms += min(elapsed_ms, self.MAX_TICK_CATCHUP_MS)

        x, y = self._motion.position_at(self._elapsed_ms)
        self._placement.move_unclamped(x, y)
        if self._buddy.player.seek_progress(
            self._motion.animation_progress(self._elapsed_ms)
        ):
            self._buddy.queue_draw()

        if self._motion.progress(self._elapsed_ms) < 1.0:
            return GLib.SOURCE_CONTINUE

        target_x, target_y = self._motion.target
        self._placement.move_to(target_x, target_y)
        self._motion = None
        self._source_id = None

        # Hold a clean idle pose briefly so a recorded entrance has a natural
        # landing beat before normal autonomous behavior resumes.
        self._buddy._play_animation("idle")
        self._hold_source_id = GLib.timeout_add(
            self.ARRIVAL_HOLD_MS,
            self._finish_arrival,
        )
        return GLib.SOURCE_REMOVE

    def _finish_arrival(self) -> bool:
        self._hold_source_id = None
        if self._buddy.state.current is MochiState.WALKING:
            self._buddy._transition_to(MochiState.IDLE)
            self._buddy.queue_draw()
        return GLib.SOURCE_REMOVE
