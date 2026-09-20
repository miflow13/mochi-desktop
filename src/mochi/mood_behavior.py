"""Resolve mood-specific movement and idle presentation.

This module deliberately contains no state transitions and no timers. It maps
an already-selected MochiMood onto optional animation variants and movement
tuning while MochiState remains the source of truth for what Mochi is doing.

Asset contract for the first SAD profile:
- sad_idle
- sad_walk
- sad_walk_left

Those manifest entries are optional. Until the art is installed, resolution
falls back to Mochi's normal idle/walk animations automatically.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from mochi.mood import MochiMood


@dataclass(frozen=True)
class MoodBehaviorProfile:
    """Optional visual/movement overrides for one mood."""

    idle_animation: str | None = None
    walk_animation: str | None = None
    walk_left_animation: str | None = None
    walk_speed_multiplier: float = 1.0

    def animation_for(self, base_animation: str) -> str | None:
        return {
            "idle": self.idle_animation,
            "walk": self.walk_animation,
            "walk_left": self.walk_left_animation,
        }.get(base_animation)


_DEFAULT_PROFILE = MoodBehaviorProfile()

MOOD_BEHAVIOR_PROFILES: dict[MochiMood, MoodBehaviorProfile] = {
    MochiMood.SAD: MoodBehaviorProfile(
        idle_animation="sad_idle",
        walk_animation="sad_walk",
        walk_left_animation="sad_walk_left",
        walk_speed_multiplier=0.80,
    ),
}


def behavior_profile_for(mood: MochiMood) -> MoodBehaviorProfile:
    return MOOD_BEHAVIOR_PROFILES.get(mood, _DEFAULT_PROFILE)


def resolve_mood_animation(
    mood: MochiMood,
    base_animation: str,
    available_animations: Mapping[str, object],
) -> str:
    """Return a mood variant only when that asset is actually available."""
    candidate = behavior_profile_for(mood).animation_for(base_animation)
    if candidate is not None and candidate in available_animations:
        return candidate
    return base_animation
