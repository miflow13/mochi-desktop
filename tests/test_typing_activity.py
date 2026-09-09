import unittest

from mochi.typing_activity import TypingBurstDetector


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


if __name__ == "__main__":
    unittest.main()
