import unittest

from mochi.typing_activity import AtspiTextActivityBackend, TypingActivityMonitor


class _Event:
    def __init__(self, event_type: str) -> None:
        self.type = event_type


class TypingFeedbackGuardTests(unittest.TestCase):
    def test_runtime_fallback_ignores_text_changed_but_keeps_caret_activity(self) -> None:
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
        )
        backend = monitor._backends[1]
        self.assertIsInstance(backend, AtspiTextActivityBackend)

        calls = 0

        def activity() -> None:
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        backend._on_accessibility_event(_Event("object:text-changed:insert"))
        self.assertEqual(calls, 0)

        backend._on_accessibility_event(_Event("object:text-caret-moved"))
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
