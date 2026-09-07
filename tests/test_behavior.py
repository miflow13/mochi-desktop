import random
import unittest

from mochi.behavior import choose_click_reaction


class ClickReactionTests(unittest.TestCase):
    def test_default_weight_is_about_fifty_five_percent_bounce(self) -> None:
        rng = random.Random(42)
        results = [choose_click_reaction(rng=rng).name for _ in range(10_000)]
        self.assertAlmostEqual(results.count("bounce") / len(results), 0.55, delta=0.02)
        self.assertEqual(set(results), {"bounce", "squish"})

    def test_two_repeats_favor_the_other_reaction(self) -> None:
        bounce_rng = random.Random(42)
        after_bounces = [
            choose_click_reaction(("bounce", "bounce"), bounce_rng).name
            for _ in range(10_000)
        ]
        squish_rng = random.Random(42)
        after_squishes = [
            choose_click_reaction(("squish", "squish"), squish_rng).name
            for _ in range(10_000)
        ]
        self.assertAlmostEqual(after_bounces.count("bounce") / 10_000, 0.40, delta=0.02)
        self.assertAlmostEqual(after_squishes.count("bounce") / 10_000, 0.60, delta=0.02)


if __name__ == "__main__":
    unittest.main()
