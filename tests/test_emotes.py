"""Bond-gated emote domain tests."""

from mochi.care import BondState
from mochi.emotes import (
    EMOTES_BY_ID,
    newly_unlocked_emotes,
    unlocked_idle_animation_names,
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


def test_idle_pool_tracks_bond_level() -> None:
    assert unlocked_idle_animation_names(BondState(level=1)) == ()
    assert unlocked_idle_animation_names(BondState(level=2)) == ("side_eye",)
    assert unlocked_idle_animation_names(BondState(level=3)) == (
        "side_eye",
        "table_flip",
    )
    assert unlocked_idle_animation_names(BondState(level=6)) == (
        "side_eye",
        "table_flip",
    )


def test_dev_override_unlocks_available_idle_emotes_only() -> None:
    assert unlocked_idle_animation_names(
        BondState(level=1),
        unlock_all=True,
    ) == ("side_eye", "table_flip")
    assert EMOTES_BY_ID["vs-code"].is_unlocked(
        BondState(level=1),
        unlock_all=True,
    )
    assert EMOTES_BY_ID["mochi-exe"].is_unlocked(
        BondState(level=1),
        unlock_all=True,
    )
