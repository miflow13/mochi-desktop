"""Bond-gated emote domain tests."""

import mochi.emotes as emotes_module
from mochi.care import BondState
from mochi.emotes import (
    EMOTES_BY_ID,
    EmoteDefinition,
    newly_unlocked_emotes,
    unlocked_emote_animation_names,
)


def test_bond_emotes_unlock_at_requested_levels() -> None:
    assert EMOTES_BY_ID["wave"].is_unlocked(BondState(level=1))
    assert not EMOTES_BY_ID["side-eye"].is_unlocked(BondState(level=1))
    assert EMOTES_BY_ID["side-eye"].is_unlocked(BondState(level=2))
    assert not EMOTES_BY_ID["table-flip"].is_unlocked(BondState(level=2))
    assert EMOTES_BY_ID["table-flip"].is_unlocked(BondState(level=3))
    assert not EMOTES_BY_ID["vs-code"].is_unlocked(BondState(level=3))
    assert EMOTES_BY_ID["vs-code"].is_unlocked(BondState(level=4))
    assert not EMOTES_BY_ID["mochi-exe"].is_unlocked(BondState(level=5))
    assert EMOTES_BY_ID["mochi-exe"].is_unlocked(BondState(level=6))


def test_reveal_queue_contains_authored_level_unlocks() -> None:
    assert tuple(
        emote.id for emote in newly_unlocked_emotes(1, 2, reveal_only=True)
    ) == ("side-eye",)
    assert tuple(
        emote.id for emote in newly_unlocked_emotes(2, 3, reveal_only=True)
    ) == ("table-flip",)
    assert tuple(
        emote.id for emote in newly_unlocked_emotes(3, 4, reveal_only=True)
    ) == ("vs-code",)
    assert tuple(
        emote.id for emote in newly_unlocked_emotes(5, 6, reveal_only=True)
    ) == ("mochi-exe",)


def test_autonomous_pool_tracks_every_unlocked_catalogue_animation() -> None:
    assert unlocked_emote_animation_names(BondState(level=1)) == (
        "heart",
        "bounce",
        "squish",
        "wave",
    )
    assert unlocked_emote_animation_names(BondState(level=3)) == (
        "heart",
        "bounce",
        "squish",
        "wave",
        "side_eye",
        "look",
        "table_flip",
    )
    assert unlocked_emote_animation_names(BondState(level=6)) == (
        "heart",
        "bounce",
        "squish",
        "wave",
        "side_eye",
        "look",
        "table_flip",
        "vs_code",
        "dance",
        "mochi_exe",
    )


def test_dev_override_exposes_every_available_catalogue_animation() -> None:
    assert unlocked_emote_animation_names(
        BondState(level=1),
        unlock_all=True,
    ) == tuple(
        emote.animation
        for emote in emotes_module.EMOTE_CATALOGUE
        if emote.animation is not None
    )


def test_adding_real_catalogue_entry_automatically_adds_it_to_pool(monkeypatch) -> None:
    extra = EmoteDefinition(
        "test-emote",
        "Test Emote",
        "test_animation",
        1,
    )
    monkeypatch.setattr(
        emotes_module,
        "EMOTE_CATALOGUE",
        (*emotes_module.EMOTE_CATALOGUE, extra),
    )

    assert unlocked_emote_animation_names(BondState(level=1))[-1] == "test_animation"
