"""Regression tests for the Nameplate positioning pipeline.

These exercise the pure position-calculation logic (`_position_x11`,
`_visible_anchor_bounds`, monitor selection/clamping) without constructing
real GTK windows, mirroring the `SimpleNamespace`-based approach already used
in `test_windowing.py`. Widget construction is bypassed via
`object.__new__(Nameplate)` so no display/X server-backed Gtk.Window or
Gtk.Popover needs to be created for these checks.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mochi.animation import AnimationFrame
from mochi.presence.nameplate import Nameplate


class MonitorList:
    def __init__(self, *monitors) -> None:
        self._monitors = monitors

    def get_n_items(self) -> int:
        return len(self._monitors)

    def get_item(self, index: int):
        return self._monitors[index]


def monitor(x: int, y: int, width: int, height: int):
    geometry = SimpleNamespace(x=x, y=y, width=width, height=height)
    return SimpleNamespace(get_geometry=lambda: geometry)


def _owner(monitors, *, width=128, height=128, scale=1.0, x=0, y=0):
    surface = SimpleNamespace(get_scale=lambda: scale)
    return SimpleNamespace(
        get_width=lambda: width,
        get_height=lambda: height,
        get_surface=lambda: surface,
        get_display=lambda: SimpleNamespace(get_monitors=lambda: monitors),
    )


def _plate_window(*, width=52, height=18, scale=1.0):
    surface = SimpleNamespace(get_scale=lambda: scale)
    moved: dict[str, tuple[int, int]] = {}

    def _get_width():
        return width

    def _get_height():
        return height

    return SimpleNamespace(
        get_width=_get_width,
        get_height=_get_height,
        get_surface=lambda: surface,
        get_visible=lambda: True,
    ), moved


def _make_nameplate(*, owner, plate_window) -> Nameplate:
    plate = object.__new__(Nameplate)
    plate._owner = owner
    plate._anchor = SimpleNamespace(get_width=owner.get_width, get_height=owner.get_height)
    plate._window = plate_window
    plate._logger = SimpleNamespace(debug=lambda *a, **k: None)
    return plate


class NameplatePositionTests(unittest.TestCase):
    def test_centers_above_mochi_on_a_single_monitor(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1920, 1080))
        owner = _owner(monitors, width=128, height=128, x=400, y=300)
        plate_window, _ = _plate_window(width=52, height=18)
        plate = _make_nameplate(owner=owner, plate_window=plate_window)

        moved = {}
        with patch(
            "mochi.presence.nameplate.get_window_position",
            return_value=(400, 300),
        ), patch(
            "mochi.presence.nameplate.move_window",
            side_effect=lambda _window, x, y: moved.update(x=x, y=y),
        ):
            plate._position_x11()

        # Horizontally centered over the (default, full-widget) visible bounds.
        expected_center_x = 400 + 128 / 2
        self.assertAlmostEqual(moved["x"] + 52 / 2, expected_center_x, delta=1)
        # Sits above Mochi's top edge (owner_y) minus the gap.
        self.assertLess(moved["y"] + 18, 300)

    def test_uses_monitor_containing_mochi_not_the_primary_monitor(self) -> None:
        # Secondary monitor to the right, plus a negative-origin monitor above
        # both -- Mochi is on the secondary (rightmost) monitor.
        monitors = MonitorList(
            monitor(0, 0, 1920, 1080),
            monitor(-1920, -200, 1920, 1080),
            monitor(1920, 0, 2560, 1440),
        )
        owner = _owner(monitors, width=128, height=128, x=2000, y=100)
        plate_window, _ = _plate_window()
        plate = _make_nameplate(owner=owner, plate_window=plate_window)

        moved = {}
        with patch(
            "mochi.presence.nameplate.get_window_position",
            return_value=(2000, 100),
        ), patch(
            "mochi.presence.nameplate.move_window",
            side_effect=lambda _window, x, y: moved.update(x=x, y=y),
        ):
            plate._position_x11()

        # Clamped to the secondary monitor's bounds (x in [1920, 4480]),
        # not the primary monitor at x in [0, 1920].
        self.assertGreaterEqual(moved["x"], 1920)

    def test_clamps_to_negative_origin_monitor_without_drifting_off_screen(self) -> None:
        monitors = MonitorList(monitor(-1920, -1080, 1920, 1080))
        owner = _owner(monitors, width=128, height=128, x=-1900, y=-1060)
        plate_window, _ = _plate_window()
        plate = _make_nameplate(owner=owner, plate_window=plate_window)

        moved = {}
        with patch(
            "mochi.presence.nameplate.get_window_position",
            return_value=(-1900, -1060),
        ), patch(
            "mochi.presence.nameplate.move_window",
            side_effect=lambda _window, x, y: moved.update(x=x, y=y),
        ):
            plate._position_x11()

        self.assertGreaterEqual(moved["x"], -1920)
        self.assertGreaterEqual(moved["y"], -1080)

    def test_hides_when_owner_position_is_unavailable(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1920, 1080))
        owner = _owner(monitors)
        plate_window, _ = _plate_window()
        plate = _make_nameplate(owner=owner, plate_window=plate_window)
        plate._popover = SimpleNamespace(
            get_visible=lambda: False, popdown=lambda: None
        )
        plate._window = SimpleNamespace(
            get_visible=lambda: True, hide=lambda: hidden.append(True)
        )
        hidden: list[bool] = []

        with patch("mochi.presence.nameplate.get_window_position", return_value=None):
            plate._position_x11()

        self.assertTrue(hidden)

    def test_scaling_is_applied_consistently_between_owner_and_plate(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1920, 1080))
        owner = _owner(monitors, width=128, height=128, x=800, y=400, scale=2.0)
        plate_window, _ = _plate_window(width=52, height=18, scale=2.0)
        plate = _make_nameplate(owner=owner, plate_window=plate_window)

        moved = {}
        with patch(
            "mochi.presence.nameplate.get_window_position",
            return_value=(800, 400),
        ), patch(
            "mochi.presence.nameplate.move_window",
            side_effect=lambda _window, x, y: moved.update(x=x, y=y),
        ):
            plate._position_x11()

        expected_center_x = 800 + (128 * 2.0) / 2
        self.assertAlmostEqual(moved["x"] + (52 * 2.0) / 2, expected_center_x, delta=2)

    def test_anchor_ignores_live_player_frame_and_stays_pixel_stable(self) -> None:
        """The plate must anchor to a fixed reference frame, not whatever
        Mochi's live animation frame happens to be.

        Different idle/blink/bounce/emote frames vary in both whole-frame
        offset and silhouette bounds (breathing, blinking, etc.), so using
        the live `player.frame` made the plate jitter a few pixels every
        tick. Anchoring is fixed regardless of what `player.frame` reports.
        """
        monitors = MonitorList(monitor(0, 0, 1920, 1080))

        # A visible_bounds stand-in whose output *would* differ per frame,
        # to prove the live/varying frame is never actually consulted.
        def _visible_bounds(frame, width, height):
            return (10.0 + frame.horizontal_offset, 10.0, 100.0, 100.0)

        positions = []
        live_frames = (
            AnimationFrame(sprite="idle_0", horizontal_offset=0.0),
            AnimationFrame(sprite="bounce_3", horizontal_offset=12.0, vertical_offset=-8.0),
            AnimationFrame(sprite="blink_2", horizontal_offset=-6.0, vertical_offset=5.0),
        )
        for live_frame in live_frames:
            owner = _owner(monitors, width=128, height=128, x=800, y=400)
            plate_window, _ = _plate_window(width=52, height=18)
            plate = _make_nameplate(owner=owner, plate_window=plate_window)
            plate._anchor.atlas = SimpleNamespace(visible_bounds=_visible_bounds)
            plate._anchor.player = SimpleNamespace(frame=live_frame)

            moved = {}
            with patch(
                "mochi.presence.nameplate.get_window_position",
                return_value=(800, 400),
            ), patch(
                "mochi.presence.nameplate.move_window",
                side_effect=lambda _window, x, y: moved.update(x=x, y=y),
            ):
                plate._position_x11()
            positions.append((moved["x"], moved["y"]))

        self.assertEqual(positions[0], positions[1])
        self.assertEqual(positions[0], positions[2])

    def test_reference_frame_passed_to_visible_bounds_has_zeroed_offsets(self) -> None:
        monitors = MonitorList(monitor(0, 0, 1920, 1080))
        owner = _owner(monitors, width=128, height=128, x=800, y=400)
        plate_window, _ = _plate_window(width=52, height=18)
        plate = _make_nameplate(owner=owner, plate_window=plate_window)

        seen_frames = []

        def _visible_bounds(frame, width, height):
            seen_frames.append(frame)
            return (10.0, 10.0, 100.0, 100.0)

        plate._anchor.atlas = SimpleNamespace(visible_bounds=_visible_bounds)
        # Even a live frame with large offsets must not influence the frame
        # actually passed to visible_bounds().
        plate._anchor.player = SimpleNamespace(
            frame=AnimationFrame(
                sprite="idle_0", horizontal_offset=25.0, vertical_offset=-14.0
            )
        )

        with patch(
            "mochi.presence.nameplate.get_window_position",
            return_value=(800, 400),
        ), patch("mochi.presence.nameplate.move_window"):
            plate._position_x11()

        self.assertEqual(len(seen_frames), 1)
        self.assertEqual(seen_frames[0].horizontal_offset, 0.0)
        self.assertEqual(seen_frames[0].vertical_offset, 0.0)


class NameplateContentTests(unittest.TestCase):
    def test_set_name_and_status_compose_two_line_text(self) -> None:
        plate = object.__new__(Nameplate)
        plate._name = "Mochi"
        plate._status = None
        plate._label = SimpleNamespace(set_text=lambda text: labels.append(text))
        plate._popover_label = SimpleNamespace(set_text=lambda _text: None)
        plate._window = SimpleNamespace(get_visible=lambda: False)
        plate._popover = SimpleNamespace(get_visible=lambda: False)
        labels: list[str] = []

        plate.set_status("cozy")
        self.assertEqual(labels[-1], "Mochi\ncozy")

        plate.clear_status()
        self.assertEqual(labels[-1], "Mochi")

    def test_set_name_falls_back_to_mochi_when_blank(self) -> None:
        plate = object.__new__(Nameplate)
        plate._name = "Mochi"
        plate._status = None
        plate._label = SimpleNamespace(set_text=lambda _text: None)
        plate._popover_label = SimpleNamespace(set_text=lambda _text: None)
        plate._window = SimpleNamespace(get_visible=lambda: False)
        plate._popover = SimpleNamespace(get_visible=lambda: False)

        plate.set_name("   ")
        self.assertEqual(plate._name, "Mochi")


if __name__ == "__main__":
    unittest.main()
