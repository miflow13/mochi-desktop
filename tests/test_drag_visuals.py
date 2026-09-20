"""Exercise sampled movement through Buddy's real player and cached artwork."""

import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

import cairo

from mochi.animation import AnimationPlayer
from mochi.buddy import Buddy
from mochi.drag_motion import DragMotionModel, drag_settle_sprite
from mochi.interaction_tuning import InteractionTuning
from mochi.sprites import ANIMATIONS, SpriteAtlas
from mochi.state import MochiState, StateMachine


class DragVisualTests(unittest.TestCase):
    def setUp(self) -> None:
        self.buddy = SimpleNamespace(
            state=StateMachine(),
            _tuning=InteractionTuning(),
            _drag_motion=DragMotionModel(),
            _drag_started=True,
            _drag_visual_key=None,
            _drag_neutral_since=None,
            _drag_sample_position=None,
            _drag_sample_time=None,
            _drag_frame_index=0,
            _current_animation="idle",
            _active_animation=ANIMATIONS["idle"],
            _pending_animation=None,
            _placement=SimpleNamespace(
                layer_shell_enabled=False, sync_from_window=Mock(),
            ),
            _logger=Mock(),
            _update_pointer_cursor=Mock(),
            _cancel_active_emote=Mock(),
            _click_reactions=SimpleNamespace(consume=Mock(return_value=False)),
            _maybe_resume_ambient_activity=Mock(return_value=False),
            queue_draw=Mock(),
            TICK_MS=Buddy.TICK_MS,
            atlas=SpriteAtlas(),
        )
        for name in (
            "_animation_name_for_mood", "_animation_for", "_is_idle_visual_active",
            "_play_drag_pose", "_sample_x11_drag", "_transition_to",
            "_play_animation", "_finish_reaction", "_play_drag_settle",
        ):
            setattr(self.buddy, name, MethodType(getattr(Buddy, name), self.buddy))
        self.buddy.player = AnimationPlayer(self.buddy._finish_reaction)
        self.buddy._play_animation("idle")
        self.time = 10.0
        self.x = 0

    def sample(self, delta: int) -> None:
        self.time += 0.016
        self.x += delta
        self.buddy._placement.sync_from_window.return_value = SimpleNamespace(
            x=self.x, y=0,
        )
        with patch("mochi.buddy.time.monotonic", return_value=self.time):
            Buddy._tick(self.buddy)

    def render(self) -> bytes:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 256, 256)
        Buddy._draw(self.buddy, None, cairo.Context(surface), 256, 256)
        surface.flush()
        return bytes(surface.get_data())

    def test_soft_and_medium_reversals_render_on_the_next_sample(self) -> None:
        # Filenames describe trailing lean: pointer left -> right-lean art,
        # pointer right -> left-lean art. Two px/tick is soft; ten is medium.
        for delta, strength in ((-2, "soft"), (2, "soft"), (-10, "medium"), (10, "medium")):
            with self.subTest(delta=delta, strength=strength):
                self.buddy._drag_motion.reset()
                self.buddy._drag_sample_position = None
                self.buddy.state.transition_to(MochiState.DRAGGED)
                for _ in range(30):
                    self.sample(delta)
                lean = "right" if delta < 0 else "left"
                self.assertEqual(
                    self.buddy.player.frame.sprite, f"drag/drag_{lean}_{strength}.png",
                )
                before = self.render()
                self.buddy.queue_draw.reset_mock()
                self.sample(-delta)
                lean = "left" if delta < 0 else "right"
                self.assertEqual(
                    self.buddy.player.frame.sprite, f"drag/drag_{lean}_{strength}.png",
                )
                self.assertTrue(before != self.render(), "Reversal must change rendered pixels")
                self.buddy.queue_draw.assert_called_once_with()
                # Static drag selection must not wait for or advance the 167 ms loop.
                self.assertEqual(self.buddy.player.elapsed_ms, 0)

    def test_unchanged_motion_does_not_restart_the_selected_visual(self) -> None:
        self.buddy.state.transition_to(MochiState.DRAGGED)
        for _ in range(40):
            self.sample(2)
        with patch.object(self.buddy.player, "play", wraps=self.buddy.player.play) as play:
            self.sample(2)
            self.sample(2)
        play.assert_not_called()

    def test_reversals_preserve_pickup_sway_drop_and_idle(self) -> None:
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                self.buddy._drag_started = True
                self.assertTrue(Buddy._begin_pickup(self.buddy))
                self.sample(10 * direction)
                self.sample(-10 * direction)
                self.assertEqual(self.buddy.state.current, MochiState.PICKUP)
                self.assertEqual(self.buddy.player.animation.name, "pickup")
                for _ in range(10):
                    self.sample(10 * direction)
                self.assertEqual(self.buddy.state.current, MochiState.DRAGGED)
                for _ in range(40):
                    self.sample(0)
                self.assertEqual(self.buddy.player.animation.name, "sway_idle")
                self.sample(-10 * direction)
                self.assertEqual(self.buddy.player.animation.name, "dragged")
                lean = "right" if direction > 0 else "left"
                self.assertEqual(
                    drag_settle_sprite(self.buddy.player.frame.sprite),
                    f"drag/drag_settle_{lean}.png",
                )
                self.assertTrue(Buddy._finish_drag_interaction(self.buddy))
                self.assertEqual(self.buddy.state.current, MochiState.DROPPING)
                self.assertIs(self.buddy.player.animation, ANIMATIONS["drop"])
                for _ in range(30):
                    self.sample(0)
                self.assertEqual(self.buddy.state.current, MochiState.IDLE)
                self.assertIs(self.buddy.player.animation, ANIMATIONS["idle"])
