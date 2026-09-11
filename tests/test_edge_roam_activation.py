"""Regression coverage for immediate Edge Roaming activation.

Enabling Edge Roaming must send Mochi toward the nearest monitor edge right
away when he is free to walk, and must defer (never bypass the state
machine, never poll) when he is busy with a higher-priority state.
"""

import unittest
from unittest.mock import Mock

from mochi.config import Position
from mochi.presence.edge_roam_controls import EdgeRoamMixin
from mochi.state import MochiState


class _State:
    def __init__(self, current: MochiState) -> None:
        self.current = current


class _Config:
    def __init__(self) -> None:
        self.save_edge_roam = Mock()


class _Logger:
    def __init__(self) -> None:
        self.info = Mock()
        self.debug = Mock()


from types import SimpleNamespace


class _Placement:
    EDGE_PADDING_PX = 8
    BOTTOM_PADDING_PX = 12

    def __init__(self, origin: Position = Position(450, 300), *, width=100, height=100) -> None:
        geometry = SimpleNamespace(x=0, y=0, width=1000, height=800)
        monitor = SimpleNamespace(get_geometry=lambda: geometry)
        self.window = SimpleNamespace(get_default_size=lambda: (width, height))
        self.layer_shell_enabled = False
        self._monitor = monitor
        self.sync_from_window = Mock(return_value=origin)

    def _monitor_for_position(self, _x, _y):
        return self._monitor

    def _x11_coordinate_scale(self):
        return 1.0


class _BaseBuddy:
    """Stand-in for Buddy's relevant surface, without any real GTK/window.

    Mirrors the contract EdgeRoamMixin relies on via super(): _start_walk,
    _transition_to (with the same can_transition WALKING-only-from-IDLE
    semantics), _maybe_resume_ambient_activity, and the menu-closed hooks.
    """

    WALK_SPEED_PX_PER_SECOND = 72.0

    def __init__(self, *, state: MochiState, context_menu_open: bool) -> None:
        self.state = _State(state)
        self._context_menu_open = context_menu_open
        self._stay_put = False
        self._config = _Config()
        self._logger = _Logger()
        self._placement = _Placement()
        self._walk_motion = None
        self._walk_elapsed_ms = 0
        self._cancel_walk = Mock()
        self._play_animation = Mock()
        self.resumed_other_ambient = False

    def _transition_to(self, next_state: MochiState) -> bool:
        if next_state is MochiState.WALKING and self.state.current is not MochiState.IDLE:
            return False
        self.state.current = next_state
        return True

    def _start_walk(self) -> None:
        # Buddy's own default random walk; edge roam tests never fall
        # through to this because EdgeRoamMixin._start_walk short-circuits
        # to the edge-following implementation whenever _edge_roam is True.
        self._transition_to(MochiState.WALKING)

    def _maybe_resume_ambient_activity(self) -> bool:
        self.resumed_other_ambient = True
        return False

    def _on_context_menu_closed(self, _popover) -> None:
        self._context_menu_open = False

    def _on_developer_menu_closed(self, _popover) -> None:
        self._context_menu_open = False


class _Buddy(EdgeRoamMixin, _BaseBuddy):
    """The real EdgeRoamMixin layered on the minimal stand-in above."""


def _make_buddy(
    *,
    state: MochiState = MochiState.IDLE,
    edge_roam: bool = False,
    context_menu_open: bool = False,
    origin: Position = Position(450, 300),
) -> _Buddy:
    buddy = _Buddy(state=state, context_menu_open=context_menu_open)
    buddy._edge_roam = edge_roam
    buddy._placement = _Placement(origin)
    return buddy


