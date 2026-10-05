"""Standing-idle beats share one lifecycle: the timed look and the investigate beat."""

from __future__ import annotations

from unittest.mock import Mock

from mochi.animation import AnimationPlayer
from mochi.presence.idle_look import IdleLookMixin
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, StateMachine


class _BeatBase:
    def __init__(self, *args, **kwargs) -> None:
        # Preview mode keeps IdleLookMixin from arming real GLib timers.
        self._preview_mode = True
        self._presence_shutting_down = False
        self._user_idle = False
        self.state = StateMachine()
        self.player = AnimationPlayer(on_finished=self._finish_reaction)
        self.player.play(ANIMATIONS["idle"], frame_index=2, elapsed_ms=40)
        self._current_animation = "idle"
        self._active_animation = ANIMATIONS["idle"]
        self._pending_animation = None
        self._logger = Mock()
        self.queue_draw = Mock()
        self.base_finished: list[str] = []
        self.base_played: list[str] = []
        self.ambient_resumes = 0

    def _is_idle_visual_active(self) -> bool:
        return (
            self.state.current is MochiState.IDLE
            and self._current_animation == "idle"
            and self.player.animation is not None
        )

    def _animation_for(self, name: str):
        return ANIMATIONS[name]

    def _finish_reaction(self, finished_animation) -> None:
        self.base_finished.append(finished_animation.name)

    def _play_animation(self, name: str, after: str | None = None) -> None:
        self.base_played.append(name)
        self._current_animation = name

    def _maybe_resume_ambient_activity(self) -> bool:
        self.ambient_resumes += 1
        return False

    def _start_typing_emote(self) -> bool:
        self.base_played.append("typing")
        return True

    def shutdown_presence(self) -> None:
        pass


class BeatHarness(IdleLookMixin, _BeatBase):
    pass


def _finish_current_animation(buddy: BeatHarness) -> None:
    buddy.player.tick(60_000)


def test_investigate_beat_plays_without_claiming_behavior_state() -> None:
    buddy = BeatHarness()

    assert buddy._play_idle_beat("investigate") is True

    assert buddy._idle_look_active is True
    assert buddy._idle_beat_animation == "investigate"
    assert buddy._current_animation == "investigate"
    assert buddy.player.animation is ANIMATIONS["investigate"]
    assert buddy.state.current is MochiState.IDLE


def test_investigate_beat_resumes_idle_where_it_left_off() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    _finish_current_animation(buddy)

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy._current_animation == "idle"
    assert buddy.player.animation is ANIMATIONS["idle"]
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)
    assert buddy.ambient_resumes == 1
    assert buddy.base_finished == []


def test_beat_refuses_when_not_standing_idle() -> None:
    buddy = BeatHarness()
    buddy.state.transition_to(MochiState.TYPING)

    assert buddy._play_idle_beat("investigate") is False

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.player.animation is ANIMATIONS["idle"]


def test_typing_during_beat_restores_idle_before_typing() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    assert buddy._start_typing_emote() is True

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.base_played == ["typing"]
    assert buddy.ambient_resumes == 0


def test_other_animation_during_beat_restores_idle_first() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    buddy._play_animation("bounce")

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.base_played == ["bounce"]


def test_timed_look_uses_the_same_lifecycle() -> None:
    buddy = BeatHarness()

    assert buddy._play_idle_look() is True
    assert buddy._idle_beat_animation == "look"
    _finish_current_animation(buddy)

    assert buddy._idle_look_active is False
    assert buddy._current_animation == "idle"
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)


def test_look_timer_firing_mid_beat_reschedules_instead_of_playing() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True
    buddy._schedule_idle_look = Mock()

    assert buddy._try_idle_look() is False  # GLib.SOURCE_REMOVE

    buddy._schedule_idle_look.assert_called_once_with()
    assert buddy._idle_beat_animation == "investigate"


def test_shutdown_clears_the_active_beat() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    buddy.shutdown_presence()

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
