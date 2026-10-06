"""GTK-free hover dwell that opens Mochi's Pocket tray.

Resting the pointer on Mochi arms a short dwell. A peek bar appears partway
through, and the tray opens when the dwell completes. Every collaborator is
injected, so the rules are testable without a display. This object owns its
three timers (peek, open, close) and cancels them in shutdown().
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto

POCKET_HOVER_DELAY_CHOICES_MS = (0, 1500, 2000, 3000)
DEFAULT_POCKET_HOVER_DELAY_MS = 2000
POCKET_PEEK_DELAY_MS = 600
POCKET_TRAY_CLOSE_GRACE_MS = 450

TimeoutAdd = Callable[[int, Callable[[], bool]], int]
SourceRemove = Callable[[int], object]


def normalize_hover_delay_ms(value: object) -> int:
    """Return a supported dwell in milliseconds; 0 means off."""
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_POCKET_HOVER_DELAY_MS
    if value not in POCKET_HOVER_DELAY_CHOICES_MS:
        return DEFAULT_POCKET_HOVER_DELAY_MS
    return value


class DwellPhase(Enum):
    IDLE = auto()
    ARMED = auto()
    PEEK = auto()
    OPEN = auto()


class PocketHoverDwell:
    """Arm, peek, open, and close the Pocket tray from pointer events."""

    def __init__(
        self,
        *,
        delay_ms: Callable[[], int],
        can_arm: Callable[[], bool],
        show_peek: Callable[[int], None],
        hide_peek: Callable[[], None],
        open_tray: Callable[[bool], bool],
        close_tray: Callable[[], None],
        timeout_add: TimeoutAdd | None = None,
        source_remove: SourceRemove | None = None,
    ) -> None:
        if timeout_add is None or source_remove is None:
            from gi.repository import GLib

            timeout_add = timeout_add or GLib.timeout_add
            source_remove = source_remove or GLib.source_remove
        self._delay_ms = delay_ms
        self._can_arm = can_arm
        self._show_peek = show_peek
        self._hide_peek = hide_peek
        self._open_tray = open_tray
        self._close_tray = close_tray
        self._timeout_add = timeout_add
        self._source_remove = source_remove
        self._sources: dict[str, int] = {}
        self._phase = DwellPhase.IDLE
        self._armed_delay_ms = 0
        self._pinned = False
        self._over_mochi = False
        self._over_tray = False
        self._needs_leave = False
        self._dragging = False

    @property
    def phase(self) -> DwellPhase:
        return self._phase

    @property
    def pinned(self) -> bool:
        return self._pinned

    def pointer_entered(self) -> None:
        self._over_mochi = True
        self._cancel("close")

    def pointer_moved(self) -> None:
        """Arm on real motion only: a window moving under a still pointer is not a reach."""
        self._over_mochi = True
        if self._phase is not DwellPhase.IDLE or self._needs_leave:
            return
        if not self._allowed():
            return
        self._armed_delay_ms = self._delay_ms()
        self._phase = DwellPhase.ARMED
        self._schedule(
            "peek",
            min(POCKET_PEEK_DELAY_MS, self._armed_delay_ms),
            self._on_peek_due,
        )
        self._schedule("open", self._armed_delay_ms, self._on_open_due)

    def pointer_left(self) -> None:
        self._over_mochi = False
        self._needs_leave = False
        if self._phase in (DwellPhase.ARMED, DwellPhase.PEEK):
            self._reset_arming()
        elif self._phase is DwellPhase.OPEN and not self._pinned:
            self._schedule_close()

    def tray_entered(self) -> None:
        self._over_tray = True
        self._cancel("close")

    def tray_left(self) -> None:
        self._over_tray = False
        if self._phase is DwellPhase.OPEN and not self._pinned:
            self._schedule_close()

    def interrupt(self) -> None:
        """A press, right-click, or drag on Mochi wins over the Pocket."""
        if self._phase in (DwellPhase.ARMED, DwellPhase.PEEK):
            self._reset_arming()
        elif self._phase is DwellPhase.OPEN:
            self.close()
        self._needs_leave = self._over_mochi

    def drag_started(self) -> None:
        self._dragging = True
        self._cancel("close")

    def drag_finished(self, delivered: bool) -> None:
        self._dragging = False
        if self._phase is not DwellPhase.OPEN:
            return
        if delivered:
            self.close()
        elif not self._pinned and not self._over_mochi and not self._over_tray:
            self._schedule_close()

    def open_pinned(self) -> bool:
        """Open the tray from the context menu, with keyboard focus."""
        if self._phase is DwellPhase.OPEN:
            return True
        self._reset_arming()
        if not self._open_tray(True):
            return False
        self._phase = DwellPhase.OPEN
        self._pinned = True
        self._needs_leave = self._over_mochi
        return True

    def close(self) -> None:
        """Close the tray after an action, Esc, focus loss, or an interrupt."""
        if self._phase is not DwellPhase.OPEN:
            return
        self._cancel("close")
        self._phase = DwellPhase.IDLE
        self._pinned = False
        self._over_tray = False
        self._dragging = False
        self._needs_leave = self._over_mochi
        self._close_tray()

    def shutdown(self) -> None:
        for name in tuple(self._sources):
            self._cancel(name)
        self._phase = DwellPhase.IDLE
        self._pinned = False
        self._dragging = False

    def _allowed(self) -> bool:
        return self._delay_ms() > 0 and self._can_arm()

    def _on_peek_due(self) -> bool:
        self._sources.pop("peek", None)
        if self._phase is not DwellPhase.ARMED:
            return False
        if not self._allowed():
            self._reset_arming()
            return False
        self._phase = DwellPhase.PEEK
        self._show_peek(max(0, self._armed_delay_ms - POCKET_PEEK_DELAY_MS))
        return False

    def _on_open_due(self) -> bool:
        self._sources.pop("open", None)
        if self._phase not in (DwellPhase.ARMED, DwellPhase.PEEK):
            return False
        if not self._allowed():
            self._reset_arming()
            return False
        peeking = self._phase is DwellPhase.PEEK
        self._cancel("peek")
        self._phase = DwellPhase.IDLE
        self._needs_leave = self._over_mochi
        # The tray replaces a visible peek in place; hide it only on failure.
        if not self._open_tray(False):
            if peeking:
                self._hide_peek()
            return False
        self._phase = DwellPhase.OPEN
        self._pinned = False
        return False

    def _on_close_due(self) -> bool:
        self._sources.pop("close", None)
        if (
            self._phase is DwellPhase.OPEN
            and not self._pinned
            and not self._dragging
            and not self._over_mochi
            and not self._over_tray
        ):
            self.close()
        return False

    def _reset_arming(self) -> None:
        self._cancel("peek")
        self._cancel("open")
        peeking = self._phase is DwellPhase.PEEK
        self._phase = DwellPhase.IDLE
        if peeking:
            self._hide_peek()

    def _schedule_close(self) -> None:
        self._schedule("close", POCKET_TRAY_CLOSE_GRACE_MS, self._on_close_due)

    def _schedule(
        self,
        name: str,
        delay_ms: int,
        callback: Callable[[], bool],
    ) -> None:
        self._cancel(name)
        self._sources[name] = self._timeout_add(delay_ms, callback)

    def _cancel(self, name: str) -> None:
        source_id = self._sources.pop(name, None)
        if source_id is not None:
            self._source_remove(source_id)
