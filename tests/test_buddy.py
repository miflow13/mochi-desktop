import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.buddy import Buddy


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


if __name__ == "__main__":
    unittest.main()
