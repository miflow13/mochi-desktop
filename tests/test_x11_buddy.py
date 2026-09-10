import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.state import MochiState
from mochi.x11_buddy import X11Buddy


class X11BuddyDragTests(unittest.TestCase):
    def test_motion_handler_never_starts_compositor_move(self) -> None:
        source = inspect.getsource(X11Buddy._on_motion)

        self.assertNotIn("surface.begin_move(", source)

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
