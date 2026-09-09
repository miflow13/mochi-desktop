"""Privacy-preserving text activity detection for Mochi's typing mirror."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import logging
import time


class TypingBurstDetector:
    """Turns anonymous accessibility activity into typing start/stop sessions."""

    def __init__(
        self,
        *,
        start_event_count: int = 3,
        burst_window_seconds: float = 0.65,
        stop_delay_seconds: float = 0.90,
    ) -> None:
        if start_event_count < 2:
            raise ValueError("start_event_count must be at least 2")
        if burst_window_seconds <= 0 or stop_delay_seconds <= 0:
            raise ValueError("typing timing values must be positive")

        self.start_event_count = start_event_count
        self.burst_window_seconds = burst_window_seconds
        self.stop_delay_seconds = stop_delay_seconds
        self.active = False
        self._event_times: deque[float] = deque(maxlen=start_event_count)

    def record_activity(self, now: float | None = None) -> bool:
        """Record one anonymous text/caret activity event.

        Returns True only when this event starts a new typing session.
        """
        timestamp = time.monotonic() if now is None else now
        self._event_times.append(timestamp)

        if self.active or len(self._event_times) < self.start_event_count:
            return False

        if self._event_times[-1] - self._event_times[0] <= self.burst_window_seconds:
            self.active = True
            return True

        return False

    def end_session(self) -> bool:
        """End the active typing session and report whether one was active."""
        was_active = self.active
        self.active = False
        self._event_times.clear()
        return was_active

    def reset(self) -> None:
        """Forget the current burst without emitting a stop event."""
        self.active = False
        self._event_times.clear()


class TypingActivityMonitor:
    """AT-SPI text/caret activity monitor for Mochi.

    Mochi never reads or stores inserted text. It only reacts to accessibility
    event timing. `object:text-changed` is treated as a strong typing signal;
    `object:text-caret-moved` is used as a fallback signal for apps that expose
    caret movement but not text-change events.
    """

    TEXT_CHANGED_EVENT = "object:text-changed"
    CARET_MOVED_EVENT = "object:text-caret-moved"

    def __init__(
        self,
        *,
        on_typing_activity: Callable[[], None],
        on_typing_stopped: Callable[[], None],
        detector: TypingBurstDetector | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._on_typing_activity = on_typing_activity
        self._on_typing_stopped = on_typing_stopped
        self._detector = detector or TypingBurstDetector()
        self._logger = logger or logging.getLogger(__name__)

        self._listener = None
        self._glib = None
        self._stop_source_id: int | None = None
        self._registered_events: list[str] = []

    @property
    def available(self) -> bool:
        return self._listener is not None

    @property
    def active(self) -> bool:
        return self._detector.active

    def start(self) -> bool:
        """Register AT-SPI listeners for text/caret activity."""
        if self._listener is not None:
            return True

        try:
            import gi

            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi, GLib
        except (ImportError, ValueError) as exc:
            self._logger.info(
                "Typing mirror unavailable: AT-SPI bindings missing (%s)",
                exc,
            )
            return False

        try:
            Atspi.init()
            listener = Atspi.EventListener.new(self._on_accessibility_event, None)

            registered: list[str] = []
            for event_name in (
                self.TEXT_CHANGED_EVENT,
                self.CARET_MOVED_EVENT,
            ):
                if listener.register(event_name):
                    registered.append(event_name)

            if not registered:
                self._logger.info(
                    "Typing mirror unavailable: AT-SPI text activity listeners "
                    "could not be registered"
                )
                return False
        except Exception as exc:
            self._logger.info("Typing mirror unavailable: %s", exc)
            return False

        self._listener = listener
        self._glib = GLib
        self._registered_events = registered

        self._logger.info(
            "Typing mirror enabled via AT-SPI text activity "
            "(typed content is never read or stored)"
        )
        self._logger.debug(
            "Typing mirror listeners: %s",
            ", ".join(self._registered_events),
        )
        return True

    def reset(self) -> None:
        """Cancel the current typing session without disabling monitoring."""
        self._cancel_stop_timer()
        self._detector.reset()

    def stop(self) -> None:
        """Unregister listeners and clear any active typing session."""
        self._cancel_stop_timer()
        self._detector.reset()

        if self._listener is not None:
            for event_name in tuple(self._registered_events):
                try:
                    self._listener.deregister(event_name)
                except Exception:
                    pass

        self._listener = None
        self._registered_events.clear()
        self._glib = None

    def _on_accessibility_event(self, event, *_args) -> None:
        # Intentionally inspect only the event *type*. Never inspect event text,
        # source contents, key values, or inserted strings.
        event_type = getattr(event, "type", "") or ""

        if not (
            event_type.startswith(self.TEXT_CHANGED_EVENT)
            or event_type.startswith(self.CARET_MOVED_EVENT)
        ):
            return

        started = self._detector.record_activity()

        if self._detector.active:
            # Emit on every active event so Mochi can begin once any
            # higher-priority animation finishes.
            self._on_typing_activity()
            self._arm_stop_timer()

        if started:
            self._logger.debug(
                "Typing activity started from %s",
                event_type,
            )

    def _arm_stop_timer(self) -> None:
        if self._glib is None:
            return

        self._cancel_stop_timer()
        self._stop_source_id = self._glib.timeout_add(
            round(self._detector.stop_delay_seconds * 1_000),
            self._finish_typing_session,
        )

    def _cancel_stop_timer(self) -> None:
        if self._stop_source_id is None or self._glib is None:
            self._stop_source_id = None
            return

        try:
            self._glib.source_remove(self._stop_source_id)
        except Exception:
            pass

        self._stop_source_id = None

    def _finish_typing_session(self) -> bool:
        self._stop_source_id = None

        if self._detector.end_session():
            self._logger.debug("Typing activity stopped")
            self._on_typing_stopped()

        if self._glib is None:
            return False

        return self._glib.SOURCE_REMOVE
