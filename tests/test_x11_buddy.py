import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.state import MochiState
from mochi.x11_buddy import X11Buddy


class X11BuddyDragTests(unittest.TestCase):
    def test_motion_handler_never_starts_compositor_move(self) -> None:
        source = inspect.getsource(X11Buddy._on_motion)

        self.assertNotIn("surface.begin_move(", source)

    def test_drag_speech_uses_presence_bubble_for_two_and_a_half_seconds(self) -> None:
        bubble = SimpleNamespace(visible=False, hide=Mock(), show=Mock(return_value=True))
        tuning = SimpleNamespace(speech_enabled=True, quiet_mode=False)
        buddy = SimpleNamespace(
            _presence_bubble=bubble,
            _ambient_presence_engine=SimpleNamespace(tuning=tuning),
            _last_drag_speech_at=float("-inf"),
            _logger=Mock(),
            DRAG_SPEECH_COOLDOWN_SECONDS=30.0,
            DRAG_SPEECH_DURATION_SECONDS=2.5,
        )

        with patch("mochi.x11_buddy.time.monotonic", return_value=100.0):
            X11Buddy._maybe_show_drag_speech(buddy)

        bubble.show.assert_called_once_with("wheee!", duration_seconds=2.5)
        self.assertEqual(buddy._last_drag_speech_at, 100.0)

    def test_drag_speech_has_thirty_second_cooldown(self) -> None:
        bubble = SimpleNamespace(visible=False, hide=Mock(), show=Mock(return_value=True))
        tuning = SimpleNamespace(speech_enabled=True, quiet_mode=False)
        buddy = SimpleNamespace(
            _presence_bubble=bubble,
            _ambient_presence_engine=SimpleNamespace(tuning=tuning),
            _last_drag_speech_at=100.0,
            _logger=Mock(),
            DRAG_SPEECH_COOLDOWN_SECONDS=30.0,
            DRAG_SPEECH_DURATION_SECONDS=2.5,
        )

        with patch("mochi.x11_buddy.time.monotonic", return_value=129.9):
            X11Buddy._maybe_show_drag_speech(buddy)
        bubble.show.assert_not_called()
        self.assertEqual(buddy._last_drag_speech_at, 100.0)

        with patch("mochi.x11_buddy.time.monotonic", return_value=130.0):
            X11Buddy._maybe_show_drag_speech(buddy)
        bubble.show.assert_called_once_with("wheee!", duration_seconds=2.5)
        self.assertEqual(buddy._last_drag_speech_at, 130.0)

    def test_drag_speech_respects_quiet_mode(self) -> None:
        bubble = SimpleNamespace(visible=False, hide=Mock(), show=Mock(return_value=True))
        tuning = SimpleNamespace(speech_enabled=True, quiet_mode=True)
        buddy = SimpleNamespace(
            _presence_bubble=bubble,
            _ambient_presence_engine=SimpleNamespace(tuning=tuning),
            DRAG_SPEECH_COOLDOWN_SECONDS=30.0,
            DRAG_SPEECH_DURATION_SECONDS=2.5,
        )

        X11Buddy._maybe_show_drag_speech(buddy)

        bubble.show.assert_not_called()

    def test_active_drag_moves_from_root_pointer_anchor(self) -> None:
        placement = SimpleNamespace(drag_to_pointer=Mock())
        buddy = SimpleNamespace(
            _drag_started=True,
            _press=(37.0, 61.0),
            state=SimpleNamespace(current=MochiState.DRAGGED),
            _placement=placement,
        )

        X11Buddy._move_with_x11_pointer(buddy)

        placement.drag_to_pointer.assert_called_once_with(37.0, 61.0)

    def test_active_drag_immediately_resyncs_visible_speech_bubble(self) -> None:
        placement = SimpleNamespace(drag_to_pointer=Mock())
        bubble = SimpleNamespace(visible=True, follow_owner_now=Mock())
        buddy = SimpleNamespace(
            _drag_started=True,
            _press=(37.0, 61.0),
            state=SimpleNamespace(current=MochiState.DRAGGED),
            _placement=placement,
            _presence_bubble=bubble,
        )

        X11Buddy._move_with_x11_pointer(buddy)

        placement.drag_to_pointer.assert_called_once_with(37.0, 61.0)
        bubble.follow_owner_now.assert_called_once_with()

    def test_idle_buddy_does_not_move_from_pointer(self) -> None:
        placement = SimpleNamespace(drag_to_pointer=Mock())
        buddy = SimpleNamespace(
            _drag_started=False,
            _press=(37.0, 61.0),
            state=SimpleNamespace(current=MochiState.IDLE),
            _placement=placement,
        )

        X11Buddy._move_with_x11_pointer(buddy)

        placement.drag_to_pointer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
