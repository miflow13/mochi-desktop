import unittest

from mochi.typing_activity import TypingActivityMonitor, TypingBurstDetector


class TypingBurstDetectorTests(unittest.TestCase):
    def test_first_activity_event_starts_typing(self) -> None:
        detector = TypingBurstDetector(
            start_event_count=1,
            burst_window_seconds=0.65,
            stop_delay_seconds=0.90,
        )

        self.assertTrue(detector.record_activity(1.0))
        self.assertTrue(detector.active)

        # Additional activity continues the same session.
        self.assertFalse(detector.record_activity(1.2))
        self.assertTrue(detector.active)

    def test_multi_event_threshold_still_works_when_configured(self) -> None:
        detector = TypingBurstDetector(
            start_event_count=3,
            burst_window_seconds=0.65,
        )

        self.assertFalse(detector.record_activity(1.00))
        self.assertFalse(detector.record_activity(1.18))
        self.assertTrue(detector.record_activity(1.36))
        self.assertTrue(detector.active)

    def test_end_session_reports_active_state_and_allows_restart(self) -> None:
        detector = TypingBurstDetector(start_event_count=1)

        self.assertTrue(detector.record_activity(1.0))
        self.assertTrue(detector.end_session())
        self.assertFalse(detector.active)
        self.assertFalse(detector.end_session())

        self.assertTrue(detector.record_activity(2.0))
        self.assertTrue(detector.active)

    def test_reset_requires_fresh_activity(self) -> None:
        detector = TypingBurstDetector(start_event_count=1)

        self.assertTrue(detector.record_activity(1.0))
        detector.reset()

        self.assertFalse(detector.active)
        self.assertTrue(detector.record_activity(2.0))
        self.assertTrue(detector.active)


class _Event:
    def __init__(self, event_type: str) -> None:
        self.type = event_type


class _FakeGLib:
    SOURCE_REMOVE = False

    def __init__(self) -> None:
        self._callbacks: dict[int, object] = {}
        self._next_source_id = 1

    def timeout_add(self, _milliseconds: int, callback: object) -> int:
        source_id = self._next_source_id
        self._next_source_id += 1
        self._callbacks[source_id] = callback
        return source_id

    def source_remove(self, source_id: int) -> None:
        self._callbacks.pop(source_id, None)

    def fire_latest_timer(self) -> None:
        source_id = max(self._callbacks)
        callback = self._callbacks.pop(source_id)
        callback()


class TypingActivityMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.activity_calls = 0
        self.stop_calls = 0
        self.glib = _FakeGLib()
        self.monitor = TypingActivityMonitor(
            on_typing_activity=self._record_activity,
            on_typing_stopped=self._record_stop,
        )
        self.monitor._glib = self.glib

    def _record_activity(self) -> None:
        self.activity_calls += 1

    def _record_stop(self) -> None:
        self.stop_calls += 1

    def test_one_caret_move_does_not_trigger_typing(self) -> None:
        self.monitor._on_accessibility_event(
            _Event(TypingActivityMonitor.CARET_MOVED_EVENT)
        )

        self.assertFalse(self.monitor.active)
        self.assertEqual(self.activity_calls, 0)

    def test_repeated_caret_activity_can_trigger_typing(self) -> None:
        event = _Event(TypingActivityMonitor.CARET_MOVED_EVENT)

        self.monitor._on_accessibility_event(event)
        self.monitor._on_accessibility_event(event)
        self.monitor._on_accessibility_event(event)

        self.assertTrue(self.monitor.active)
        self.assertEqual(self.activity_calls, 1)

    def test_text_changed_triggers_typing(self) -> None:
        self.monitor._on_accessibility_event(
            _Event(TypingActivityMonitor.TEXT_CHANGED_EVENT)
        )

        self.assertTrue(self.monitor.active)
        self.assertEqual(self.activity_calls, 1)

    def test_typing_stops_after_inactivity(self) -> None:
        self.monitor._on_accessibility_event(
            _Event(TypingActivityMonitor.TEXT_CHANGED_EVENT)
        )
        self.glib.fire_latest_timer()

        self.assertFalse(self.monitor.active)
        self.assertEqual(self.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
