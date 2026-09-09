import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.animation import Animation
from mochi.buddy import Buddy
from mochi.sprites import ANIMATIONS
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
            _drag_started=True,
            state=SimpleNamespace(current=MochiState.PICKUP),
            _transition_to=Mock(),
            _drag_motion=SimpleNamespace(reset=Mock()),
            _drag_frame_index=4,
            _play_drag_pose=Mock(),
        )

        Buddy._finish_reaction(buddy, pickup)

        buddy._transition_to.assert_called_once_with(MochiState.DRAGGED)
        buddy._drag_motion.reset.assert_not_called()
        self.assertEqual(buddy._drag_frame_index, 4)
        buddy._play_drag_pose.assert_called_once()

    def test_rejected_pickup_does_not_replace_the_active_animation(self) -> None:
        buddy = SimpleNamespace(
            _cancel_active_emote=Mock(),
            _transition_to=Mock(return_value=False),
            _play_animation=Mock(),
        )

        self.assertFalse(Buddy._begin_pickup(buddy))

        buddy._play_animation.assert_not_called()

    def test_drag_visual_setup_does_not_replace_active_pickup(self) -> None:
        buddy = SimpleNamespace(
            _last_drag_update_time=0.0,
            _drag_motion=SimpleNamespace(begin=Mock()),
            _drag_frame_index=4,
            _play_drag_pose=Mock(),
        )

        Buddy._begin_drag_visual(buddy, 10.0, 20.0)

        buddy._drag_motion.begin.assert_called_once()
        self.assertEqual(buddy._drag_frame_index, 0)
        self.assertIsNone(buddy._drag_visual_key)
        buddy._play_drag_pose.assert_not_called()

    def test_pickup_motion_is_sampled_without_replacing_pickup_art(self) -> None:
        buddy = SimpleNamespace(
            state=SimpleNamespace(current=MochiState.PICKUP),
            _last_drag_update_time=0.0,
            _drag_motion=SimpleNamespace(update=Mock()),
            _play_drag_pose=Mock(),
        )

        with patch("mochi.buddy.time.monotonic", return_value=5.0):
            Buddy._update_drag_visual(buddy, 10.0, 20.0)

        buddy._drag_motion.update.assert_called_once_with(10.0, 20.0, 5.0)
        buddy._play_drag_pose.assert_not_called()

    def test_repeated_same_drag_pose_does_not_restart_player(self) -> None:
        buddy = SimpleNamespace(
            _drag_motion=SimpleNamespace(
                pose_sprite=Mock(return_value="drag/drag_left_soft.png"),
                body_sway=-0.09,
            ),
            _drag_frame_index=0,
            _drag_visual_key=None,
            player=Mock(),
            _current_animation="pickup",
            _active_animation=None,
            _pending_animation=None,
            queue_draw=Mock(),
        )

        Buddy._play_drag_pose(buddy)
        Buddy._play_drag_pose(buddy)

        buddy.player.play.assert_called_once()
        buddy.queue_draw.assert_called_once()

    def test_release_cancels_pickup_and_uses_the_normal_settle_path(self) -> None:
        buddy = SimpleNamespace(
            _press=(1, 1),
            _drag_started=True,
            _drag_move_started=True,
            _drag_release_handled=False,
            _drag_sample_position=(1, 1),
            _drag_sample_time=1.0,
            _drag_visual_key=("drag/drag_left_soft.png", 2),
            state=SimpleNamespace(current=MochiState.PICKUP),
            _drag_motion=SimpleNamespace(reset=Mock()),
            _transition_to=Mock(),
            _play_drag_settle=Mock(),
            react_to_click=Mock(),
        )
        buddy._finish_drag_interaction = lambda: Buddy._finish_drag_interaction(buddy)

        Buddy._on_released(buddy, None, 1, 0.0, 0.0)

        buddy._transition_to.assert_called_once_with(MochiState.IDLE)
        buddy._play_drag_settle.assert_called_once()
        buddy._drag_motion.reset.assert_called_once()
        self.assertTrue(buddy._drag_release_handled)
        self.assertIsNone(buddy._drag_visual_key)
        buddy.react_to_click.assert_not_called()

    def test_drag_end_recovers_state_when_click_release_is_not_delivered(self) -> None:
        buddy = SimpleNamespace(
            _drag_started=True,
            _drag_release_handled=False,
            _drag_end_handled=False,
            _drag_move_started=True,
            _drag_sample_position=(1, 1),
            _drag_sample_time=1.0,
            _drag_visual_key=("drag/drag_right_soft.png", -2),
            state=SimpleNamespace(current=MochiState.DRAGGED),
            _drag_motion=SimpleNamespace(reset=Mock()),
            _transition_to=Mock(),
            _play_drag_settle=Mock(),
            _placement=SimpleNamespace(layer_shell_enabled=True, position=(10, 20)),
            _config=SimpleNamespace(save_position=Mock()),
            _sound=SimpleNamespace(play=Mock()),
        )
        buddy._finish_drag_interaction = lambda: Buddy._finish_drag_interaction(buddy)

        Buddy._on_drag_end(buddy, None, 5.0, 0.0)

        self.assertFalse(buddy._drag_started)
        self.assertTrue(buddy._drag_release_handled)
        buddy._play_drag_settle.assert_called_once()
        buddy._config.save_position.assert_called_once_with((10, 20))


