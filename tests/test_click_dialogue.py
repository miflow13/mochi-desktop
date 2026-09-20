"""Direct bond-dialogue regression coverage."""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.care import BondState
from mochi.presence.click_dialogue import ClickDialogueMixin
from mochi.presence.engine import PresenceTuning
from mochi.presence.phrases import PhraseBank, bond_dialogue_lines


class _ClickBase:
    def react_to_click(self) -> None:
        self.base_click_count += 1


class _ClickHarness(ClickDialogueMixin, _ClickBase):
    pass


def _harness(level: int = 1) -> _ClickHarness:
    harness = object.__new__(_ClickHarness)
    harness._preview_mode = False
    harness._sound = Mock()
    harness._click_burst_detector = Mock()
    harness._fedora_click_detector = Mock()
    harness._fedora_mode_holding = False
    harness._toggle_fedora_mode = Mock()
    harness._bond_state = BondState(level=level)
    harness._presence_bubble = Mock()
    harness._presence_bubble.show.return_value = True
    harness._ambient_presence_engine = SimpleNamespace(
        tuning=PresenceTuning(),
        phrases=PhraseBank(rng=random.Random(4)),
    )
    harness._dismiss_presence_bubble = Mock()
    harness._logger = Mock()
    harness.base_click_count = 0
    return harness


def test_triple_click_uses_one_direct_bond_dialogue_response() -> None:
    harness = _harness(level=3)
    harness._click_burst_detector.record.return_value = True
    harness._fedora_click_detector.record.return_value = False

    harness.react_to_click()

    harness._sound.play.assert_called_once()
    assert harness.base_click_count == 1
    harness._presence_bubble.show.assert_called_once()
    text = harness._presence_bubble.show.call_args.args[0]
    assert text in bond_dialogue_lines(BondState(level=3))


def test_direct_bond_dialogue_avoids_immediate_repetition() -> None:
    harness = _harness(level=6)

    assert harness._show_click_burst_dialogue() is True
    assert harness._show_click_burst_dialogue() is True

    first, second = [
        call.args[0] for call in harness._presence_bubble.show.call_args_list
    ]
    assert first != second
    assert first in bond_dialogue_lines(BondState(level=6))
    assert second in bond_dialogue_lines(BondState(level=6))


def test_six_click_fedora_secret_still_takes_precedence() -> None:
    harness = _harness()
    harness._click_burst_detector.record.return_value = True
    harness._fedora_click_detector.record.return_value = True

    harness.react_to_click()

    harness._click_burst_detector.reset.assert_called_once_with()
    harness._toggle_fedora_mode.assert_called_once_with()
    assert harness.base_click_count == 0
    harness._presence_bubble.show.assert_not_called()


def test_direct_dialogue_respects_speech_and_quiet_controls() -> None:
    harness = _harness()
    harness._ambient_presence_engine.tuning.speech_enabled = False
    assert harness._show_click_burst_dialogue() is False
    harness._presence_bubble.show.assert_not_called()

    harness._ambient_presence_engine.tuning.speech_enabled = True
    harness._ambient_presence_engine.tuning.quiet_mode = True
    assert harness._show_click_burst_dialogue() is False
    harness._presence_bubble.show.assert_not_called()


def test_bond_dialogue_preview_uses_production_selector_without_mutating_bond() -> None:
    harness = _harness(level=8)
    original = harness._bond_state

    harness._preview_bond_dialogue()

    assert harness._bond_state == original
    harness._presence_bubble.show.assert_called_once()
    text = harness._presence_bubble.show.call_args.args[0]
    assert text in bond_dialogue_lines(original)
    assert harness._logger.debug.call_args.args[2] == "CLOSE"
