from __future__ import annotations

import random

from mochi.presence.context import AmbientContext
from mochi.presence.engine import PresenceEngine, PresenceTuning


def test_user_inactive_suppresses_unsolicited_speech():
    tuning = PresenceTuning(
        ambient_min_seconds=0,
        ambient_max_seconds=0,
        ambient_silence_probability=0,
        global_cooldown_seconds=0,
    )
    engine = PresenceEngine(tuning=tuning, rng=random.Random(1), clock=lambda: 0.0)
    engine.force_ambient()
    assert engine.evaluate(AmbientContext(user_active=False), now=0) is None
