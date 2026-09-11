import unittest

from mochi.presence.engine import PresenceAction


class SpeechPresentationTests(unittest.TestCase):
    def test_normal_ambient_speech_requests_typing_preview(self) -> None:
        action = PresenceAction(
            "speech",
            "ambient",
            "just hanging out",
            10,
        )

        self.assertEqual(action.text, "just hanging out")
        self.assertTrue(getattr(action.text, "typing_preview", False))

    def test_contextual_speech_requests_typing_preview(self) -> None:
        action = PresenceAction(
            "speech",
            "developer",
            "tiny commit?",
            30,
            "build_succeeded",
        )

        self.assertTrue(getattr(action.text, "typing_preview", False))

    def test_critical_system_speech_stays_immediate(self) -> None:
        action = PresenceAction(
            "speech",
            "network",
            "internet disappeared...",
            40,
            "network_lost",
        )

        self.assertFalse(getattr(action.text, "typing_preview", True))

    def test_text_remains_a_normal_string(self) -> None:
        action = PresenceAction("speech", "ambient", "hello", 10)

        self.assertIsInstance(action.text, str)
        self.assertEqual(action.text.strip(), "hello")


if __name__ == "__main__":
    unittest.main()
