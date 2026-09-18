"""Regression coverage for Mochi's bond-aware emote catalogue."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.care import BondState, bond_xp_required
from mochi.presence.emote_catalogue import (
    EMOTE_CATALOGUE,
    EMOTES_BY_ID,
    RARITY_STYLES,
    EmoteCatalogueCanvas,
    EmoteCatalogueMixin,
    EmoteCatalogueWindow,
    bond_xp_until_level,
    emote_status_text,
    next_emote_unlock,
)
from mochi.sprites import ANIMATIONS



def test_catalogue_contains_unlocked_locked_and_future_placeholder_emotes() -> None:
    assert tuple(emote.id for emote in EMOTE_CATALOGUE) == (
        "heart",
        "bounce",
        "squish",
        "side-eye",
        "look",
        "table-flip",
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


def test_catalogue_assigns_progressive_rarity_tiers() -> None:
    assert tuple(emote.rarity for emote in EMOTE_CATALOGUE) == (
        "common",
        "common",
        "uncommon",
        "uncommon",
        "rare",
        "rare",
        "epic",
        "legendary",
        "legendary",
        "legendary",
    )
    assert RARITY_STYLES["legendary"].ornament_count > RARITY_STYLES["epic"].ornament_count
    assert RARITY_STYLES["epic"].ornament_count > RARITY_STYLES["common"].ornament_count


def test_exact_xp_remaining_to_level_three_uses_current_progress() -> None:
    state = BondState(level=1, xp=100)

    assert bond_xp_until_level(state, 3) == (
        bond_xp_required(1) - 100 + bond_xp_required(2)
    )


def test_next_unlock_advances_from_look_to_dance() -> None:
    assert next_emote_unlock(BondState(level=1, xp=0)).id == "side-eye"
    assert next_emote_unlock(BondState(level=2, xp=0)).id == "look"
    assert next_emote_unlock(BondState(level=3, xp=0)).id == "dance"
    assert next_emote_unlock(BondState(level=5, xp=0)) is None


def test_catalogue_uses_single_compact_canvas_without_scrolling() -> None:
    mixin_source = inspect.getsource(EmoteCatalogueMixin)
    window_source = inspect.getsource(EmoteCatalogueWindow)

    assert "_build_context_menu" not in mixin_source
    assert "DEFAULT_WIDTH = 900" in window_source
    assert "DEFAULT_HEIGHT = 900" in window_source
    assert "EmoteCatalogueCanvas" in window_source
    assert "Gtk.Grid()" not in window_source
    assert "Gtk.GridView" not in window_source
    assert "Gtk.ScrolledWindow" not in window_source


def test_canvas_uses_long_two_column_rarity_cards() -> None:
    assert EmoteCatalogueCanvas.COLUMNS == 2
    assert EmoteCatalogueCanvas.CARD_WIDTH > EmoteCatalogueCanvas.CARD_HEIGHT * 3
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "RARITY_STYLES[emote.rarity]" in source
    assert "_draw_ornaments" in source


def test_canvas_caches_one_surface_per_card_and_no_card_widget_tree() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "Gtk.DrawingArea" in source
    assert "self._card_surfaces" in source
    assert "cairo.ImageSurface" in source
    assert "mask_surface" in source
    assert "Gtk.Button" not in source
    assert "Gtk.Picture" not in source


def test_canvas_hover_uses_motion_controller_without_click_dispatch() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "Gtk.ScrolledWindow" not in source
    assert "Gtk.EventControllerMotion" in source
    assert 'motion.connect("motion", self._on_motion)' in source
    assert 'motion.connect("leave", self._on_leave)' in source
    assert "Gtk.GestureClick" not in source
    assert "def _on_click" not in source


def test_canvas_refresh_is_keyed_to_level_not_exact_xp_state() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas.refresh)

    assert "state.level == previous.level" in source
    assert "state == self._state" not in source
    assert "self._render_card_surfaces()" in source


def test_card_rasterization_has_no_repeating_render_timer() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas._render_card_surfaces)

    assert "GLib.timeout_add" not in source
    assert "for emote in EMOTE_CATALOGUE" in source
    assert "self._card_surfaces = surfaces" in source
    assert source.count("self.queue_draw()") == 1


def test_canvas_is_a_read_only_collection_view() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)
    mixin_source = inspect.getsource(EmoteCatalogueMixin)

    assert "Gtk.GestureClick" not in source
    assert "def _on_click" not in source
    assert "Click to ask Mochi" not in source
    assert "_start_manual_emote" not in mixin_source
    assert "_play_manual_dance" not in mixin_source







def test_window_refresh_skips_identical_bond_state() -> None:
    window = object.__new__(EmoteCatalogueWindow)
    window._state = BondState(level=2, xp=33)
    window._unlock_all = False
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
    buddy._dev_unlock_all_emotes = False
    buddy._emote_catalogue_window = SimpleNamespace(
        visible=False,
        refresh=Mock(),
    )

    EmoteCatalogueMixin._refresh_emote_catalogue(buddy)

    buddy._emote_catalogue_window.refresh.assert_not_called()


def test_visible_catalogue_refreshes_with_live_bond_progress() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._bond_state = BondState(level=2, xp=44)
    buddy._dev_unlock_all_emotes = False
    buddy._emote_catalogue_window = SimpleNamespace(
        visible=True,
        refresh=Mock(),
    )

    EmoteCatalogueMixin._refresh_emote_catalogue(buddy)

    buddy._emote_catalogue_window.refresh.assert_called_once_with(
        buddy._bond_state,
        force=False,
        unlock_all=False,
    )


def test_show_catalogue_lazy_creates_and_reuses_cached_state_when_unchanged() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._preview_mode = False
    buddy._bond_state = BondState(level=3, xp=12)
    buddy._dev_unlock_all_emotes = False
    window = SimpleNamespace(refresh=Mock(), present=Mock())
    buddy._ensure_emote_catalogue_window = Mock(return_value=window)

    EmoteCatalogueMixin._show_emote_catalogue(buddy)

    buddy._ensure_emote_catalogue_window.assert_called_once_with()
    window.refresh.assert_called_once_with(
        buddy._bond_state,
        unlock_all=False,
    )
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
    assert "set_title_widget" not in source
    assert "self.window.set_titlebar(header)" in source


def test_catalogue_is_application_owned_not_transient_to_buddy() -> None:
    source = inspect.getsource(EmoteCatalogueWindow.__init__)

    assert "owner.get_application()" in source
    assert "Gtk.ApplicationWindow(application=application)" in source
    assert "set_transient_for" not in source
    assert "set_destroy_with_parent" not in source
    assert "self.window.set_hide_on_close(True)" in source
    assert 'connect("close-request"' not in source


def test_window_refreshes_only_the_single_canvas() -> None:
    source = inspect.getsource(EmoteCatalogueWindow.refresh)

    assert "self._canvas.refresh(" in source
    assert "unlock_all=self._unlock_all" in source


def test_locked_card_detail_is_static_across_xp_ticks() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas._detail)

    assert '"Keep bonding to discover this mood."' in source
    assert "bond_xp_until_level" not in source


def test_scale_notification_is_guarded_by_last_rendered_scale() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas._on_scale_factor_changed)

    assert "scale != self._render_scale" in source
    assert "self._render_card_surfaces()" in source


def test_card_hit_testing_ignores_gap_and_glow_padding() -> None:
    first_x, first_y = EmoteCatalogueCanvas._card_origin(0)
    second_x, second_y = EmoteCatalogueCanvas._card_origin(1)

    assert EmoteCatalogueCanvas.card_index_at(first_x + 10, first_y + 10) == 0
    assert EmoteCatalogueCanvas.card_index_at(second_x + 10, second_y + 10) == 1
    assert (
        EmoteCatalogueCanvas.card_index_at(
            first_x + EmoteCatalogueCanvas.CARD_WIDTH + 2,
            first_y + 10,
        )
        is None
    )


def test_hover_animation_is_short_lived_and_render_cache_independent() -> None:
    tick_source = inspect.getsource(EmoteCatalogueCanvas._tick_hover)
    motion_source = inspect.getsource(EmoteCatalogueCanvas._on_motion)

    assert "self._render_card_surfaces" not in tick_source
    assert "self._render_card_surfaces" not in motion_source
    assert "self.queue_draw()" in tick_source
    assert "self._hover_source_id = None" in tick_source
    assert "GLib.SOURCE_REMOVE" in tick_source


def test_only_rare_and_legendary_cards_get_persistent_rarity_glow() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas._draw_rarity_glow)

    assert 'emote.rarity == "rare"' in source
    assert 'emote.rarity == "legendary"' in source
    assert "else:" in source
    assert "return" in source
    assert "boost" in source


def test_hover_outline_applies_to_every_emote_without_making_cards_clickable() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas)

    assert "def _draw_hover_outline" in source
    assert "self._draw_hover_outline(context, emote" in source
    assert "Gtk.GestureClick" not in source


def test_hover_progress_handles_rapid_pointer_changes_and_converges() -> None:
    progress = tuple(0.0 for _ in EMOTE_CATALOGUE)

    for hovered in (0, 7, 2, 5, 1, None, 6, 3, None) * 8:
        progress, _animating = EmoteCatalogueCanvas._advance_hover_progress(
            progress,
            hovered,
        )
        assert all(0.0 <= value <= 1.0 for value in progress)

    animating = True
    for _ in range(64):
        progress, animating = EmoteCatalogueCanvas._advance_hover_progress(
            progress,
            None,
        )
        if not animating:
            break

    assert animating is False
    assert progress == tuple(0.0 for _ in EMOTE_CATALOGUE)


def test_hidden_catalogue_resets_hover_state() -> None:
    window = object.__new__(EmoteCatalogueWindow)
    window._canvas = SimpleNamespace(reset_hover=Mock())
    gtk_window = SimpleNamespace(get_visible=Mock(return_value=False))

    EmoteCatalogueWindow._on_visibility_changed(window, gtk_window)

    window._canvas.reset_hover.assert_called_once_with()


def test_explicit_hide_resets_hover_before_hiding_window() -> None:
    calls: list[str] = []
    window = object.__new__(EmoteCatalogueWindow)
    window._canvas = SimpleNamespace(reset_hover=lambda: calls.append("reset"))
    window.window = SimpleNamespace(hide=lambda: calls.append("hide"))

    EmoteCatalogueWindow.hide(window)

    assert calls == ["reset", "hide"]


def test_destroy_resets_hover_before_destroying_window() -> None:
    calls: list[str] = []
    window = object.__new__(EmoteCatalogueWindow)
    window._canvas = SimpleNamespace(reset_hover=lambda: calls.append("reset"))
    window.window = SimpleNamespace(destroy=lambda: calls.append("destroy"))

    EmoteCatalogueWindow.destroy(window)

    assert calls == ["reset", "destroy"]


def test_hover_and_glow_have_safe_canvas_padding() -> None:
    max_glow_half_width = 8.0 / 2.0

    assert EmoteCatalogueCanvas.GLOW_PAD >= (
        EmoteCatalogueCanvas.HOVER_LIFT + max_glow_half_width
    )
    assert EmoteCatalogueCanvas.HOVER_LIFT <= 4.0


def test_developer_unlock_override_invalidates_card_cache() -> None:
    source = inspect.getsource(EmoteCatalogueCanvas.refresh)

    assert "previous_unlock_all" in source
    assert "self._unlock_all == previous_unlock_all" in source


def test_developer_unlock_override_reaches_catalogue_window() -> None:
    buddy = object.__new__(EmoteCatalogueMixin)
    buddy._preview_mode = False
    buddy._bond_state = BondState(level=1, xp=0)
    buddy._dev_unlock_all_emotes = True
    window = SimpleNamespace(refresh=Mock(), present=Mock())
    buddy._ensure_emote_catalogue_window = Mock(return_value=window)

    EmoteCatalogueMixin._show_emote_catalogue(buddy)

    window.refresh.assert_called_once_with(
        buddy._bond_state,
        unlock_all=True,
    )



def test_hover_preview_animates_all_real_emotes_but_not_placeholders() -> None:
    for emote in EMOTE_CATALOGUE:
        enabled = EmoteCatalogueCanvas._preview_animation_enabled(emote)
        if emote.available and emote.animation is not None:
            assert enabled is True, emote.id
        else:
            assert enabled is False, emote.id


def test_hover_preview_uses_authored_frame_timing_and_loops() -> None:
    schedule_source = inspect.getsource(
        EmoteCatalogueCanvas._schedule_hover_preview_tick
    )
    advance_source = inspect.getsource(
        EmoteCatalogueCanvas._advance_hover_preview
    )

    assert "frame.duration_ms or animation.frame_duration_ms" in schedule_source
    assert "% len(animation.frames)" in advance_source
    assert "self.queue_draw()" in advance_source


def test_hover_preview_does_not_rebuild_catalogue_surfaces() -> None:
    start_source = inspect.getsource(EmoteCatalogueCanvas._start_hover_preview)
    advance_source = inspect.getsource(
        EmoteCatalogueCanvas._advance_hover_preview
    )

    assert "_render_card_surfaces" not in start_source
    assert "_render_card_surfaces" not in advance_source


def test_catalogue_keeps_static_preview_cache_separate_from_card_chrome() -> None:
    render_source = inspect.getsource(
        EmoteCatalogueCanvas._render_card_surfaces
    )
    draw_source = inspect.getsource(EmoteCatalogueCanvas._draw)

    assert "self._preview_surfaces" in render_source
    assert "self._render_preview_surface(emote, scale)" in render_source
    assert "self._preview_surfaces" in draw_source
    assert "self._hover_preview_frame_index" in draw_source
