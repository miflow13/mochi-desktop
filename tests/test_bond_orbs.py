"""Unit coverage for the visual-only one-orb-per-XP particle field."""

from __future__ import annotations

import random

from mochi.bond_orbs import (
    GAIN_MARKER_DURATION_SECONDS,
    DENSE_ORB_THRESHOLD,
    LEVEL_UP_BLOOM_DURATION_SECONDS,
    MAX_ACTIVE_GAIN_MARKERS,
    MAX_ACTIVE_ORBS,
    MAX_ACTIVE_PULSES,
    ORB_EMIT_INTERVAL_SECONDS,
    XpOrb,
    XpOrbField,
)


def test_queue_preserves_one_orb_per_xp() -> None:
    field = XpOrbField(rng=random.Random(7))

    assert field.queue_xp(5) == 5
    assert field.pending_xp == 5
    assert field.total_emitted == 0


def test_first_queued_xp_emits_immediately_on_next_tick() -> None:
    field = XpOrbField(rng=random.Random(7))
    field.queue_xp(1)

    changed = field.advance(
        0.0,
        width=128,
        height=128,
        target_x=64,
        target_y=72,
    )

    assert changed is True
    assert field.pending_xp == 0
    assert field.active_count == 1
    assert field.total_emitted == 1


def test_large_reward_streams_without_exceeding_active_cap() -> None:
    field = XpOrbField(rng=random.Random(7))
    field.queue_xp(60)

    for _ in range(60):
        field.advance(
            ORB_EMIT_INTERVAL_SECONDS,
            width=128,
            height=128,
            target_x=64,
            target_y=72,
        )
        assert field.active_count <= MAX_ACTIVE_ORBS

    assert field.total_emitted > 0
    assert field.total_emitted + field.pending_xp >= 60 - field.active_count


def test_dense_reward_uses_bounded_particle_count() -> None:
    field = XpOrbField(rng=random.Random(13))
    field.queue_xp(60)

    peak = 0
    for _ in range(240):
        field.advance(
            0.016,
            width=128,
            height=128,
            target_x=64,
            target_y=72,
        )
        peak = max(peak, field.active_count)

    assert peak <= MAX_ACTIVE_ORBS
    assert MAX_ACTIVE_ORBS > DENSE_ORB_THRESHOLD


def test_dense_spawn_pattern_reaches_all_four_quadrants() -> None:
    field = XpOrbField(rng=random.Random(17))
    field.queue_xp(12)

    # Give the emitter enough accumulated time to fill its bounded active set.
    field.advance(
        1.0,
        width=128,
        height=128,
        target_x=64,
        target_y=64,
    )

    quadrants = {
        (orb.start_x >= 64, orb.start_y >= 64)
        for orb in field._active
    }
    assert len(quadrants) == 4


def test_every_queued_xp_eventually_becomes_exactly_one_orb() -> None:
    field = XpOrbField(rng=random.Random(11))
    field.queue_xp(60)

    for _ in range(500):
        field.advance(
            0.05,
            width=128,
            height=128,
            target_x=64,
            target_y=72,
        )
        if not field.has_activity:
            break

    assert field.pending_xp == 0
    assert field.active_count == 0
    assert field.pulse_count == 0
    assert field.total_emitted == 60


def test_orb_curves_to_exact_target_and_fades_at_collection() -> None:
    orb = XpOrb(
        start_x=10,
        start_y=20,
        sway=12,
        age_seconds=0,
        duration_seconds=1,
        radius=3,
    )

    assert orb.position(64, 72) == (10, 20)
    assert orb.alpha > 0

    orb.age_seconds = 1
    x, y = orb.position(64, 72)

    assert round(x, 5) == 64
    assert round(y, 5) == 72
    assert orb.alpha == 0
    assert orb.complete is True


def test_collected_orb_creates_short_absorption_pulse() -> None:
    field = XpOrbField(rng=random.Random(5))
    field.queue_xp(1)
    field.advance(0.0, width=128, height=128, target_x=64, target_y=72)

    field.advance(2.0, width=128, height=128, target_x=64, target_y=72)

    assert field.active_count == 0
    assert field.pulse_count == 1
    assert field.has_activity is True

    field.advance(1.0, width=128, height=128, target_x=64, target_y=72)
    assert field.pulse_count == 0


def test_gain_marker_floats_and_self_finishes_without_adding_xp() -> None:
    field = XpOrbField(rng=random.Random(4))

    assert field.show_gain_marker(1) == 1
    assert field.marker_count == 1
    assert field.pending_xp == 0
    assert field.total_emitted == 0
    assert field.has_activity is True

    field.advance(
        GAIN_MARKER_DURATION_SECONDS + 0.01,
        width=128,
        height=128,
        target_x=64,
        target_y=72,
    )

    assert field.marker_count == 0
    assert field.pending_xp == 0
    assert field.total_emitted == 0


def test_large_award_uses_one_marker_for_the_award_amount() -> None:
    field = XpOrbField(rng=random.Random(9))

    assert field.show_gain_marker(60) == 60
    assert field.marker_count == 1


def test_level_up_bloom_is_feedback_only_and_self_finishes() -> None:
    field = XpOrbField(rng=random.Random(2))
    field.trigger_level_up()

    assert field.level_up_active is True
    assert field.pending_xp == 0
    assert field.total_emitted == 0

    field.advance(
        LEVEL_UP_BLOOM_DURATION_SECONDS + 0.01,
        width=128,
        height=128,
        target_x=64,
        target_y=72,
    )

    assert field.level_up_active is False
    assert field.total_emitted == 0


def test_invalid_or_negative_awards_do_not_queue_particles() -> None:
    field = XpOrbField(rng=random.Random(3))

    assert field.queue_xp(-10) == 0
    assert field.queue_xp("bad") == 0
    assert field.has_activity is False


def test_feed_sized_feedback_stays_bounded_through_full_lifecycle() -> None:
    field = XpOrbField(rng=random.Random(23))
    field.queue_xp(60)
    field.show_gain_marker(60)

    peak_orbs = 0
    peak_pulses = 0
    peak_markers = 0
    for _ in range(600):
        field.advance(
            0.016,
            width=112,
            height=112,
            target_x=56,
            target_y=64,
        )
        peak_orbs = max(peak_orbs, field.active_count)
        peak_pulses = max(peak_pulses, field.pulse_count)
        peak_markers = max(peak_markers, field.marker_count)
        if not field.has_activity:
            break

    assert field.total_emitted == 60
    assert field.pending_xp == 0
    assert peak_orbs <= MAX_ACTIVE_ORBS
    assert peak_pulses <= MAX_ACTIVE_PULSES
    assert peak_markers <= MAX_ACTIVE_GAIN_MARKERS
    assert field.has_activity is False
