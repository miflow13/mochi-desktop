"""Bond-gated emote definitions shared by behavior and presentation."""

from __future__ import annotations

from dataclasses import dataclass

from mochi.care import BondState


@dataclass(frozen=True, slots=True)
class EmoteDefinition:
    id: str
    label: str
    animation: str | None
    required_bond_level: int | None
    available: bool = True
    rarity: str = "common"
    reveal_on_unlock: bool = False

    def is_unlocked(self, state: BondState, *, unlock_all: bool = False) -> bool:
        return bool(
            self.available
            and self.required_bond_level is not None
            and (unlock_all or state.level >= self.required_bond_level)
        )


EMOTE_CATALOGUE = (
    EmoteDefinition("heart", "Heart", "heart", 1, rarity="common"),
    EmoteDefinition("bounce", "Bounce", "bounce", 1, rarity="common"),
    EmoteDefinition("squish", "Squish", "squish", 1, rarity="uncommon"),
    EmoteDefinition("wave", "Wave", "wave", 1, rarity="common"),
    EmoteDefinition("coffee", "Coffee", "coffee", 1, rarity="common"),
    EmoteDefinition(
        "side-eye",
        "Side Eye",
        "side_eye",
        2,
        rarity="uncommon",
        reveal_on_unlock=True,
    ),
    EmoteDefinition("look", "Look Around", "look", 3, rarity="rare"),
    EmoteDefinition(
        "table-flip",
        "Table Flip",
        "table_flip",
        3,
        rarity="rare",
        reveal_on_unlock=True,
    ),
    EmoteDefinition(
        "vs-code",
        "VS Code",
        "vs_code",
        4,
        rarity="epic",
        reveal_on_unlock=True,
    ),
    EmoteDefinition("dance", "Dance", "dance", 5, rarity="epic"),
    EmoteDefinition(
        "mochi-exe",
        "Mochi.exe",
        "mochi_exe",
        6,
        rarity="legendary",
        reveal_on_unlock=True,
    ),
)
EMOTES_BY_ID = {emote.id: emote for emote in EMOTE_CATALOGUE}


def next_emote_unlock(state: BondState) -> EmoteDefinition | None:
    candidates = (
        emote
        for emote in EMOTE_CATALOGUE
        if emote.available
        and emote.required_bond_level is not None
        and emote.required_bond_level > state.level
    )
    return min(candidates, key=lambda emote: emote.required_bond_level, default=None)


def newly_unlocked_emotes(
    previous_level: int,
    new_level: int,
    *,
    reveal_only: bool = False,
) -> tuple[EmoteDefinition, ...]:
    if new_level <= previous_level:
        return ()
    return tuple(
        emote
        for emote in EMOTE_CATALOGUE
        if emote.available
        and emote.required_bond_level is not None
        and previous_level < emote.required_bond_level <= new_level
        and (not reveal_only or emote.reveal_on_unlock)
    )


def unlocked_emote_animation_names(
    state: BondState | None,
    *,
    unlock_all: bool = False,
) -> tuple[str, ...]:
    """Return every unlocked catalogue animation in catalogue order.

    Catalogue membership is the behavior contract: once a real emote is added
    to EMOTE_CATALOGUE and unlocked, it automatically becomes available to
    Mochi\'s autonomous emote pool. Scheduling/frequency stays outside this
    module so adding emotes increases variety without making Mochi noisier.
    """

    current = state or BondState()
    return tuple(
        emote.animation
        for emote in EMOTE_CATALOGUE
        if emote.animation is not None
        and emote.is_unlocked(current, unlock_all=unlock_all)
    )
