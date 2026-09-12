from __future__ import annotations

import random

from mochi.presence.context import AmbientContext
from mochi.presence.engine import PresenceEngine, PresenceTuning
from mochi.presence.phrases import CONTEXT_PHRASES, EVENT_PHRASES, PHRASES, PhraseBank


class Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def test_default_presence_uses_lively_ambisense_profile():
    tuning = PresenceTuning()
    assert tuning.ambient_min_seconds == 20
    assert tuning.ambient_max_seconds == 60
    assert tuning.ambient_silence_probability == 0.10
    assert tuning.global_cooldown_seconds == 25
    assert tuning.max_phrases_per_hour == 30
    assert tuning.typing_medium_sustain_seconds == 12
    assert tuning.typing_high_sustain_seconds == 8
    assert tuning.typing_comment_probability == 1.0


def test_startup_phrase_bank_exists():
    text = PhraseBank(rng=random.Random(1)).choose("startup")
    assert isinstance(text, str)
    assert text


def test_large_phrase_bank_is_loaded_by_category():
    expected_counts = {
        "ambient": 49,
        "encouragement": 41,
        "focus": 38,
        "developer": 61,
        "body_care": 42,
        "rest": 31,
        "frustration": 32,
        "creative": 34,
        "mischief": 47,
        "companionship": 28,
    }
    for category, expected in expected_counts.items():
        assert len(PHRASES[category]) == expected
        assert len(set(PHRASES[category])) == expected
    assert sum(len(PHRASES[name]) for name in expected_counts) == 403


def test_context_only_lines_do_not_leak_into_random_ambient_pool():
    assert CONTEXT_PHRASES["many_browser_tabs"] == ("the tabs are reproducing",)
    assert CONTEXT_PHRASES["screenshot_taken"] == ("cheese 📸",)
    assert "the tabs are reproducing" not in PHRASES["ambient"]
    assert "cheese 📸" not in PHRASES["ambient"]


def test_supported_context_events_use_specific_lines():
    assert "green! 🌱" in EVENT_PHRASES["build_succeeded"]
    assert "hmm. clues." in EVENT_PHRASES["build_failed"]
    assert "snack acquired ⚡" in EVENT_PHRASES["charging_started"]
    assert "oh we're watching something?" in EVENT_PHRASES["media_started"]


def test_typing_session_sustain_survives_intensity_changes():
    clock = Clock()
    engine = PresenceEngine(clock=clock, rng=random.Random(1))

    engine.record_typing_activity(now=0)
    for index in range(1, 31):
        engine.record_typing_activity(now=index * 0.1)

    _intensity, sustained = engine.typing_snapshot(now=10)
    assert sustained == 10

    engine.record_typing_stopped(now=11)
    _intensity, sustained = engine.typing_snapshot(now=12)
    assert sustained == 0


def test_real_sustained_typing_can_produce_comment():
    clock = Clock()
    tuning = PresenceTuning(
        ambient_min_seconds=9999,
        ambient_max_seconds=9999,
        global_cooldown_seconds=0,
        same_category_min_seconds=0,
        same_category_max_seconds=0,
        max_phrases_per_hour=50,
        typing_medium_sustain_seconds=2,
        typing_high_sustain_seconds=2,
        typing_comment_probability=1,
    )
    engine = PresenceEngine(tuning=tuning, clock=clock, rng=random.Random(2))

    for index in range(31):
        engine.record_typing_activity(now=index * 0.1)

    intensity, sustained = engine.typing_snapshot(now=3.1)
    action = engine.evaluate(
        AmbientContext(
            typing_intensity=intensity,
            typing_sustained_seconds=sustained,
        ),
        now=3.1,
    )

    assert action is not None
    assert action.category == "typing"
    assert action.event == "typing_sustained"