class BuddyContextMenuTests(unittest.TestCase):
    def test_menu_action_waits_for_closed_and_one_idle_turn(self) -> None:
        action = Mock()
        buddy = SimpleNamespace(
            _pending_context_action=None,
            _context_menu_open=True,
            _context_menu=SimpleNamespace(popdown=Mock()),
            _logger=Mock(),
        )
        buddy._dispatch_context_action = Buddy._dispatch_context_action.__get__(buddy)

        Buddy._close_context_menu_then(buddy, action)

        action.assert_not_called()
        buddy._context_menu.popdown.assert_called_once()
        with patch("mochi.buddy.GLib.idle_add") as idle_add:
            Buddy._on_context_menu_closed(buddy, None)

        self.assertFalse(buddy._context_menu_open)
        action.assert_not_called()
        idle_add.assert_called_once_with(buddy._dispatch_context_action, action)
        self.assertFalse(buddy._dispatch_context_action(action))
        action.assert_called_once()


class BuddyEmoteTests(unittest.TestCase):
    def test_hover_heart_fires_once_until_pointer_leaves(self) -> None:
        buddy = SimpleNamespace(
            _hovered=False,
            _mark_interaction=Mock(),
            _start_heart_emote=Mock(),
        )

        Buddy._on_enter(buddy, None, 0.0, 0.0)
        Buddy._on_enter(buddy, None, 0.0, 0.0)

        buddy._start_heart_emote.assert_called_once()
        Buddy._on_leave(buddy, None)
        Buddy._on_enter(buddy, None, 0.0, 0.0)
        self.assertEqual(buddy._start_heart_emote.call_count, 2)

    def test_heart_respects_cooldown_and_idle_priority(self) -> None:
        buddy = SimpleNamespace(
            state=SimpleNamespace(current=MochiState.IDLE),
            _context_menu_open=False,
            player=SimpleNamespace(animation=ANIMATIONS["idle"]),
            _last_heart_started=9.0,
            _tuning=SimpleNamespace(hover_heart_cooldown_seconds=2.0),
            _transition_to=Mock(return_value=True),
            _play_animation=Mock(),
        )

        with patch("mochi.buddy.time.monotonic", return_value=10.0):
            self.assertFalse(Buddy._start_heart_emote(buddy))
        buddy.state.current = MochiState.DRAGGED
        with patch("mochi.buddy.time.monotonic", return_value=12.0):
            self.assertFalse(Buddy._start_heart_emote(buddy))

        buddy._play_animation.assert_not_called()

    def test_computer_emote_plays_single_animation(self) -> None:
        buddy = SimpleNamespace(
            state=SimpleNamespace(current=MochiState.IDLE),
            _context_menu_open=False,
            player=SimpleNamespace(animation=ANIMATIONS["idle"]),
            _transition_to=Mock(return_value=True),
            _computer_idle_source_id=None,
            _play_animation=Mock(),
        )

        self.assertTrue(Buddy._start_computer_emote(buddy))

        buddy._transition_to.assert_called_once_with(MochiState.COMPUTER)
        buddy._play_animation.assert_called_once_with(
            "computer",
            after="idle",
        )

    def test_direct_input_cancels_computer_emote_and_returns_to_idle(self) -> None:
        buddy = SimpleNamespace(
            state=SimpleNamespace(current=MochiState.COMPUTER),
            _transition_to=Mock(return_value=True),
            _play_animation=Mock(),
        )

        self.assertTrue(Buddy._cancel_active_emote(buddy))

        buddy._transition_to.assert_called_once_with(MochiState.IDLE)
        buddy._play_animation.assert_called_once_with("idle")

    def test_computer_idle_timer_cannot_stack(self) -> None:
        buddy = SimpleNamespace(
            _computer_idle_source_id=None,
            _try_computer_idle_emote=Mock(),
            _logger=Mock(),
        )

        with (
            patch("mochi.buddy.random.randint", return_value=60),
            patch("mochi.buddy.GLib.timeout_add_seconds", return_value=9) as add,
        ):
            Buddy._schedule_computer_idle_emote(buddy)
            Buddy._schedule_computer_idle_emote(buddy)

        add.assert_called_once_with(60, buddy._try_computer_idle_emote)


if __name__ == "__main__":
    unittest.main()
