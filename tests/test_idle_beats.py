"""Standing-idle beats share one lifecycle: the timed look and the investigate beat."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

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
        # Presentation as the base class saw it on entry, to pin restore-first.
        self.base_snapshots: list[tuple[bool, object, tuple[int, int]]] = []
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

    def _snapshot(self) -> tuple[bool, object, tuple[int, int]]:
        return (
            self._idle_look_active,
            self.player.animation,
            (self.player.frame_index, self.player.elapsed_ms),
        )

    def _play_animation(self, name: str, after: str | None = None) -> None:
        self.base_played.append(name)
        self.base_snapshots.append(self._snapshot())
        self._current_animation = name

    def _maybe_resume_ambient_activity(self) -> bool:
        self.ambient_resumes += 1
        return False

    def _start_typing_emote(self) -> bool:
        self.base_played.append("typing")
        self.base_snapshots.append(self._snapshot())
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
    assert buddy.player.animation is ANIMATIONS["idle"]
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)
    # Idle was already restored when the base class started typing.
    assert buddy.base_snapshots == [(False, ANIMATIONS["idle"], (2, 40))]


def test_other_animation_during_beat_restores_idle_first() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    buddy._play_animation("bounce")

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.base_played == ["bounce"]
    assert buddy._current_animation == "bounce"
    assert buddy.player.animation is ANIMATIONS["idle"]
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)
    assert buddy.base_snapshots == [(False, ANIMATIONS["idle"], (2, 40))]


def test_look_animation_during_investigate_restores_idle_first() -> None:
    # "look" is the timed beat's name, but it is not the active beat here, so
    # it must interrupt investigate like any other animation.
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    buddy._play_animation("look")

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.base_played == ["look"]
    assert buddy.base_snapshots == [(False, ANIMATIONS["idle"], (2, 40))]


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


def test_unknown_beat_name_raises_without_touching_state() -> None:
    buddy = BeatHarness()

    with pytest.raises(KeyError):
        buddy._play_idle_beat("not-a-beat")

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy._current_animation == "idle"
    assert buddy.player.animation is ANIMATIONS["idle"]
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)


def test_unknown_beat_name_leaves_the_armed_look_timer_alone() -> None:
    buddy = BeatHarness()
    buddy._idle_look_source_id = 77

    with patch("mochi.presence.idle_look.GLib.source_remove") as source_remove:
        with pytest.raises(KeyError):
            buddy._play_idle_beat("not-a-beat")

    source_remove.assert_not_called()
    assert buddy._idle_look_source_id == 77


def test_starting_a_beat_cancels_the_armed_look_timer() -> None:
    buddy = BeatHarness()
    buddy._idle_look_source_id = 77

    with patch("mochi.presence.idle_look.GLib.source_remove") as source_remove:
        assert buddy._play_idle_beat("investigate") is True

    source_remove.assert_called_once_with(77)
    assert buddy._idle_look_source_id is None


def test_refused_beat_keeps_the_armed_look_timer() -> None:
    buddy = BeatHarness()
    buddy.state.transition_to(MochiState.TYPING)
    buddy._idle_look_source_id = 77

    with patch("mochi.presence.idle_look.GLib.source_remove") as source_remove:
        assert buddy._play_idle_beat("investigate") is False

    source_remove.assert_not_called()
    assert buddy._idle_look_source_id == 77


def test_look_timer_is_rearmed_fresh_after_a_beat_started_off_timer() -> None:
    buddy = BeatHarness()
    buddy._preview_mode = False  # let the post-beat restore arm a real interval
    buddy._idle_look_source_id = 77

    with (
        patch("mochi.presence.idle_look.GLib.source_remove") as source_remove,
        patch(
            "mochi.presence.idle_look.GLib.timeout_add_seconds", return_value=99
        ) as timeout_add,
    ):
        assert buddy._play_idle_beat("investigate") is True
        _finish_current_animation(buddy)

    source_remove.assert_called_once_with(77)
    timeout_add.assert_called_once()
    assert buddy._idle_look_source_id == 99
