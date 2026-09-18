"""Regression coverage for Mochi's bond-aware emote catalogue."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.care import BondState, bond_xp_required
from mochi.presence.emote_catalogue import (
    EMOTE_CATALOGUE,
    EMOTES_BY_ID,
    EmoteCatalogueMixin,
    bond_xp_until_level,
    emote_status_text,
    next_emote_unlock,
)
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, PresentationState, StateMachine


def _harness(*, bond: BondState, state: MochiState = MochiState.IDLE):
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._bond_state = bond
    buddy.state = StateMachine()
    buddy.state.current = state
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


def test_catalogue_contains_unlocked_locked_and_future_placeholder_emotes() -> None:
    assert tuple(emote.id for emote in EMOTE_CATALOGUE) == (
        "heart",
        "bounce",
        "squish",
        "look",
        "dance",
        "mystery-1",
        "mystery-2",
        "mystery-3",
    )

    state = BondState(level=1, xp=0)
    assert EMOTES_BY_ID["heart"].is_unlocked(state)
    assert not EMOTES_BY_ID["look"].is_unlocked(state)
    assert not EMOTES_BY_ID["mystery-1"].is_unlocked(BondState(level=99, xp=0))
    assert emote_status_text(EMOTES_BY_ID["mystery-1"], state) == "Coming soon"


def test_exact_xp_remaining_to_level_three_uses_current_progress() -> None:
    state = BondState(level=1, xp=100)

    assert bond_xp_until_level(state, 3) == (
        bond_xp_required(1) - 100 + bond_xp_required(2)
    )


def test_next_unlock_advances_from_look_to_dance() -> None:
    level_one = BondState(level=1, xp=0)
    level_three = BondState(level=3, xp=0)
    level_five = BondState(level=5, xp=0)

    assert next_emote_unlock(level_one).id == "look"
    assert next_emote_unlock(level_three).id == "dance"
    assert next_emote_unlock(level_five) is None


def test_locked_emote_cannot_be_dispatched_before_required_bond_level() -> None:
    buddy = _harness(bond=BondState(level=2, xp=0))

    assert EmoteCatalogueMixin._start_manual_emote(buddy, "look") is False

    buddy._mark_interaction.assert_not_called()
    buddy._play_idle_look.assert_not_called()


def test_placeholder_emote_can_never_be_dispatched_even_at_high_bond() -> None:
    buddy = _harness(bond=BondState(level=99, xp=0))

    assert EmoteCatalogueMixin._start_manual_emote(buddy, "mystery-1") is False

    buddy._mark_interaction.assert_not_called()
    buddy._play_animation.assert_not_called()


def test_level_three_unlocks_manual_look() -> None:
    buddy = _harness(bond=BondState(level=3, xp=0))

    assert EmoteCatalogueMixin._start_manual_emote(buddy, "look") is True

    buddy._play_idle_look.assert_called_once_with()


def test_level_five_manual_dance_is_one_authored_cycle() -> None:
    buddy = _harness(bond=BondState(level=5, xp=0))

    assert EmoteCatalogueMixin._start_manual_emote(buddy, "dance") is True

    buddy._transition_to.assert_called_once_with(MochiState.DANCING)
    played = buddy.player.play.call_args.args[0]
    assert played.name == "dance"
    assert played.looping is False
    assert buddy._pending_animation == "idle"


def test_manual_emote_does_not_interrupt_level_up_presentation() -> None:
    buddy = _harness(bond=BondState(level=5, xp=0))
    buddy.state.transition_presentation(PresentationState.LEVEL_UP)

    assert EmoteCatalogueMixin._start_manual_emote(buddy, "heart") is False

    buddy._start_heart_emote.assert_not_called()


def test_unlocked_selection_waits_for_catalogue_close_before_dispatch() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._bond_state = BondState(level=3, xp=0)
    buddy._pending_manual_emote = None
    buddy._emote_catalogue_window = SimpleNamespace(popdown=Mock())
    buddy._context_menu_open = True
    buddy._dispatch_manual_emote = Mock()

    EmoteCatalogueMixin._choose_manual_emote(buddy, "look")
    assert buddy._pending_manual_emote == "look"
    buddy._emote_catalogue_window.popdown.assert_called_once_with()

    with patch("mochi.presence.emote_catalogue.GLib.idle_add") as idle_add:
        EmoteCatalogueMixin._on_emote_catalogue_closed(
            buddy,
            buddy._emote_catalogue_window,
        )

    assert buddy._context_menu_open is False
    assert buddy._pending_manual_emote is None
    idle_add.assert_called_once_with(buddy._dispatch_manual_emote, "look")


def test_locked_selection_is_ignored_without_closing_catalogue() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._bond_state = BondState(level=1, xp=0)
    buddy._pending_manual_emote = None
    buddy._emote_catalogue_window = SimpleNamespace(popdown=Mock())

    EmoteCatalogueMixin._choose_manual_emote(buddy, "dance")

    assert buddy._pending_manual_emote is None
    buddy._emote_catalogue_window.popdown.assert_not_called()
