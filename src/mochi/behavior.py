"""Mochi's small collection of v0.1 reactions."""

from __future__ import annotations

import random

from mochi.animation import Animation
from mochi.sprites import ANIMATIONS


def choose_click_reaction(
    recent: tuple[str, ...] = (), rng: random.Random | None = None
) -> Animation:
    """Choose a tactile reaction, gently discouraging three repeats in a row."""
    generator = rng or random
    bounce_probability = 0.55
    if len(recent) >= 2 and recent[-1] == recent[-2]:
        bounce_probability = 0.40 if recent[-1] == "bounce" else 0.60
    name = "bounce" if generator.random() < bounce_probability else "squish"
    return ANIMATIONS[name]
