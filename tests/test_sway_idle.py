import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.buddy import Buddy
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class BuddyHeldSwayTests(unittest.TestCase):
    def test_neutral_held_pose_enters_sway_loop(self) -> None:
        buddy = SimpleNamespace(
            _drag_motion=SimpleNamespace(
                pose_sprite=Mock(return_value="drag/drag_neutral.png"),
                horizontal_intensity=0.0,
                body_sway=0.0,
            ),
            _drag_frame_index=4,
            _drag_visual_key=None,
            _current_animation="dragged",
            _active_animation=ANIMATIONS["dragged"],
            _pending_animation=None,
            _drag_neutral_since=None,
            player=Mock(),
            _logger=Mock(),
            queue_draw=Mock(),
        )

        with patch("mochi.buddy.time.monotonic", side_effect=(10.0, 10.11)):
            Buddy._play_drag_pose(buddy)
            buddy.player.play.assert_not_called()
            Buddy._play_drag_pose(buddy)

        self.assertEqual(buddy._current_animation, "sway_idle")
        self.assertEqual(buddy._drag_frame_index, 0)
        self.assertEqual(buddy._drag_visual_key, ("sway_idle", 0))
        buddy.player.play.assert_called_once_with(ANIMATIONS["sway_idle"])
        buddy.queue_draw.assert_called_once_with()

    def test_repeated_neutral_samples_do_not_restart_sway_loop(self) -> None:
        buddy = SimpleNamespace(
            _drag_motion=SimpleNamespace(
                pose_sprite=Mock(return_value="drag/drag_neutral.png"),
                horizontal_intensity=0.0,
                body_sway=0.0,
            ),
            _drag_frame_index=0,
            _drag_visual_key=("sway_idle", 0),
            _current_animation="sway_idle",
            _active_animation=ANIMATIONS["sway_idle"],
            _pending_animation=None,
            _drag_neutral_since=1.0,
            player=Mock(),
            _logger=Mock(),
            queue_draw=Mock(),
        )

        Buddy._play_drag_pose(buddy)

        buddy.player.play.assert_not_called()
        buddy.queue_draw.assert_not_called()

    def test_directional_motion_interrupts_sway_immediately(self) -> None:
        buddy = SimpleNamespace(
            _drag_motion=SimpleNamespace(
                pose_sprite=Mock(return_value="drag/drag_left_soft.png"),
                horizontal_intensity=0.30,
                body_sway=-0.1,
            ),
            _drag_frame_index=0,
            _drag_visual_key=("sway_idle", 0),
            _current_animation="sway_idle",
            _active_animation=ANIMATIONS["sway_idle"],
            _pending_animation=None,
            _drag_neutral_since=1.0,
            player=Mock(),
            queue_draw=Mock(),
        )

        Buddy._play_drag_pose(buddy)

        self.assertEqual(buddy._current_animation, "dragged")
        self.assertEqual(buddy._drag_frame_index, 1)
        self.assertNotEqual(buddy._drag_visual_key, ("sway_idle", 0))
        buddy.player.play.assert_called_once()

    def test_small_directional_jitter_does_not_interrupt_sway(self) -> None:
        buddy = SimpleNamespace(
            _drag_motion=SimpleNamespace(
                pose_sprite=Mock(return_value="drag/drag_left_soft.png"),
                horizontal_intensity=0.14,
                body_sway=-0.05,
            ),
            _drag_frame_index=0,
            _drag_visual_key=("sway_idle", 0),
            _current_animation="sway_idle",
            _active_animation=ANIMATIONS["sway_idle"],
            _pending_animation=None,
            _drag_neutral_since=1.0,
            player=Mock(),
            queue_draw=Mock(),
        )

        with patch("mochi.buddy.time.monotonic", return_value=2.0):
            Buddy._play_drag_pose(buddy)

        self.assertEqual(buddy._current_animation, "sway_idle")
        self.assertEqual(buddy._drag_frame_index, 0)
        self.assertEqual(buddy._drag_visual_key, ("sway_idle", 0))
        buddy.player.play.assert_not_called()
        buddy.queue_draw.assert_not_called()

    def test_sway_manifest_uses_authored_ten_frame_loop(self) -> None:
        sway = ANIMATIONS["sway_idle"]

        self.assertEqual(len(sway.frames), 10)
        self.assertEqual(sway.frame_duration_ms, 120)
        self.assertTrue(sway.looping)
        self.assertEqual(
            tuple(frame.sprite for frame in sway.frames),
            tuple(f"sway_idle/sway_idle_{index:02d}.png" for index in range(1, 11)),
        )

    def test_tick_advances_sway_while_drag_state_is_held(self) -> None:
        buddy = SimpleNamespace(
            state=SimpleNamespace(current=MochiState.DRAGGED),
            _preview_mode=False,
            _placement=SimpleNamespace(layer_shell_enabled=True),
            _last_drag_update_time=10.0,
            _current_animation="sway_idle",
            player=Mock(),
            queue_draw=Mock(),
            _sample_x11_drag=Mock(),
            _settle_drag_visual=Mock(),
            _advance_walk=Mock(),
        )
        buddy.player.tick.return_value = True

        # Keep the layer-shell idle-settle condition false for this unit test.
        from unittest.mock import patch
        with patch("mochi.buddy.time.monotonic", return_value=10.0):
            self.assertTrue(Buddy._tick(buddy))

        buddy.player.tick.assert_called_once_with(Buddy.TICK_MS)
        buddy.queue_draw.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
