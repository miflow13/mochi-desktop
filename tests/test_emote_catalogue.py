"""Regression coverage for Mochi's bond-aware emote catalogue."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.care import BondState, bond_xp_required
from mochi.presence.emote_catalogue import (
    EMOTE_CATALOGUE,
    EMOTES_BY_ID,
    EmoteCatalogueMixin,
    EmoteCatalogueWindow,
    EmotePreview,
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
    assert emote_status_text(EMOTES_BY_ID["mystery-1"], state) == "COMING SOON"


def test_exact_xp_remaining_to_level_three_uses_current_progress() -> None:
    state = BondState(level=1, xp=100)

    assert bond_xp_until_level(state, 3) == (
        bond_xp_required(1) - 100 + bond_xp_required(2)
    )


def test_next_unlock_advances_from_look_to_dance() -> None:
    assert next_emote_unlock(BondState(level=1, xp=0)).id == "look"
    assert next_emote_unlock(BondState(level=3, xp=0)).id == "dance"
    assert next_emote_unlock(BondState(level=5, xp=0)) is None


def test_catalogue_is_large_card_grid_not_a_context_menu_feature() -> None:
    mixin_source = inspect.getsource(EmoteCatalogueMixin)
    window_source = inspect.getsource(EmoteCatalogueWindow)

    assert "_build_context_menu" not in mixin_source
    assert "DEFAULT_WIDTH = 900" in window_source
    assert "DEFAULT_HEIGHT = 680" in window_source
    assert "Gtk.Grid()" in window_source
    assert "index % 3" in window_source


def test_locked_previews_use_authored_sprite_alpha_as_silhouette() -> None:
    source = inspect.getsource(EmotePreview._draw)

    assert "mask_surface" in source
    assert "self._atlas.draw" in source


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


def test_unlocked_card_hides_window_then_dispatches_on_idle() -> None:
    window = object.__new__(EmoteCatalogueWindow)
    window._state = BondState(level=3, xp=0)
    window._on_emote_requested = Mock()
    window.hide = Mock()
    window._dispatch_card = Mock(return_value=False)

    with patch("mochi.presence.emote_catalogue.GLib.idle_add") as idle_add:
        EmoteCatalogueWindow._on_card_activate(window, "look")

    window.hide.assert_called_once_with()
    idle_add.assert_called_once_with(window._dispatch_card, "look")


def test_locked_card_does_not_hide_or_dispatch() -> None:
    window = object.__new__(EmoteCatalogueWindow)
    window._state = BondState(level=1, xp=0)
    window.hide = Mock()
    window._dispatch_card = Mock(return_value=False)

    with patch("mochi.presence.emote_catalogue.GLib.idle_add") as idle_add:
        EmoteCatalogueWindow._on_card_activate(window, "dance")

    window.hide.assert_not_called()
    idle_add.assert_not_called()
