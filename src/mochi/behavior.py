"""Mochi's small collection of v0.1 reactions."""

from __future__ import annotations

import random

from mochi.animation import Animation
from mochi.sprites import ANIMATIONS


def choose_click_reaction(rng: random.Random | None = None) -> Animation:
    return (rng or random).choice(
        (ANIMATIONS["bounce"], ANIMATIONS["squish"], ANIMATIONS["excited"])
    )
