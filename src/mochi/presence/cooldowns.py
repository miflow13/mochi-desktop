"""Rate limiting primitives for Mochi's ambient speech."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import time


class CooldownTracker:
    """Track global, hourly, and per-category speech limits in memory."""

    def __init__(
        self,
        *,
        global_gap_seconds: float = 300.0,
        max_per_hour: int = 4,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.global_gap_seconds = global_gap_seconds
        self.max_per_hour = max_per_hour
        self._clock = clock
        self._last_spoken_at: float | None = None
        self._history: deque[tuple[float, str]] = deque()
        self._category_until: dict[str, float] = {}

    def can_speak(self, now: float | None = None) -> tuple[bool, str | None]:
        timestamp = self._clock() if now is None else now
        self._prune(timestamp)
        if (
            self._last_spoken_at is not None
            and timestamp - self._last_spoken_at < self.global_gap_seconds
        ):
            return False, "global cooldown active"
        if len(self._history) >= self.max_per_hour:
            return False, "hourly speech limit reached"
        return True, None

    def category_ready(
        self, category: str, now: float | None = None
    ) -> tuple[bool, str | None]:
        timestamp = self._clock() if now is None else now
        until = self._category_until.get(category)
        if until is not None and timestamp < until:
            return False, f"{category} cooldown active"
        return True, None

    def record(
        self,
        category: str,
        *,
        now: float | None = None,
        category_cooldown_seconds: float = 0.0,
    ) -> None:
        timestamp = self._clock() if now is None else now
        self._last_spoken_at = timestamp
        self._history.append((timestamp, category))
        if category_cooldown_seconds > 0:
            self._category_until[category] = timestamp + category_cooldown_seconds
        self._prune(timestamp)

    def clear(self) -> None:
        self._last_spoken_at = None
        self._history.clear()
        self._category_until.clear()

    @property
    def last_spoken_at(self) -> float | None:
        return self._last_spoken_at

    @property
    def phrases_last_hour(self) -> int:
        self._prune(self._clock())
        return len(self._history)

    def _prune(self, now: float) -> None:
        cutoff = now - 3600.0
        while self._history and self._history[0][0] <= cutoff:
            self._history.popleft()
        expired = [name for name, until in self._category_until.items() if until <= now]
        for name in expired:
            del self._category_until[name]
