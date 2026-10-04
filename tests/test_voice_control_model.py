"""Pure logic behind the "Talk to Mochi" control: motion, placement, input."""

from __future__ import annotations

import pytest

from mochi.voice_control_model import (
    BUTTON_RADIUS,
    BUTTON_SIZE,
    HOVER_LOOP_MS,
    IDLE_HEIGHTS,
    Rect,
    VisibilityTracker,
    bar_geometry,
    bar_heights_at,
    inside_button,
    place_control,
    inflate,
    place_panel,
    settle_heights,
)


def test_idle_and_loop_endpoints_are_the_idle_pose() -> None:
    assert bar_heights_at(0) == IDLE_HEIGHTS
    assert bar_heights_at(HOVER_LOOP_MS) == IDLE_HEIGHTS
    assert bar_heights_at(HOVER_LOOP_MS * 3) == IDLE_HEIGHTS


@pytest.mark.parametrize(
    ("elapsed_ms", "pose"),
    [
        (240, (10, 18, 12, 8, 14)),
        (480, (16, 10, 8, 18, 10)),
        (720, (8, 14, 18, 10, 6)),
    ],
)
def test_keyframe_poses_match_the_spec(elapsed_ms: int, pose) -> None:
    assert bar_heights_at(elapsed_ms) == pytest.approx(pose)


def test_segments_use_cosine_ease() -> None:
    # Halfway between 0 ms and 240 ms, cosine ease is exactly halfway in value;
    # a quarter of the way it is (1 - cos(pi/4)) / 2 ~= 0.146.
    assert bar_heights_at(120)[0] == pytest.approx(8.0)
    assert bar_heights_at(60)[0] == pytest.approx(6 + 4 * 0.1464466, abs=1e-6)


def test_settle_starts_at_the_current_pose_and_ends_idle() -> None:
    current = (16.0, 10.0, 8.0, 18.0, 10.0)

    assert settle_heights(current, 0.0) == pytest.approx(current)
    assert settle_heights(current, 1.0) == pytest.approx(IDLE_HEIGHTS)
    assert settle_heights(current, 2.0) == pytest.approx(IDLE_HEIGHTS)


def test_the_control_is_small() -> None:
    assert BUTTON_SIZE == 28


def test_press_counts_only_inside_the_visible_circle() -> None:
    center = BUTTON_RADIUS
    assert inside_button(center, center)
    assert inside_button(center, 1)
    assert not inside_button(1, 1)  # transparent corner of the square box
    assert not inside_button(BUTTON_SIZE + 6, center)


def test_waveform_keeps_the_design_proportions_at_the_smaller_size() -> None:
    # The spec draws on a 48-unit button; the bars scale with the button and
    # stay at least 2 px wide so they remain crisp.
    bars = bar_geometry((6.0, 12.0, 20.0, 12.0, 6.0))

    centers = [x for x, _width, _height in bars]
    assert centers == pytest.approx([c * BUTTON_SIZE / 48 for c in (14, 19, 24, 29, 34)])
    assert all(width == 2.0 for _x, width, _height in bars)
    assert bars[2][2] == pytest.approx(20 * BUTTON_SIZE / 48)


WORK = Rect(0, 0, 1920, 1080)


def test_control_goes_under_mochi_when_there_is_room() -> None:
    sprite = Rect(900, 400, 100, 90)

    placement = place_control(sprite, WORK)

    assert placement.side == "under"
    assert placement.x == 900 + 50 - BUTTON_SIZE / 2
    assert placement.y == 400 + 90 + 12


def test_control_moves_to_the_right_when_mochi_sits_at_the_bottom() -> None:
    sprite = Rect(900, 1000, 100, 70)

    placement = place_control(sprite, WORK)

    assert placement.side == "right"
    assert placement.x == 900 + 100 + 12
    # Upper third of the sprite.
    assert placement.y == pytest.approx(1000 + 70 / 3 - BUTTON_SIZE / 2)


def test_control_mirrors_left_at_the_bottom_right_corner() -> None:
    sprite = Rect(1840, 1000, 70, 70)

    placement = place_control(sprite, WORK)

    assert placement.side == "left"
    assert placement.x == 1840 - 12 - BUTTON_SIZE


def test_control_is_clamped_inside_the_work_area_inset() -> None:
    sprite = Rect(-30, 300, 100, 90)  # partly off the left edge

    placement = place_control(sprite, WORK)

    assert placement.x == 8


def test_visibility_survives_the_gap_between_mochi_and_the_control() -> None:
    visibility = VisibilityTracker(grace_seconds=0.35)

    visibility.set_source("pet_hover", True, now=10.0)
    visibility.set_source("pet_hover", False, now=11.0)
    assert visibility.visible(now=11.2)  # crossing the 12 px gap

    visibility.set_source("control_hover", True, now=11.2)
    assert visibility.visible(now=20.0)

    visibility.set_source("control_hover", False, now=20.0)
    assert visibility.visible(now=20.34)
    assert not visibility.visible(now=20.36)


def test_dragging_hides_immediately_and_restores_with_interaction() -> None:
    visibility = VisibilityTracker(grace_seconds=0.35)
    visibility.set_source("pet_hover", True, now=1.0)

    visibility.set_dragging(True)
    assert not visibility.visible(now=1.1)

    visibility.set_dragging(False)
    assert visibility.visible(now=1.2)


def test_a_kept_side_does_not_flip_while_mochi_moves() -> None:
    first = place_control(Rect(900, 400, 100, 90), WORK)
    # Mochi walked to the bottom edge; without re-evaluation the side stays.
    followed = place_control(Rect(900, 1000, 100, 70), WORK, side=first.side)

    assert followed.side == "under"
    assert followed.y == 1080 - 8 - BUTTON_SIZE  # clamped, not flipped


def test_panel_opens_below_the_button_with_a_10px_gap() -> None:
    button = Rect(900, 600, BUTTON_SIZE, BUTTON_SIZE)

    x, y = place_panel(button, (248, 150), WORK)

    assert (x, y) == (900 + BUTTON_RADIUS - 124, 600 + BUTTON_SIZE + 10)


def test_panel_turns_toward_free_space_near_the_bottom_edge() -> None:
    button = Rect(900, 1000, BUTTON_SIZE, BUTTON_SIZE)

    x, y = place_panel(button, (248, 150), WORK)

    assert x == 900 + BUTTON_SIZE + 10  # right of the button
    assert 8 <= y and y + 150 <= 1080 - 8


def test_panel_goes_left_at_the_bottom_right_corner() -> None:
    button = Rect(1860, 1000, BUTTON_SIZE, BUTTON_SIZE)

    x, _y = place_panel(button, (248, 150), WORK)

    assert x == 1860 - 10 - 248


def test_the_proximity_zone_pads_the_control_area() -> None:
    zone = inflate(Rect(950, 500, 80, 50))  # button + label area under Mochi

    assert zone.contains(990, 520)
    assert zone.contains(950 - 23, 500 - 23)  # inside the 24 px padding
    assert not zone.contains(950 - 30, 520)
    assert not zone.contains(990, 500 + 50 + 30)


def test_the_padding_reaches_up_to_mochi_across_the_gap() -> None:
    sprite = Rect(900, 400, 100, 90)
    placement = place_control(sprite, WORK)
    control = Rect(placement.x, placement.y, BUTTON_SIZE, BUTTON_SIZE)

    zone = inflate(control)
    # Just under Mochi's bottom edge, above the button: already "close".
    assert zone.contains(950, sprite.bottom + 2)
    # Over Mochi's middle: not close, so hovering him does not show it.
    assert not zone.contains(950, sprite.y + sprite.height / 2)
