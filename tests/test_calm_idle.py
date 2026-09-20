"""Regression coverage for Mochi's calmer standing-idle cadence."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.buddy import Buddy
from mochi.sprites import ANIMATIONS


def test_standing_idle_uses_one_static_authored_frame() -> None:
    buddy = SimpleNamespace(
        IDLE_BREATHING_ENABLED=False,
        _animation_name_for_mood=lambda name: name,
    )

    idle = Buddy._animation_for(buddy, "idle")

    assert idle.name == "idle"
    assert idle.looping is True
    assert len(idle.frames) == 1
    assert idle.frames[0] == ANIMATIONS["idle"].frames[0]


def test_static_idle_preserves_mood_specific_art() -> None:
    buddy = SimpleNamespace(
        IDLE_BREATHING_ENABLED=False,
        _animation_name_for_mood=lambda _name: "sad_idle",
    )

    idle = Buddy._animation_for(buddy, "idle")

    assert idle.name == "sad_idle"
    assert len(idle.frames) == 1
    assert idle.frames[0] == ANIMATIONS["sad_idle"].frames[0]


def test_idle_opportunities_are_spaced_out() -> None:
    buddy = SimpleNamespace(
        _idle_action_source_id=None,
        IDLE_ACTION_INTERVAL_SECONDS=(20, 45),
        _choose_idle_action=Mock(),
    )

    with (
        patch("mochi.buddy.random.randint", return_value=31) as randint,
        patch("mochi.buddy.GLib.timeout_add_seconds", return_value=7) as add,
    ):
        Buddy._schedule_idle_action(buddy)

    randint.assert_called_once_with(20, 45)
    add.assert_called_once_with(31, buddy._choose_idle_action)
    assert buddy._idle_action_source_id == 7


def test_idle_movement_is_deliberately_low_probability() -> None:
    assert Buddy.IDLE_WALK_CHANCE == 0.10
    assert Buddy.IDLE_CATALOGUE_EMOTE_CHANCE == 0.20
