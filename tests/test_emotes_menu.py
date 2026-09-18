"""Regression coverage for the user-facing manual emotes menu."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.presence.emotes_menu import EMOTE_CHOICES, EmotesMenuMixin
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


def _harness(state: MochiState = MochiState.IDLE):
    buddy = object.__new__(EmotesMenuMixin)
    buddy.state = SimpleNamespace(current=state)
    buddy._logger = Mock()
    buddy._mark_interaction = Mock()
    buddy._cancel_hover_heart = Mock()
    buddy._cancel_idle_look = Mock(return_value=False)
    buddy._cancel_active_emote = Mock(return_value=False)
    buddy._cancel_walk = Mock()
    buddy._transition_to = Mock(
        side_effect=lambda next_state: (
            setattr(buddy.state, "current", next_state) or True
        )
    )
    buddy._play_animation = Mock()
    buddy._start_heart_emote = Mock(return_value=True)
    buddy._play_idle_look = Mock(return_value=True)
    buddy._sound = SimpleNamespace(play=Mock())
    buddy.player = Mock()
    buddy._current_animation = "idle"
    buddy._active_animation = ANIMATIONS["idle"]
    buddy._pending_animation = None
    buddy.queue_draw = Mock()
    return buddy


def test_user_emote_choices_are_intentional_and_finite() -> None:
    assert tuple(choice[2] for choice in EMOTE_CHOICES) == (
        "heart",
        "bounce",
        "squish",
        "look",
        "dance",
    )


def test_manual_heart_uses_existing_heart_path_and_ignores_hover_cooldown() -> None:
    buddy = _harness()

    assert EmotesMenuMixin._start_manual_emote(buddy, "heart") is True

    buddy._start_heart_emote.assert_called_once_with(ignore_cooldown=True)
    buddy._play_animation.assert_not_called()


def test_manual_squish_uses_existing_reaction_state_and_animation() -> None:
    buddy = _harness()

    assert EmotesMenuMixin._start_manual_emote(buddy, "squish") is True

    buddy._transition_to.assert_called_once_with(MochiState.SQUISHING)
    buddy._play_animation.assert_called_once_with("squish")


def test_manual_emote_interrupts_low_priority_contextual_activity() -> None:
    buddy = _harness(MochiState.WATCHING)

    def cancel_active() -> bool:
        buddy.state.current = MochiState.IDLE
        return True

    buddy._cancel_active_emote.side_effect = cancel_active

    assert EmotesMenuMixin._start_manual_emote(buddy, "bounce") is True

    buddy._cancel_active_emote.assert_called_once_with()
    buddy._transition_to.assert_called_once_with(MochiState.BOUNCING)
    buddy._play_animation.assert_called_once_with("bounce")


def test_manual_emote_never_interrupts_critical_interaction_state() -> None:
    buddy = _harness(MochiState.DRAGGED)

    assert EmotesMenuMixin._start_manual_emote(buddy, "heart") is False

    buddy._mark_interaction.assert_not_called()
    buddy._cancel_active_emote.assert_not_called()
    buddy._start_heart_emote.assert_not_called()


def test_manual_dance_is_exactly_one_authored_cycle() -> None:
    buddy = _harness()

    assert EmotesMenuMixin._play_manual_dance(buddy) is True

    buddy._transition_to.assert_called_once_with(MochiState.DANCING)
    played = buddy.player.play.call_args.args[0]
    assert played.name == "dance"
    assert played.looping is False
    assert buddy._pending_animation == "idle"
    buddy.queue_draw.assert_called_once_with()


def test_emote_selection_waits_for_picker_to_close_before_dispatch() -> None:
    buddy = object.__new__(EmotesMenuMixin)
    buddy._pending_manual_emote = None
    buddy._emotes_menu = SimpleNamespace(popdown=Mock())
    buddy._context_menu_open = True
    buddy._dispatch_manual_emote = Mock()

    EmotesMenuMixin._choose_manual_emote(buddy, "squish")
    assert buddy._pending_manual_emote == "squish"
    buddy._emotes_menu.popdown.assert_called_once_with()

    with patch("mochi.presence.emotes_menu.GLib.idle_add") as idle_add:
        EmotesMenuMixin._on_emotes_menu_closed(buddy, buddy._emotes_menu)

    assert buddy._context_menu_open is False
    assert buddy._pending_manual_emote is None
    idle_add.assert_called_once_with(buddy._dispatch_manual_emote, "squish")
