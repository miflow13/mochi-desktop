"""Small timing helpers for direct click-driven Mochi reactions."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import time


class ClickBurstDetector:
    """Recognize a fixed number of clicks inside a short rolling window."""

    def __init__(
        self,
        *,
        required_clicks: int = 3,
        window_seconds: float = 1.4,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if required_clicks < 2:
            raise ValueError("required_clicks must be at least 2")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.required_clicks = required_clicks
        self.window_seconds = window_seconds
        self._clock = clock
        self._clicks: deque[float] = deque(maxlen=required_clicks)

    def record(self, *, now: float | None = None) -> bool:
        timestamp = self._clock() if now is None else now
        cutoff = timestamp - self.window_seconds
        while self._clicks and self._clicks[0] < cutoff:
            self._clicks.popleft()
        self._clicks.append(timestamp)
        if len(self._clicks) < self.required_clicks:
            return False
        self._clicks.clear()
        return True

    def reset(self) -> None:
        self._clicks.clear()