class EdgeRoamActivationTests(unittest.TestCase):
    def test_idle_activation_starts_walk_toward_nearest_edge_immediately(self) -> None:
        buddy = _make_buddy(state=MochiState.IDLE)

        buddy._toggle_edge_roam(None)

        self.assertTrue(buddy._edge_roam)
        self.assertIs(buddy.state.current, MochiState.WALKING)
        self.assertFalse(buddy._edge_roam_start_pending)
        self.assertIsNotNone(buddy._walk_motion)
        # Origin (450, 300) projects to the nearest edge (top, y=8) without
        # crossing back through the interior.
        self.assertEqual(buddy._walk_motion.target[1], 8)

    def test_busy_state_activation_does_not_interrupt_and_sets_pending(self) -> None:
        for busy_state in (
            MochiState.DRAGGED,
            MochiState.PICKUP,
            MochiState.SLEEPING,
            MochiState.HEART,
        ):
            with self.subTest(busy_state=busy_state):
                buddy = _make_buddy(state=busy_state)

                buddy._toggle_edge_roam(None)

                self.assertTrue(buddy._edge_roam)
                self.assertIs(buddy.state.current, busy_state)
                self.assertTrue(buddy._edge_roam_start_pending)

    def test_pending_activation_starts_once_mochi_returns_to_idle(self) -> None:
        buddy = _make_buddy(state=MochiState.HEART)
        buddy._toggle_edge_roam(None)
        self.assertTrue(buddy._edge_roam_start_pending)

        # Mochi's reaction finishes and returns him to ambient IDLE through
        # the existing resume path (buddy.py's _finish_reaction/_resume_idle
        # eventually call _maybe_resume_ambient_activity).
        buddy.state.current = MochiState.IDLE
        started = buddy._maybe_resume_ambient_activity()

        self.assertTrue(started)
        self.assertIs(buddy.state.current, MochiState.WALKING)
        self.assertFalse(buddy._edge_roam_start_pending)
        # Edge roam owned ambient priority; the base ambient chain (watching/
        # searching/etc.) must not also be consulted.
        self.assertFalse(buddy.resumed_other_ambient)

    def test_disabling_while_pending_clears_the_flag(self) -> None:
        buddy = _make_buddy(state=MochiState.DRAGGED)
        buddy._toggle_edge_roam(None)
        self.assertTrue(buddy._edge_roam_start_pending)

        buddy._toggle_edge_roam(None)  # off

        self.assertFalse(buddy._edge_roam)
        self.assertFalse(buddy._edge_roam_start_pending)

        # Returning to IDLE afterwards must not start a walk: edge roam is off.
        buddy.state.current = MochiState.IDLE
        started = buddy._maybe_resume_ambient_activity()
        self.assertFalse(started)
        self.assertIs(buddy.state.current, MochiState.IDLE)

    def test_repeated_toggle_cycles_do_not_duplicate_state(self) -> None:
        buddy = _make_buddy(state=MochiState.IDLE)

        buddy._toggle_edge_roam(None)  # on: walk starts
        self.assertIs(buddy.state.current, MochiState.WALKING)
        self.assertFalse(buddy._edge_roam_start_pending)

        # Turning off does not interrupt an in-flight walk (existing, intentional
        # semantics preserved from before this fix); it simply stops future
        # edge-roam activations.
        buddy._toggle_edge_roam(None)  # off
        self.assertFalse(buddy._edge_roam)
        self.assertFalse(buddy._edge_roam_start_pending)
        self.assertIs(buddy.state.current, MochiState.WALKING)
        buddy._cancel_walk.assert_not_called()

        # The walk finishes naturally and Mochi returns to ambient IDLE.
        buddy.state.current = MochiState.IDLE
        started = buddy._maybe_resume_ambient_activity()
        self.assertFalse(started)  # edge roam is off; no new walk begins

        buddy._toggle_edge_roam(None)  # on again: walk starts again
        self.assertIs(buddy.state.current, MochiState.WALKING)
        self.assertFalse(buddy._edge_roam_start_pending)

        buddy._toggle_edge_roam(None)  # off again
        self.assertFalse(buddy._edge_roam)
        self.assertFalse(buddy._edge_roam_start_pending)

    def test_already_on_edge_does_not_jitter_or_reinitialize(self) -> None:
        # Origin already sits on the top edge (y matches the projected edge).
        buddy = _make_buddy(state=MochiState.IDLE, origin=Position(450, 8))

        buddy._toggle_edge_roam(None)

        self.assertIs(buddy.state.current, MochiState.WALKING)
        motion = buddy._walk_motion
        self.assertIsNotNone(motion)
        self.assertEqual(motion.origin[1], 8)

    def test_context_menu_open_defers_activation(self) -> None:
        buddy = _make_buddy(state=MochiState.IDLE, context_menu_open=True)

        buddy._toggle_edge_roam(None)

        self.assertTrue(buddy._edge_roam)
        self.assertTrue(buddy._edge_roam_start_pending)
        self.assertIsNot(buddy.state.current, MochiState.WALKING)

        # Menu closes through the real hook; the pending activation should
        # now proceed without any polling timer.
        buddy._on_context_menu_closed(None)

        self.assertIs(buddy.state.current, MochiState.WALKING)
        self.assertFalse(buddy._edge_roam_start_pending)

    def test_developer_menu_close_also_consumes_pending_activation(self) -> None:
        buddy = _make_buddy(state=MochiState.IDLE, context_menu_open=True)
        buddy._toggle_edge_roam(None)
        self.assertTrue(buddy._edge_roam_start_pending)

        buddy._on_developer_menu_closed(None)

        self.assertIs(buddy.state.current, MochiState.WALKING)
        self.assertFalse(buddy._edge_roam_start_pending)

    def test_disabled_edge_roam_never_starts_from_ambient_resume(self) -> None:
        buddy = _make_buddy(state=MochiState.IDLE, edge_roam=False)
        buddy._edge_roam_start_pending = False

        started = buddy._maybe_resume_ambient_activity()

        self.assertFalse(started)
        self.assertIs(buddy.state.current, MochiState.IDLE)
        self.assertTrue(buddy.resumed_other_ambient)


if __name__ == "__main__":
    unittest.main()
