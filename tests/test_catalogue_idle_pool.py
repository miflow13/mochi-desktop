"""Behavior coverage for autonomous catalogue emotes."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

from mochi.behavior import ClickReactionBuffer
from mochi.buddy import Buddy
from mochi.state import MochiState, StateMachine


class IdleEmoteHarness:
    def __init__(self) -> None:
        self.state = StateMachine()
        self._logger = logging.getLogger(__name__)
        self._preview_mode = False
        self._user_idle = False
        self._context_menu_open = False
        self._current_animation = "idle"
        self._idle_action_source_id = None
        self._idle_resume_position = None
        self._click_reactions = ClickReactionBuffer()
        self.player = SimpleNamespace(animation=None, play=self._play)
        self.played = []
        self.walks = 0
        self._available_catalogue_emote_animations = lambda: ("dance",)
        self._play_animation("idle")

    def __getattr__(self, name):
        return getattr(Buddy, name).__get__(self)

    def _play(self, animation, **_kwargs) -> None:
        self.player.animation = animation
        self.played.append(animation)

    def queue_draw(self) -> None:
        pass

    def _schedule_idle_action(self) -> None:
        pass

    def _start_walk(self) -> None:
        self.walks += 1


def test_autonomous_catalogue_playback_forces_looping_emote_to_finish() -> None:
    buddy = IdleEmoteHarness()

    assert buddy._play_autonomous_catalogue_emote("dance") is True
    assert buddy.state.current is MochiState.IDLE_EMOTE
    assert buddy._active_animation.name == "dance"
    assert buddy._active_animation.looping is False
    assert buddy._active_animation.next_state == "idle"

    buddy._finish_reaction(buddy._active_animation)

    assert buddy.state.current is MochiState.IDLE
    assert buddy._current_animation == "idle"


def test_idle_emote_frequency_is_category_based_not_pool_size() -> None:
    buddy = IdleEmoteHarness()
    buddy._available_catalogue_emote_animations = lambda: tuple(
        f"emote_{index}" for index in range(100)
    )
    buddy._play_autonomous_catalogue_emote = lambda name: buddy.played.append(name) or True

    # Walk occupies [0.00, 0.25); catalogue emotes [0.25, 0.50).
    with (
        patch("mochi.buddy.random.random", return_value=0.30),
        patch("mochi.buddy.random.choice", return_value="emote_42"),
    ):
        buddy._choose_idle_action_with_walk(allow_walk=True)

    assert buddy.played[-1] == "emote_42"
    assert buddy.walks == 0


def test_stay_put_style_idle_selection_keeps_emotes_but_removes_walk_slot() -> None:
    buddy = IdleEmoteHarness()
    buddy._available_catalogue_emote_animations = lambda: ("wave",)
    buddy._play_autonomous_catalogue_emote = lambda name: buddy.played.append(name) or True

    with (
        patch("mochi.buddy.random.random", return_value=0.10),
        patch("mochi.buddy.random.choice", return_value="wave"),
    ):
        buddy._choose_idle_action_with_walk(allow_walk=False)

    assert buddy.played[-1] == "wave"
    assert buddy.walks == 0
