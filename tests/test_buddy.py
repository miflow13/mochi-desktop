import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.animation import Animation
from mochi.buddy import Buddy
from mochi.state import MochiState


class BuddyDragReleaseTests(unittest.TestCase):
    def test_drag_release_builds_settle_animation_from_current_pose(self) -> None:
        buddy = SimpleNamespace(
            _drag_frame_index=4,
            _current_animation="dragged",
            _active_animation=None,
            _pending_animation=None,
            player=Mock(),
            queue_draw=Mock(),
        )

        Buddy._play_drag_settle(buddy)

        settle = buddy.player.play.call_args.args[0]
        self.assertEqual(
            tuple(frame.sprite for frame in settle.frames),
            ("drag/drag_settle_right.png", "drag/drag_settle_neutral.png"),
        )
        self.assertEqual(buddy._pending_animation, "idle")

    def test_pickup_completion_enters_the_existing_drag_visual(self) -> None:
        pickup = Animation("pickup", (), 120)
        buddy = SimpleNamespace(
            _active_animation=pickup,
            _current_animation="pickup",
            _transition_to=Mock(),
            _drag_motion=SimpleNamespace(reset=Mock()),
            _drag_frame_index=4,
            _play_drag_pose=Mock(),
        )

        Buddy._finish_reaction(buddy, pickup)

        buddy._transition_to.assert_called_once_with(MochiState.DRAGGED)
        buddy._drag_motion.reset.assert_called_once()
        self.assertEqual(buddy._drag_frame_index, 0)
        buddy._play_drag_pose.assert_called_once()

    def test_drag_visual_setup_does_not_replace_active_pickup(self) -> None:
        buddy = SimpleNamespace(
            _last_drag_update_time=0.0,
            _drag_motion=SimpleNamespace(begin=Mock()),
            _drag_frame_index=4,
            _play_drag_pose=Mock(),
        )

        Buddy._begin_drag_visual(buddy, 10.0, 20.0)

        buddy._drag_motion.begin.assert_called_once()
        self.assertEqual(buddy._drag_frame_index, 1)
        buddy._play_drag_pose.assert_not_called()

    def test_release_cancels_pickup_and_uses_the_normal_settle_path(self) -> None:
        buddy = SimpleNamespace(
            _press=(1, 1),
            _drag_started=True,
            _drag_move_started=True,
            _drag_sample_position=(1, 1),
            _drag_sample_time=1.0,
            state=SimpleNamespace(current=MochiState.PICKUP),
            _drag_motion=SimpleNamespace(reset=Mock()),
            _transition_to=Mock(),
            _play_drag_settle=Mock(),
            react_to_click=Mock(),
        )

        Buddy._on_released(buddy, None, 1, 0.0, 0.0)

        buddy._transition_to.assert_called_once_with(MochiState.IDLE)
        buddy._play_drag_settle.assert_called_once()
        buddy.react_to_click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
