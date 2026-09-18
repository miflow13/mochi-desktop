import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.drag_motion import DragMotionModel
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

    def test_existing_speech_is_preserved_when_drag_starts(self) -> None:
        bubble = SimpleNamespace(visible=True, hide=Mock(), show=Mock(return_value=True))
        tuning = SimpleNamespace(speech_enabled=True, quiet_mode=False)
        buddy = SimpleNamespace(
            _presence_bubble=bubble,
            _ambient_presence_engine=SimpleNamespace(tuning=tuning),
            _last_drag_speech_at=float("-inf"),
            _logger=Mock(),
            DRAG_SPEECH_COOLDOWN_SECONDS=30.0,
            DRAG_SPEECH_DURATION_SECONDS=2.5,
        )

        X11Buddy._maybe_show_drag_speech(buddy)

        bubble.hide.assert_not_called()
        bubble.show.assert_not_called()

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

    def test_visual_sample_uses_pointer_target_without_window_readback(self) -> None:
        motion = SimpleNamespace(
            begin=Mock(),
            update=Mock(),
            filtered_velocity_x=125.0,
            horizontal_intensity=0.25,
        )
        placement = SimpleNamespace(
            position=SimpleNamespace(x=120, y=80),
            sync_from_window=Mock(
                side_effect=AssertionError("drag visual must not use X11 readback")
            ),
        )
        buddy = SimpleNamespace(
            _placement=placement,
            _drag_sample_position=(100, 80),
            _drag_sample_time=10.0,
            _drag_motion=motion,
            _last_drag_update_time=0.0,
            _play_drag_pose=Mock(),
            player=SimpleNamespace(
                frame=SimpleNamespace(sprite="drag/drag_left_medium.png")
            ),
            _drag_frame_index=2,
            _logger=Mock(),
        )

        with patch("mochi.x11_buddy.time.monotonic", return_value=10.016):
            X11Buddy._sample_x11_drag(buddy, render=True)

        motion.begin.assert_not_called()
        motion.update.assert_called_once_with(120, 80, 10.016)
        placement.sync_from_window.assert_not_called()
        buddy._play_drag_pose.assert_called_once_with()
        self.assertEqual(buddy._drag_sample_position, (120, 80))
        self.assertEqual(buddy._drag_sample_time, 10.016)

    def test_pointer_target_reversal_changes_motion_sign_on_next_sample(self) -> None:
        motion = DragMotionModel()
        placement = SimpleNamespace(position=SimpleNamespace(x=100, y=80))
        buddy = SimpleNamespace(
            _placement=placement,
            _drag_sample_position=None,
            _drag_sample_time=None,
            _drag_motion=motion,
            _last_drag_update_time=0.0,
            _play_drag_pose=Mock(),
            player=SimpleNamespace(frame=None),
            _drag_frame_index=0,
            _logger=Mock(),
        )

        with patch("mochi.x11_buddy.time.monotonic", return_value=10.000):
            X11Buddy._sample_x11_drag(buddy, render=False)

        placement.position = SimpleNamespace(x=110, y=80)
        with patch("mochi.x11_buddy.time.monotonic", return_value=10.016):
            X11Buddy._sample_x11_drag(buddy, render=False)
        self.assertGreater(motion.filtered_velocity_x, 0.0)

        placement.position = SimpleNamespace(x=100, y=80)
        with patch("mochi.x11_buddy.time.monotonic", return_value=10.032):
            X11Buddy._sample_x11_drag(buddy, render=False)
        self.assertLess(motion.filtered_velocity_x, 0.0)


if __name__ == "__main__":
    unittest.main()
