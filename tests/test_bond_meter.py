"""Regression coverage for Mochi's bond progress integration."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from mochi.animation import AnimationPlayer
from mochi.bond_orbs import XpOrbField
from mochi.care import (
    BOND_FEED_FIRST_XP,
    BOND_FEED_REWARD_WINDOW_SECONDS,
    BOND_FEED_SECOND_XP,
    BondState,
)
from mochi.config import ConfigStore
from mochi.emotes import EMOTES_BY_ID
from mochi.focus import FocusPhase, FocusPlan, FocusSession
from mochi.presence.bond_meter import (
    BOND_DEV_VISUAL_ORB_LIMIT,
    BOND_DEV_SWARM_XP,
    BOND_FEED_VISUAL_ORB_LIMIT,
    BOND_PERSIST_INTERVAL_XP,
    BondMeterMixin,
)
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, PresentationState, StateMachine


class _LayoutBase:
    def __init__(self) -> None:
        self.rows = ["status", "sleep", "close"]

    def _build_context_menu(self):
        return "menu"

    def _register_context_menu_row(
        self,
        row_id,
        _widget,
        *,
        before=None,
        after=None,
        animated=True,
    ) -> None:
        if before is not None:
            self.rows.insert(self.rows.index(before), row_id)
        elif after is not None:
            self.rows.insert(self.rows.index(after) + 1, row_id)
        else:
            self.rows.append(row_id)


class _FeedMenuMixin:
    def _build_context_menu(self):
        menu = super()._build_context_menu()
        self._register_context_menu_row("feed", "feed-row", before="sleep")
        return menu


class _BondMenuHarness(BondMeterMixin, _FeedMenuMixin, _LayoutBase):
    def _build_bond_meter_row(self):
        return "bond-row"


class _CompletionBase:
    def _on_feed_animation_completed(self) -> None:
        self.completion_chain_calls += 1


class _BondCompletionHarness(BondMeterMixin, _CompletionBase):
    pass


class _ShutdownBase:
    def shutdown_presence(self) -> None:
        self.shutdown_chain_calls += 1


class _BondShutdownHarness(BondMeterMixin, _ShutdownBase):
    pass


class _TickBase:
    def _tick(self) -> bool:
        self.behavior_tick_calls += 1
        return True


class _BondTickHarness(BondMeterMixin, _TickBase):
    pass


def _runtime_harness(state: BondState | None = None):
    harness = object.__new__(BondMeterMixin)
    harness._bond_state = state or BondState()
    harness._bond_orbs = Mock()
    harness._bond_meter = Mock()
    harness._bond_level_label = Mock()
    harness._bond_dev_status_label = None
    harness._dev_unlock_all_emotes = False
    harness._dev_unlock_all_label = None
    harness._pending_emote_unlocks = []
    harness._pending_emote_demo = None
    harness._bond_emote_demo_source_id = None
    harness._pending_level_up_card = None
    harness._bond_presentation_animation = None
    harness._bond_presentation_stage = None
    harness._bond_presentation_player = AnimationPlayer(
        on_finished=lambda animation: BondMeterMixin._on_bond_presentation_animation_finished(
            harness,
            animation,
        )
    )
    harness._bond_progress_overlay = Mock()
    harness._bond_progress_overlay.active = True
    harness._bond_progress_overlay.level_up_active = False
    harness._bond_progress_overlay.emote_unlock_active = False
    harness._bond_progress_overlay.presentation_active = False
    harness._bond_typing_source_id = None
    harness._bond_unsaved_xp = 0
    harness._bond_feed_last_completed_at = None
    harness._bond_feed_count_in_window = 0
    harness._focus_session = None
    harness._config = Mock()
    harness._logger = Mock()
    harness._sound = Mock()
    harness.state = StateMachine()
    harness.state.current = MochiState.TYPING
    harness._dismiss_presence_bubble = Mock()
    harness.queue_draw = Mock()
    harness._on_bond_level_up = Mock()
    return harness


def test_bond_row_lands_between_status_and_feed() -> None:
    harness = _BondMenuHarness()

    assert harness._build_context_menu() == "menu"
    assert harness.rows == ["status", "bond", "feed", "sleep", "close"]


def test_restore_loads_persisted_relationship_state() -> None:
    harness = _runtime_harness()
    harness.state.current = MochiState.IDLE
    harness._config.load_bond_state.return_value = BondState(level=3, xp=210)

    harness._restore_bond_state()

    assert harness._bond_state == BondState(level=3, xp=210)
    harness._bond_level_label.set_label.assert_called_once_with("Bond Lv. 3")
    harness._bond_meter.set_state.assert_called_once_with(BondState(level=3, xp=210))
    harness._bond_progress_overlay.update.assert_called_once_with(
        BondState(level=3, xp=210)
    )


def test_first_completed_feed_awards_30_xp_persists_and_shows_bar() -> None:
    harness = object.__new__(_BondCompletionHarness)
    runtime = _runtime_harness(BondState(level=1, xp=10))
    harness.__dict__.update(runtime.__dict__)
    harness.completion_chain_calls = 0
    harness.state.current = MochiState.EATING

    with patch("mochi.presence.bond_meter.time.monotonic", return_value=100.0):
        harness._on_feed_animation_completed()

    assert harness._bond_state == BondState(level=1, xp=10 + BOND_FEED_FIRST_XP)
    harness._bond_orbs.queue_xp_bounded.assert_called_once_with(
        BOND_FEED_FIRST_XP,
        max_outstanding=BOND_FEED_VISUAL_ORB_LIMIT,
    )
    harness._bond_orbs.show_gain_marker.assert_called_once_with(BOND_FEED_FIRST_XP)
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
    harness._bond_progress_overlay.show_activity.assert_called_once_with(
        BondState(level=1, xp=10),
        "sharing a snack",
    )
    harness._bond_progress_overlay.notify_xp_gain.assert_called_once_with(
        harness._bond_state,
        BOND_FEED_FIRST_XP,
    )
    harness._bond_progress_overlay.finish_activity.assert_called_once()
    assert harness.completion_chain_calls == 1


def test_feed_reward_window_is_30_then_10_then_zero_until_inactive_reset() -> None:
    harness = _runtime_harness()

    assert BondMeterMixin._next_feed_bond_reward(harness, now=100.0) == 30
    assert BondMeterMixin._next_feed_bond_reward(harness, now=200.0) == 10
    assert BondMeterMixin._next_feed_bond_reward(harness, now=300.0) == 0

    reset_at = 300.0 + BOND_FEED_REWARD_WINDOW_SECONDS
    assert BondMeterMixin._next_feed_bond_reward(harness, now=reset_at) == 30


def test_zero_xp_feed_keeps_completion_chain_without_showing_xp_feedback() -> None:
    harness = object.__new__(_BondCompletionHarness)
    runtime = _runtime_harness(BondState(level=1, xp=75))
    harness.__dict__.update(runtime.__dict__)
    harness.completion_chain_calls = 0
    harness.state.current = MochiState.EATING
    harness._bond_feed_last_completed_at = 100.0
    harness._bond_feed_count_in_window = 2

    with patch("mochi.presence.bond_meter.time.monotonic", return_value=200.0):
        harness._on_feed_animation_completed()

    assert harness._bond_state == BondState(level=1, xp=75)
    harness._bond_orbs.queue_xp_bounded.assert_not_called()
    harness._bond_progress_overlay.show_activity.assert_not_called()
    harness._bond_progress_overlay.notify_xp_gain.assert_not_called()
    harness._bond_progress_overlay.finish_activity.assert_not_called()
    harness._config.save_bond_state.assert_not_called()
    assert harness.completion_chain_calls == 1


def test_typing_tick_adds_one_xp_without_writing_every_second() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))

    assert harness._bond_typing_tick()

    assert harness._bond_state == BondState(level=1, xp=101)
    assert harness._bond_unsaved_xp == 1
    harness._bond_orbs.queue_xp.assert_called_once_with(1)
    harness._bond_orbs.show_gain_marker.assert_called_once_with(1)
    harness._bond_progress_overlay.notify_xp_gain.assert_not_called()
    harness._config.save_bond_state.assert_not_called()


def test_typing_progress_batches_disk_writes() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))
    harness._bond_unsaved_xp = BOND_PERSIST_INTERVAL_XP - 1

    harness._bond_typing_tick()

    assert harness._bond_state == BondState(level=1, xp=101)
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
    assert harness._bond_unsaved_xp == 0


def test_typing_activity_starts_one_timer_without_showing_bond_hud() -> None:
    harness = _runtime_harness()

    with patch(
        "mochi.presence.bond_meter.GLib.timeout_add_seconds",
        return_value=44,
    ) as timeout:
        harness._start_bond_typing_session()
        harness._start_bond_typing_session()

    timeout.assert_called_once()
    assert harness._bond_typing_source_id == 44
    assert harness._bond_progress_overlay.dismiss.call_count == 2
    harness._bond_progress_overlay.show_activity.assert_not_called()


def test_typing_stop_flushes_pending_xp_and_holds_progress_briefly() -> None:
    harness = _runtime_harness(BondState(level=1, xp=123))
    harness._bond_typing_source_id = 77
    harness._bond_unsaved_xp = 3

    with patch("mochi.presence.bond_meter.GLib.source_remove") as remove:
        harness._finish_bond_typing_session()

    remove.assert_called_once_with(77)
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
    harness._bond_progress_overlay.finish_activity.assert_not_called()
    assert harness._bond_typing_source_id is None
    assert harness._bond_unsaved_xp == 0


def test_typing_tick_stops_if_mochi_is_no_longer_typing() -> None:
    harness = _runtime_harness(BondState(level=1, xp=200))
    harness.state.current = MochiState.HEART

    result = harness._bond_typing_tick()

    assert result == 0
    assert harness._bond_state == BondState(level=1, xp=200)
    harness._bond_progress_overlay.finish_activity.assert_not_called()


def test_focus_bond_hint_tracks_real_xp_earning_not_current_visual_state() -> None:
    harness = _runtime_harness(BondState(level=1, xp=120))
    session = FocusSession(FocusPlan(focus_minutes=5, break_minutes=1, rounds=1))
    harness._focus_session = session

    # The context menu can temporarily put Mochi in the thinking visual while
    # the focus clock still earns XP. The bar should remain visible.
    harness.state.current = MochiState.IDLE_EMOTE
    assert harness._focus_bond_hint_active() is True

    session.set_paused(True)
    assert harness._focus_bond_hint_active() is False

    session.set_paused(False)
    session.phase = FocusPhase.BREAK
    assert harness._focus_bond_hint_active() is False


def test_focus_xp_award_keeps_orbs_and_suppresses_full_bond_hud() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))
    harness.state.current = MochiState.COMPUTER
    harness._focus_session = FocusSession(
        FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)
    )

    BondMeterMixin._award_bond(harness, 1, persist=False)

    assert harness._bond_state == BondState(level=1, xp=101)
    harness._bond_orbs.queue_xp.assert_called_once_with(1)
    harness._bond_orbs.show_gain_marker.assert_not_called()
    harness._bond_progress_overlay.notify_xp_gain.assert_not_called()


def test_focus_compact_hint_suppresses_full_activity_card() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))
    harness.state.current = MochiState.EATING
    harness._focus_session = FocusSession(
        FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)
    )

    BondMeterMixin._show_bond_progress(harness, "sharing a snack")

    harness._bond_progress_overlay.show_activity.assert_not_called()


def test_focus_bond_hint_geometry_sits_above_visible_mochi_bounds() -> None:
    harness = _runtime_harness(BondState(level=1, xp=120))
    harness.state.current = MochiState.COMPUTER
    harness._focus_session = FocusSession(FocusPlan())
    harness.player = SimpleNamespace(frame=object())
    harness.atlas = SimpleNamespace(
        visible_bounds=lambda _frame, _width, _height: (30.0, 42.0, 68.0, 72.0)
    )

    _x, y, _bar_width, bar_height = BondMeterMixin._focus_bond_bar_geometry(
        harness,
        128,
        128,
    )

    assert y + bar_height <= 42.0 - 7.0


def test_focus_bond_hint_draws_only_track_and_progress_fill() -> None:
    harness = _runtime_harness(BondState(level=1, xp=120))
    harness.state.current = MochiState.COMPUTER
    harness._focus_session = FocusSession(
        FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)
    )
    harness.player = SimpleNamespace(frame=None)
    harness.atlas = None
    context = Mock()
    context.text_extents.return_value = SimpleNamespace(
        width=38.0,
        x_bearing=0.0,
    )

    BondMeterMixin._draw_focus_bond_hint(harness, context, 128, 128)

    context.show_text.assert_called_once_with("Bond XP")
    assert context.rectangle.call_count == 2
    track = context.rectangle.call_args_list[0].args
    fill = context.rectangle.call_args_list[1].args
    assert track[0:2] == fill[0:2]
    assert track[3] == fill[3]
    assert track[3] >= 5.0
    assert fill[2] == track[2] * harness._bond_state.progress_fraction
    assert context.fill.call_count == 2


def test_focus_tick_dismisses_stale_nonpresentation_bond_overlay() -> None:
    harness = object.__new__(_BondTickHarness)
    runtime = _runtime_harness(BondState(level=1, xp=100))
    harness.__dict__.update(runtime.__dict__)
    harness.behavior_tick_calls = 0
    harness.state.current = MochiState.COMPUTER
    harness._focus_session = FocusSession(
        FocusPlan(focus_minutes=5, break_minutes=1, rounds=1)
    )
    harness._bond_orbs.has_activity = False
    harness._bond_presentation_player.stop()

    assert harness._tick() is True

    harness._bond_progress_overlay.dismiss.assert_called_once_with()


def test_level_up_plays_default_animation_before_card_even_while_typing() -> None:
    harness = _runtime_harness(BondState(level=2, xp=10))

    BondMeterMixin._on_bond_level_up(harness, 1, 2)

    assert harness.state.current is MochiState.TYPING
    assert harness.state.presentation is PresentationState.LEVEL_UP
    assert harness.state.dialogue_allowed is False
    harness._dismiss_presence_bubble.assert_called_once_with(user_initiated=False)
    harness._bond_orbs.trigger_level_up.assert_called_once_with()
    harness._sound.play_level_up.assert_called_once_with()
    assert harness._bond_presentation_animation == "level_up_default"
    assert harness._bond_presentation_stage == "level_up"
    assert harness._bond_presentation_player.animation is not None
    assert harness._bond_presentation_player.animation.name == "level_up_default"
    harness._bond_progress_overlay.show_level_up.assert_not_called()

    BondMeterMixin._on_bond_presentation_animation_finished(
        harness,
        harness._bond_presentation_player.animation,
    )

    harness._bond_progress_overlay.show_level_up.assert_called_once_with(
        harness._bond_state,
        previous_level=1,
    )
    assert harness.state.current is MochiState.TYPING


def test_level_up_animation_is_visual_only_outside_typing() -> None:
    harness = _runtime_harness(BondState(level=2, xp=10))
    harness.state.current = MochiState.EATING

    BondMeterMixin._on_bond_level_up(harness, 1, 2)

    assert harness.state.current is MochiState.EATING
    assert harness._bond_presentation_animation == "level_up_default"
    harness._bond_progress_overlay.show_level_up.assert_not_called()


def test_dev_award_one_uses_real_bond_path() -> None:
    harness = _runtime_harness(BondState(level=1, xp=20))
    harness._award_bond = Mock()

    BondMeterMixin._test_bond_award_one(harness)

    harness._award_bond.assert_called_once_with(
        1,
        persist=False,
        visual_orb_limit=BOND_DEV_VISUAL_ORB_LIMIT,
    )


def test_rapid_dev_awards_bound_visuals_and_flush_pending_xp_on_shutdown(tmp_path) -> None:
    harness = object.__new__(_BondShutdownHarness)
    harness.__dict__.update(_runtime_harness().__dict__)
    harness.shutdown_chain_calls = 0
    harness.state.current = MochiState.IDLE
    harness._bond_orbs = XpOrbField(rng=random.Random(2))
    harness._config = ConfigStore(tmp_path / "config.json")
    harness._config.save_bond_state = Mock(wraps=harness._config.save_bond_state)

    for _ in range(100):
        harness._test_bond_award_one()

    assert harness._bond_state == BondState(level=1, xp=100)
    assert harness._bond_orbs.outstanding_orb_count == BOND_DEV_VISUAL_ORB_LIMIT
    assert harness._bond_orbs.marker_count <= 3
    assert (
        harness._config.save_bond_state.call_count
        == 100 // BOND_PERSIST_INTERVAL_XP
    )
    assert harness._config.load_bond_state() == BondState(level=1, xp=90)
    assert harness._bond_unsaved_xp == 10
    assert harness._bond_progress_overlay.notify_xp_gain.call_count == 100

    harness.shutdown_presence()

    assert harness._config.load_bond_state() == BondState(level=1, xp=100)
    assert (
        harness._config.save_bond_state.call_count
        == 1 + 100 // BOND_PERSIST_INTERVAL_XP
    )
    assert harness._bond_unsaved_xp == 0
    assert harness.shutdown_chain_calls == 1


def test_dev_award_persists_level_crossing_before_shutdown(tmp_path) -> None:
    near_level = BondState(level=2, xp=BondState(level=2).xp_required - 1)
    harness = _runtime_harness(near_level)
    harness._config = ConfigStore(tmp_path / "config.json")
    harness._on_bond_level_up = lambda previous, new: BondMeterMixin._on_bond_level_up(
        harness, previous, new
    )

    harness._test_bond_award_one()

    assert harness._bond_state == BondState(level=3, xp=0)
    assert harness._config.load_bond_state() == harness._bond_state
    assert harness._bond_unsaved_xp == 0
    assert harness.state.presentation is PresentationState.LEVEL_UP
    harness._sound.play_level_up.assert_called_once_with()
    harness._bond_orbs.trigger_level_up.assert_called_once_with()
    assert harness._pending_emote_unlocks


def test_dev_swarm_is_visual_only() -> None:
    harness = _runtime_harness(BondState(level=3, xp=210))
    harness.queue_draw = Mock()
    original = harness._bond_state

    BondMeterMixin._test_bond_swarm(harness)

    assert harness._bond_state == original
    harness._bond_orbs.queue_xp_bounded.assert_called_once_with(
        BOND_DEV_SWARM_XP,
        max_outstanding=BOND_DEV_SWARM_XP,
    )
    harness._bond_orbs.show_gain_marker.assert_called_once_with(BOND_DEV_SWARM_XP)
    harness._config.save_bond_state.assert_not_called()
    harness.queue_draw.assert_called_once_with()


def test_dev_level_up_card_previews_next_level_without_mutating_state() -> None:
    harness = _runtime_harness(BondState(level=4, xp=120))
    harness.queue_draw = Mock()
    original = harness._bond_state

    BondMeterMixin._test_bond_level_up_card(harness)

    assert harness._bond_state == original
    assert harness.state.presentation is PresentationState.LEVEL_UP
    harness._dismiss_presence_bubble.assert_called_once_with(user_initiated=False)
    harness._bond_orbs.trigger_level_up.assert_called_once_with()
    assert harness._bond_presentation_animation == "level_up_default"
    harness._bond_progress_overlay.show_level_up.assert_not_called()
    harness._sound.play_level_up.assert_not_called()
    harness._config.save_bond_state.assert_not_called()


def test_dev_real_level_up_crosses_boundary_with_one_xp() -> None:
    harness = _runtime_harness(BondState(level=2, xp=33))
    harness._set_bond_state_for_ui = Mock(
        side_effect=lambda state: setattr(harness, "_bond_state", state)
    )
    harness._persist_bond_state = Mock()
    harness._award_bond = Mock()

    BondMeterMixin._test_bond_real_level_up(harness)

    near = BondState(level=2, xp=BondState(level=2).xp_required - 1)
    harness._set_bond_state_for_ui.assert_called_once_with(near)
    harness._persist_bond_state.assert_called_once_with()
    harness._award_bond.assert_called_once_with(1, persist=True)


def test_dev_reset_restores_level_one_and_dismisses_overlay() -> None:
    harness = _runtime_harness(BondState(level=7, xp=222))
    harness._set_bond_state_for_ui = Mock(
        side_effect=lambda state: setattr(harness, "_bond_state", state)
    )
    harness._persist_bond_state = Mock()

    BondMeterMixin._test_bond_reset(harness)

    harness._set_bond_state_for_ui.assert_called_once_with(BondState())
    harness._persist_bond_state.assert_called_once_with()
    harness._bond_progress_overlay.dismiss.assert_called_once_with()


def test_typing_refresh_does_not_dismiss_active_level_up_card() -> None:
    harness = _runtime_harness(BondState(level=2, xp=0))
    harness._bond_progress_overlay.level_up_active = True
    harness._bond_progress_overlay.presentation_active = True

    with patch(
        "mochi.presence.bond_meter.GLib.timeout_add_seconds",
        return_value=55,
    ):
        BondMeterMixin._start_bond_typing_session(harness)

    harness._bond_progress_overlay.dismiss.assert_not_called()
    assert harness._bond_typing_source_id == 55


def test_unlock_card_then_new_emote_demo_starts_after_tiny_anticipation() -> None:
    harness = _runtime_harness(BondState(level=2, xp=0))
    harness.state.transition_presentation(PresentationState.LEVEL_UP)
    harness._pending_emote_unlocks = [EMOTES_BY_ID["side-eye"]]

    with patch(
        "mochi.presence.bond_meter.GLib.timeout_add",
        return_value=91,
    ) as timeout:
        BondMeterMixin._on_bond_level_up_finished(harness)

    assert harness.state.presentation is PresentationState.EMOTE_UNLOCK
    harness._bond_progress_overlay.show_emote_unlock.assert_called_once_with(
        EMOTES_BY_ID["side-eye"]
    )
    assert harness._pending_emote_demo is EMOTES_BY_ID["side-eye"]
    assert harness._bond_presentation_animation is None
    timeout.assert_called_once_with(
        150,
        harness._start_pending_emote_demo,
    )

    result = BondMeterMixin._start_pending_emote_demo(harness)

    assert result == 0
    assert harness._bond_presentation_animation == "side_eye"
    assert harness._bond_presentation_stage == "emote_demo"
    assert harness._bond_presentation_player.animation is not None
    assert harness._bond_presentation_player.animation.name == "side_eye"
    assert harness._bond_presentation_player.animation.looping is False

    finished = harness._bond_presentation_player.animation
    BondMeterMixin._on_bond_presentation_animation_finished(harness, finished)

    assert harness.state.presentation is PresentationState.EMOTE_UNLOCK
    assert harness._pending_emote_demo is EMOTES_BY_ID["side-eye"]

    BondMeterMixin._on_bond_level_up_finished(harness)

    assert harness._pending_emote_demo is None
    assert harness.state.presentation is PresentationState.NORMAL
    assert harness.state.dialogue_allowed is True


def test_multiple_unlock_cards_stay_ordered_and_demos_do_not_overlap() -> None:
    harness = _runtime_harness(BondState(level=3, xp=0))
    harness.state.transition_presentation(PresentationState.LEVEL_UP)
    side_eye = EMOTES_BY_ID["side-eye"]
    table_flip = EMOTES_BY_ID["table-flip"]
    harness._pending_emote_unlocks = [side_eye, table_flip]

    with patch(
        "mochi.presence.bond_meter.GLib.timeout_add",
        side_effect=(91, 92),
    ) as timeout:
        BondMeterMixin._on_bond_level_up_finished(harness)

        assert harness._pending_emote_demo is side_eye
        assert harness._pending_emote_unlocks == [table_flip]
        BondMeterMixin._start_pending_emote_demo(harness)
        assert harness._bond_presentation_animation == "side_eye"

        BondMeterMixin._on_bond_level_up_finished(harness)

    assert harness._pending_emote_demo is table_flip
    assert harness._pending_emote_unlocks == []
    assert harness._bond_presentation_animation is None
    assert harness._bond_progress_overlay.show_emote_unlock.call_args_list == [
        call(side_eye),
        call(table_flip),
    ]
    assert timeout.call_args_list == [
        call(150, harness._start_pending_emote_demo),
        call(150, harness._start_pending_emote_demo),
    ]

    BondMeterMixin._start_pending_emote_demo(harness)
    assert harness._bond_presentation_animation == "table_flip"
    assert harness._bond_presentation_stage == "emote_demo"

    finished = harness._bond_presentation_player.animation
    assert finished is not None
    BondMeterMixin._on_bond_presentation_animation_finished(harness, finished)
    BondMeterMixin._on_bond_level_up_finished(harness)

    assert harness._pending_emote_demo is None
    assert harness.state.presentation is PresentationState.NORMAL


def test_level_up_finish_releases_dialogue_priority() -> None:
    harness = _runtime_harness(BondState(level=2, xp=0))
    harness.state.transition_presentation(PresentationState.LEVEL_UP)

    BondMeterMixin._on_bond_level_up_finished(harness)

    assert harness.state.presentation is PresentationState.NORMAL
    assert harness.state.dialogue_allowed is True


def test_real_xp_threshold_runs_complete_level_up_presentation_regression() -> None:
    almost_level_two = BondState(
        level=1,
        xp=BondState(level=1).xp_required - 1,
    )
    harness = _runtime_harness(almost_level_two)
    harness._on_bond_level_up = lambda previous, new: BondMeterMixin._on_bond_level_up(
        harness,
        previous,
        new,
    )

    advance = BondMeterMixin._award_bond(harness, 1, persist=True)

    assert advance.levelled_up is True
    assert harness._bond_state == BondState(level=2, xp=0)
    assert harness.state.presentation is PresentationState.LEVEL_UP
    assert harness.state.dialogue_allowed is False
    harness._config.save_bond_state.assert_called_once_with(BondState(level=2, xp=0))
    harness._bond_orbs.queue_xp.assert_called_once_with(1)
    harness._bond_orbs.show_gain_marker.assert_called_once_with(1)
    harness._bond_orbs.trigger_level_up.assert_called_once_with()
    harness._dismiss_presence_bubble.assert_called_once_with(user_initiated=False)
    harness._sound.play_level_up.assert_called_once_with()
    assert harness._bond_presentation_animation == "level_up_default"
    harness._bond_progress_overlay.show_level_up.assert_not_called()


def test_same_level_updates_do_not_replay_level_up_or_sound() -> None:
    almost_level_two = BondState(
        level=1,
        xp=BondState(level=1).xp_required - 1,
    )
    harness = _runtime_harness(almost_level_two)
    harness._on_bond_level_up = lambda previous, new: BondMeterMixin._on_bond_level_up(
        harness,
        previous,
        new,
    )

    first = BondMeterMixin._award_bond(harness, 1, persist=True)
    second = BondMeterMixin._award_bond(harness, 1, persist=True)

    assert first.levelled_up is True
    assert second.levelled_up is False
    harness._sound.play_level_up.assert_called_once_with()
    harness._bond_orbs.trigger_level_up.assert_called_once_with()


def test_restore_does_not_replay_completed_level_up() -> None:
    harness = _runtime_harness()
    restored = BondState(level=3, xp=40)
    harness._config.load_bond_state.return_value = restored

    harness._restore_bond_state()

    assert harness._bond_state == restored
    harness._sound.play_level_up.assert_not_called()
    harness._bond_orbs.trigger_level_up.assert_not_called()
    assert harness._bond_presentation_player.animation is None
    assert harness.state.presentation is PresentationState.NORMAL


def test_shutdown_cancels_unlock_work_before_destroy_callback_can_advance() -> None:
    harness = object.__new__(_BondShutdownHarness)
    runtime = _runtime_harness(BondState(level=3, xp=0))
    harness.__dict__.update(runtime.__dict__)
    harness.shutdown_chain_calls = 0
    harness.state.transition_presentation(PresentationState.EMOTE_UNLOCK)
    harness._pending_emote_unlocks = [EMOTES_BY_ID["table-flip"]]
    harness._pending_emote_demo = EMOTES_BY_ID["side-eye"]
    harness._bond_emote_demo_source_id = 73
    overlay = harness._bond_progress_overlay
    overlay.destroy.side_effect = harness._on_bond_level_up_finished

    with patch("mochi.presence.bond_meter.GLib.source_remove") as remove:
        harness.shutdown_presence()

    remove.assert_called_once_with(73)
    overlay.destroy.assert_called_once_with()
    overlay.show_emote_unlock.assert_not_called()
    assert harness._bond_progress_overlay is None
    assert harness._pending_emote_unlocks == []
    assert harness._pending_emote_demo is None
    assert harness.state.presentation is PresentationState.NORMAL
    assert harness.shutdown_chain_calls == 1


def test_idle_bond_tick_does_not_request_an_extra_redraw() -> None:
    harness = object.__new__(_BondTickHarness)
    runtime = _runtime_harness()
    harness.__dict__.update(runtime.__dict__)
    harness.behavior_tick_calls = 0
    harness._bond_orbs.has_activity = False
    harness._bond_presentation_player.stop()

    assert harness._tick() is True

    assert harness.behavior_tick_calls == 1
    harness.queue_draw.assert_not_called()
    harness._bond_orbs.advance.assert_not_called()


def test_presentation_and_orb_changes_share_one_redraw_per_tick() -> None:
    harness = object.__new__(_BondTickHarness)
    runtime = _runtime_harness()
    harness.__dict__.update(runtime.__dict__)
    harness.behavior_tick_calls = 0
    harness._bond_orbs.has_activity = True
    harness._bond_orbs.advance.return_value = True
    harness._bond_presentation_player.play(ANIMATIONS["level_up_default"])
    harness._frame_elapsed_ms = 120

    assert harness._tick() is True

    assert harness.behavior_tick_calls == 1
    harness.queue_draw.assert_called_once_with()


def test_feed_uses_visual_backlog_cap_without_reducing_real_xp() -> None:
    harness = _runtime_harness(BondState(level=1, xp=100))
    harness.state.current = MochiState.EATING

    advance = BondMeterMixin._award_bond(
        harness,
        BOND_FEED_FIRST_XP,
        persist=True,
        visual_orb_limit=BOND_FEED_VISUAL_ORB_LIMIT,
    )

    assert advance.xp_awarded == BOND_FEED_FIRST_XP
    assert harness._bond_state == BondState(level=1, xp=100 + BOND_FEED_FIRST_XP)
    harness._bond_orbs.queue_xp_bounded.assert_called_once_with(
        BOND_FEED_FIRST_XP,
        max_outstanding=BOND_FEED_VISUAL_ORB_LIMIT,
    )
    harness._config.save_bond_state.assert_called_once_with(harness._bond_state)
