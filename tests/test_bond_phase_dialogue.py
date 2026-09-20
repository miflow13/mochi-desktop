"""Bond-phase classification and non-regressive relationship dialogue tests."""

from __future__ import annotations

import random

import pytest

from mochi.care import BondPhase, BondState, bond_phase_for_level
from mochi.presence.phrases import BOND_DIALOGUE, PHRASES, PhraseBank, bond_dialogue_lines


@pytest.mark.parametrize(
    ("level", "phase"),
    (
        (1, BondPhase.NEW),
        (2, BondPhase.NEW),
        (3, BondPhase.FAMILIAR),
        (4, BondPhase.FAMILIAR),
        (5, BondPhase.COMFORTABLE),
        (6, BondPhase.COMFORTABLE),
        (7, BondPhase.COMFORTABLE),
        (8, BondPhase.CLOSE),
        (9, BondPhase.CLOSE),
        (10, BondPhase.CLOSE),
        (11, BondPhase.DEEP_BOND),
        (99, BondPhase.DEEP_BOND),
    ),
)
def test_bond_phase_ranges(level: int, phase: BondPhase) -> None:
    assert bond_phase_for_level(level) is phase


@pytest.mark.parametrize("level", (0, -1, "invalid", None))
def test_invalid_or_low_levels_use_new_phase(level: object) -> None:
    assert bond_phase_for_level(level) is BondPhase.NEW


def test_level_one_cannot_receive_level_two_relationship_lines() -> None:
    level_one = bond_dialogue_lines(BondState(level=1))
    level_two_only = {
        line.text
        for line in BOND_DIALOGUE[BondPhase.NEW]
        if line.required_level == 2
    }

    assert level_one
    assert level_two_only.isdisjoint(level_one)


def test_level_two_accumulates_new_phase_lines() -> None:
    lines = set(bond_dialogue_lines(BondState(level=2)))
    level_one = {
        line.text
        for line in BOND_DIALOGUE[BondPhase.NEW]
        if line.required_level == 1
    }
    level_two = {
        line.text
        for line in BOND_DIALOGUE[BondPhase.NEW]
        if line.required_level == 2
    }

    assert level_one <= lines
    assert level_two <= lines


def test_level_three_switches_to_familiar_without_new_relationship_lines() -> None:
    lines = set(bond_dialogue_lines(BondState(level=3)))
    new_lines = {line.text for line in BOND_DIALOGUE[BondPhase.NEW]}
    familiar_level_three = {
        line.text
        for line in BOND_DIALOGUE[BondPhase.FAMILIAR]
        if line.required_level == 3
    }

    assert familiar_level_three <= lines
    assert new_lines.isdisjoint(lines)


def test_level_six_accumulates_comfortable_lines_without_level_seven() -> None:
    lines = set(bond_dialogue_lines(BondState(level=6)))
    level_five_or_six = {
        line.text
        for line in BOND_DIALOGUE[BondPhase.COMFORTABLE]
        if line.required_level in (5, 6)
    }
    level_seven = {
        line.text
        for line in BOND_DIALOGUE[BondPhase.COMFORTABLE]
        if line.required_level == 7
    }

    assert level_five_or_six <= lines
    assert level_seven.isdisjoint(lines)


def test_close_and_deep_bond_use_only_their_current_phase_pools() -> None:
    close_lines = set(bond_dialogue_lines(BondState(level=8)))
    deep_lines = set(bond_dialogue_lines(BondState(level=11)))

    assert close_lines == {
        line.text
        for line in BOND_DIALOGUE[BondPhase.CLOSE]
        if line.required_level <= 8
    }
    assert deep_lines == {line.text for line in BOND_DIALOGUE[BondPhase.DEEP_BOND]}


def test_contextual_ambisense_categories_remain_independent() -> None:
    bank = PhraseBank(rng=random.Random(3))

    assert bank.choose("developer") in PHRASES["developer"]
    assert bank.choose("media") in PHRASES["media"]
