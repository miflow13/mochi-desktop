"""Integration regressions for bond-driven idle emote unlocks."""

from __future__ import annotations

import inspect

from mochi.buddy import Buddy
from mochi.presence.bond_meter import BondMeterMixin
from mochi.state import PresentationState


def test_presentation_state_has_distinct_emote_unlock_mode() -> None:
    assert PresentationState.EMOTE_UNLOCK is not PresentationState.LEVEL_UP


def test_idle_selector_uses_bond_gated_emote_pool() -> None:
    selector_source = inspect.getsource(Buddy._choose_idle_action)
    pool_source = inspect.getsource(BondMeterMixin._available_idle_emote_animations)

    assert "_available_idle_emote_animations" in selector_source
    assert "MochiState.IDLE_EMOTE" in selector_source
    assert "unlocked_idle_animation_names" in pool_source
    assert "_dev_unlock_all_emotes" in pool_source


def test_bond_level_up_queues_revealable_emotes() -> None:
    source = inspect.getsource(BondMeterMixin._on_bond_level_up)

    assert "newly_unlocked_emotes" in source
    assert "reveal_only=True" in source
    assert "_pending_emote_unlocks.extend" in source


def test_level_up_completion_chains_into_unlock_card() -> None:
    source = inspect.getsource(BondMeterMixin._on_bond_level_up_finished)

    assert "PresentationState.EMOTE_UNLOCK" in source
    assert "overlay.show_emote_unlock(emote)" in source


def test_developer_menu_has_session_only_unlock_all_action() -> None:
    menu_source = inspect.getsource(BondMeterMixin._build_developer_menu)
    callback_source = inspect.getsource(BondMeterMixin._test_unlock_all_emotes)

    assert '"Unlock all emotes"' in menu_source
    assert "Session-only QA override" in menu_source
    assert "self._dev_unlock_all_emotes = not self._dev_unlock_all_emotes" in callback_source
    assert "_persist_bond_state" not in callback_source
