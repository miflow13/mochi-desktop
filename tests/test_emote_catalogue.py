"""Regression coverage for Mochi's bond-aware emote catalogue."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.care import BondState, bond_xp_required
from mochi.presence.emote_catalogue import (
    EMOTE_CATALOGUE,
    EMOTES_BY_ID,
    EmoteCatalogueCanvas,
    EmoteCatalogueMixin,
    EmoteCatalogueWindow,
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


def test_catalogue_uses_single_compact_canvas_without_scrolling() -> None:
    mixin_source = inspect.getsource(EmoteCatalogueMixin)
    window_source = inspect.getsource(EmoteCatalogueWindow)

    assert "_build_context_menu" not in mixin_source
    assert "DEFAULT_WIDTH = 900" in window_source
    assert "DEFAULT_HEIGHT = 680" in window_source
    assert "EmoteCatalogueCanvas" in window_source
    assert "Gtk.Grid()" not in window_source
    assert "Gtk.GridView" not in window_source
    assert "Gtk.ScrolledWindow" not in window_source


def test_canvas_retains_one_surface_and_no_card_widget_tree() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "Gtk.DrawingArea" in source
    assert "cairo.ImageSurface" in source
    assert "mask_surface" in source
    assert "Gtk.Button" not in source
    assert "Gtk.Picture" not in source


def test_canvas_has_no_scroll_path_or_pointer_motion_repaint() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "Gtk.ScrolledWindow" not in source
    assert "def refresh" in source
    assert "if state == self._state" in source
    assert "EventControllerMotion" not in source
    assert "def _on_motion" not in source


def test_canvas_is_a_read_only_collection_view() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "Gtk.GestureClick" not in source
    assert "def _on_click" not in source
    assert "def emote_at" not in source
    assert "Click to ask Mochi" not in source


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


def test_window_refresh_skips_identical_bond_state() -> None:
    window = object.__new__(EmoteCatalogueWindow)
    window._state = BondState(level=2, xp=33)
    window._canvas = SimpleNamespace(refresh=Mock())
    window._next_label = SimpleNamespace(set_text=Mock())
    window._progress = SimpleNamespace(set_fraction=Mock())

    changed = EmoteCatalogueWindow.refresh(
        window,
        BondState(level=2, xp=33),
    )

    assert changed is False
    window._canvas.refresh.assert_not_called()
    window._next_label.set_text.assert_not_called()
    window._progress.set_fraction.assert_not_called()


def test_hidden_catalogue_is_not_refreshed_on_each_bond_tick() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._bond_state = BondState(level=2, xp=44)
    buddy._emote_catalogue_window = SimpleNamespace(
        visible=False,
        refresh=Mock(),
    )

    EmoteCatalogueMixin._refresh_emote_catalogue(buddy)

    buddy._emote_catalogue_window.refresh.assert_not_called()


def test_visible_catalogue_refreshes_with_live_bond_progress() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._bond_state = BondState(level=2, xp=44)
    buddy._emote_catalogue_window = SimpleNamespace(
        visible=True,
        refresh=Mock(),
    )

    EmoteCatalogueMixin._refresh_emote_catalogue(buddy)

    buddy._emote_catalogue_window.refresh.assert_called_once_with(
        buddy._bond_state
    )


def test_show_catalogue_lazy_creates_then_forces_current_state_refresh() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._preview_mode = False
    buddy._bond_state = BondState(level=3, xp=12)
    window = SimpleNamespace(refresh=Mock(), present=Mock())
    buddy._ensure_emote_catalogue_window = Mock(return_value=window)

    EmoteCatalogueMixin._show_emote_catalogue(buddy)

    buddy._ensure_emote_catalogue_window.assert_called_once_with()
    window.refresh.assert_called_once_with(buddy._bond_state, force=True)
    window.present.assert_called_once_with()


def test_cumulative_xp_helper_is_cached() -> None:
    from mochi.presence.emote_catalogue import _bond_xp_to_level_start

    _bond_xp_to_level_start.cache_clear()
    state = BondState(level=1, xp=10)

    bond_xp_until_level(state, 5)
    first = _bond_xp_to_level_start.cache_info()
    bond_xp_until_level(state, 5)
    second = _bond_xp_to_level_start.cache_info()

    assert second.hits > first.hits


def test_catalogue_titlebar_uses_native_close_only_decoration() -> None:
    source = inspect.getsource(EmoteCatalogueWindow.__init__)

    assert "Gtk.HeaderBar()" in source
    assert "header.set_show_title_buttons(True)" in source
    assert 'header.set_decoration_layout(":close")' in source
    assert "self.window.set_titlebar(header)" in source


def test_window_refreshes_only_the_single_canvas() -> None:
    source = inspect.getsource(EmoteCatalogueWindow.refresh)

    assert "self._canvas.refresh(self._state)" in source
