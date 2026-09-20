"""Mood-specific idle/walk resolver tests."""

from __future__ import annotations

import unittest

from mochi.mood import MochiMood
from mochi.mood_behavior import behavior_profile_for, resolve_mood_animation


class MoodBehaviorTests(unittest.TestCase):
    def test_sad_profile_declares_plug_in_asset_contract(self) -> None:
        profile = behavior_profile_for(MochiMood.SAD)
        self.assertEqual(profile.idle_animation, "sad_idle")
        self.assertEqual(profile.walk_animation, "sad_walk")
        self.assertEqual(profile.walk_left_animation, "sad_walk_left")
        self.assertLess(profile.walk_speed_multiplier, 1.0)

    def test_sad_animation_is_used_when_asset_exists(self) -> None:
        available = {"idle": object(), "sad_idle": object()}
        self.assertEqual(
            resolve_mood_animation(MochiMood.SAD, "idle", available),
            "sad_idle",
        )

    def test_missing_mood_asset_falls_back_to_base_animation(self) -> None:
        available = {"idle": object(), "walk": object(), "walk_left": object()}
        for base in ("idle", "walk", "walk_left"):
            with self.subTest(base=base):
                self.assertEqual(
                    resolve_mood_animation(MochiMood.SAD, base, available),
                    base,
                )

    def test_unprofiled_mood_keeps_normal_animation(self) -> None:
        available = {"idle": object(), "sad_idle": object()}
        self.assertEqual(
            resolve_mood_animation(MochiMood.CONTENT, "idle", available),
            "idle",
        )


if __name__ == "__main__":
    unittest.main()
