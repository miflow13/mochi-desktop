"""Low-priority autonomous nap scheduling for Mochi.

This module owns *when* Mochi decides to take an occasional nap. It deliberately
does not own sleep/wake animation or behavior state; those remain in Buddy's
existing sleep lifecycle.
"""

from __future__ import annotations

import random

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

from mochi.state import MochiState, PresentationState


class AutonomousSleepController:
    """Schedule occasional naps without creating a second sleep state machine."""

    NAP_INTERVAL_SECONDS = (10 * 60, 25 * 60)
    NAP_DURATION_SECONDS = (30, 120)

    def __init__(self, buddy, *, rng=None) -> None:
        self._buddy = buddy
        self._rng = rng or random
        self._nap_source_id: int | None = None
        self._wake_source_id: int | None = None
        self._owns_sleep = False

    @property
    def owns_sleep(self) -> bool:
        """Whether the controller initiated Mochi's current sleep."""

        return self._owns_sleep

    def start(self) -> None:
        """Start autonomous nap scheduling."""

        self._schedule_next_nap()

    def stop(self) -> None:
        """Cancel autonomous nap/wake timers without changing Mochi's state."""

        self._remove_source("_nap_source_id")
        self._remove_source("_wake_source_id")
        self._owns_sleep = False

    def note_external_wake(self) -> None:
        """Release nap ownership when another interaction wakes Mochi first."""

        if not self._owns_sleep:
            return
        self._owns_sleep = False
        self._remove_source("_wake_source_id")
        self._schedule_next_nap()

    def _remove_source(self, attribute: str) -> None:
        source_id = getattr(self, attribute, None)
        setattr(self, attribute, None)
        if source_id is None:
            return
        try:
            GLib.source_remove(source_id)
        except Exception:
            # Shutdown can race a source that already removed itself.
            pass

    def _schedule_next_nap(self) -> None:
        """Schedule one future nap opportunity.

        Busy/ineligible states are never interrupted. If the opportunity arrives
        at a bad time, a fresh random opportunity is scheduled instead.
        """

        if (
            self._nap_source_id is not None
            or self._wake_source_id is not None
            or self._owns_sleep
            or getattr(self._buddy, "_preview_mode", False)
            or getattr(self._buddy, "_presence_shutting_down", False)
        ):
            return

        delay = self._rng.randint(*self.NAP_INTERVAL_SECONDS)
        self._nap_source_id = GLib.timeout_add_seconds(
            delay,
            self._try_start_nap,
        )
        self._buddy._logger.debug(
            "Autonomous nap opportunity scheduled in %d seconds",
            delay,
        )

    def _can_start_nap(self) -> bool:
        """Return whether autonomous sleep is currently low-risk."""

        if (
            getattr(self._buddy, "_preview_mode", False)
            or getattr(self._buddy, "_presence_shutting_down", False)
            or getattr(self._buddy, "_user_idle", False)
            or getattr(self._buddy, "_context_menu_open", False)
            or getattr(self._buddy, "_hovered", False)
            or getattr(self._buddy, "_press", None) is not None
        ):
            return False

        if self._buddy.state.current is not MochiState.IDLE:
            return False
        if self._buddy.state.presentation is not PresentationState.NORMAL:
            return False
        if getattr(self._buddy, "_current_animation", None) != "idle":
            return False

        focus_session = getattr(self._buddy, "_focus_session", None)
        if focus_session is not None and getattr(focus_session, "active", False):
            return False

        return True

    def _try_start_nap(self) -> bool:
        """Take a nap if eligible; otherwise defer to another random interval."""

        self._nap_source_id = None

        if not self._can_start_nap():
            self._schedule_next_nap()
            return GLib.SOURCE_REMOVE

        self._buddy._begin_sleep()

        # Buddy remains authoritative for whether sleep actually began.
        if self._buddy.state.current is not MochiState.SLEEPING:
            self._schedule_next_nap()
            return GLib.SOURCE_REMOVE

        self._owns_sleep = True
        duration = self._rng.randint(*self.NAP_DURATION_SECONDS)
        self._wake_source_id = GLib.timeout_add_seconds(
            duration,
            self._wake_from_nap,
        )
        self._buddy._logger.debug(
            "Autonomous nap started for about %d seconds",
            duration,
        )
        return GLib.SOURCE_REMOVE

    def _wake_from_nap(self) -> bool:
        """Wake only sleep that this controller still owns."""

        self._wake_source_id = None

        if not self._owns_sleep:
            self._schedule_next_nap()
            return GLib.SOURCE_REMOVE

        # If the real presence detector reports the user idle while Mochi is
        # napping, hand ownership to presence sleep instead of waking him.
        if getattr(self._buddy, "_user_idle", False):
            self._owns_sleep = False
            self._schedule_next_nap()
            return GLib.SOURCE_REMOVE

        if self._buddy.state.current is MochiState.SLEEPING:
            self._buddy._wake_up()

        self._owns_sleep = False
        self._schedule_next_nap()
        return GLib.SOURCE_REMOVE
