"""GTK behavior of the "Talk to Mochi" placeholder control (needs a display)."""

from __future__ import annotations

import time

import pytest

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.presence.voice_control import MARGIN_PX, VoiceControl  # noqa: E402
from mochi.voice_control_model import BUTTON_RADIUS  # noqa: E402

pytestmark = pytest.mark.skipif(
    Gdk.Display.get_default() is None, reason="needs a display (run under xvfb-run)"
)

CENTER = MARGIN_PX + BUTTON_RADIUS  # the circle's center in the button's coordinates


def _pump(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        context.iteration(False)
        time.sleep(0.005)


@pytest.fixture
def control():
    owner = Gtk.Window()
    owner.present()
    activations: list[int] = []
    voice = VoiceControl(
        owner=owner, anchor_widget=owner, on_activate=lambda: activations.append(1)
    )
    voice.activations = activations
    yield voice
    voice.destroy()
    owner.destroy()


def test_release_inside_activates_once(control) -> None:
    control._on_pressed(None, 1, CENTER, CENTER)
    control._on_released(None, 1, CENTER + 3, CENTER)

    assert control.activations == [1]


def test_release_outside_the_circle_cancels(control) -> None:
    control._on_pressed(None, 1, CENTER, CENTER)
    assert control._pressed  # the press itself registered
    control._on_released(None, 1, 2, 2)  # transparent corner

    assert control.activations == []
    assert not control._pressed


def test_press_on_the_transparent_corner_does_nothing(control) -> None:
    control._on_pressed(None, 1, 2, 2)
    control._on_released(None, 1, CENTER, CENTER)

    assert control.activations == []


def test_space_with_key_repeat_activates_once_on_release(control) -> None:
    for _ in range(3):  # auto-repeat resends key-pressed only
        control._on_key_pressed(None, Gdk.KEY_space, 0, 0)
    control._on_key_released(None, Gdk.KEY_space, 0, 0)

    assert control.activations == [1]


def test_placeholder_toggles_and_escape_closes(control) -> None:
    control.toggle_placeholder()
    assert control._panel.get_visible()

    control._on_panel_key(None, Gdk.KEY_Escape, 0, 0)
    assert not control._panel.get_visible()

    control.toggle_placeholder()
    control.toggle_placeholder()  # repeated activation closes it
    assert not control._panel.get_visible()


def test_hover_animation_stops_when_hidden(control) -> None:
    control.set_pointer_near(True)
    control._set_hovered(True)
    _pump(0.2)
    assert control._frame_source_id is not None  # waveform is animating

    control._set_hovered(False)
    control.set_pointer_near(False)
    _pump(0.9)  # 350 ms grace + 140 ms fade + 160 ms settle, with slack

    assert not control.window.get_visible()
    assert control._frame_source_id is None


def _pump_until(condition, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        _pump(0.02)
    return condition()


def test_open_panel_stops_the_hover_animation(control) -> None:
    # Xvfb has no window manager to activate the panel, so MenuWindow's
    # outside-click dismissal would close it; that behavior is not under test.
    control._panel._dismiss_on_focus_loss = False
    control.set_pointer_near(True)
    control._set_hovered(True)
    _pump(0.1)
    control.toggle_placeholder()

    assert _pump_until(lambda: control._frame_source_id is None)
    assert control._panel.get_visible()


def test_destroy_removes_the_frame_timer(control) -> None:
    control.set_pointer_near(True)
    control._set_hovered(True)
    _pump(0.1)

    control.destroy()

    assert control._frame_source_id is None


def test_proximity_signal_shows_and_hides_the_control(control) -> None:
    control.set_pointer_near(True)
    _pump(0.2)
    assert control.window.get_visible()

    control.set_pointer_near(False)
    _pump(0.9)
    assert not control.window.get_visible()
    assert control._frame_source_id is None


def test_proximity_zone_is_relative_to_mochi_and_starts_under_him(control) -> None:
    _pump(0.2)  # let the owner window get a size
    height = control._owner.get_height()

    zone = control.proximity_zone(500.0, 300.0)

    assert zone is not None
    # Relative to Mochi's window: it starts just under him (12 px gap minus the
    # 24 px padding) and does not reach his middle.
    assert height / 2 < zone.y <= height


def test_returning_focus_from_the_panel_keeps_the_control_shown(control) -> None:
    control._panel._dismiss_on_focus_loss = False
    control.set_pointer_near(True)
    _pump(0.1)
    control.toggle_placeholder()
    assert _pump_until(lambda: control._panel.window.is_active())
    control.set_pointer_near(False)  # only the panel keeps it shown now

    control._on_panel_key(None, Gdk.KEY_Escape, 0, 0)  # focus back to the control
    _pump(0.9)  # longer than the grace period and fade-out

    assert control._focused
    assert control.window.get_visible()


def test_a_press_that_dismissed_the_panel_does_not_reopen_it(control) -> None:
    control.toggle_placeholder()
    control._on_pressed(None, 1, CENTER, CENTER)
    # Focus moved to the control on press, so MenuWindow's outside-click
    # dismissal closed the panel before the release arrives.
    control._panel.popdown()
    control._on_released(None, 1, CENTER, CENTER)

    assert not control._panel.get_visible()
    assert control.activations == []  # no toggle, which would reopen it


def test_a_press_on_the_still_open_panel_activates(control) -> None:
    control._panel._dismiss_on_focus_loss = False
    control.toggle_placeholder()
    control._on_pressed(None, 1, CENTER, CENTER)
    control._on_released(None, 1, CENTER, CENTER)

    assert control.activations == [1]  # the seam toggles it closed


def test_losing_focus_cancels_a_held_key(control) -> None:
    control.set_pointer_near(True)
    control.window.present()
    assert _pump_until(control.window.is_active)
    control._on_key_pressed(None, Gdk.KEY_space, 0, 0)
    assert control._pressed

    control._owner.present()  # the user switches away with Space held
    assert _pump_until(lambda: not control.window.is_active())
    control._on_key_released(None, Gdk.KEY_space, 0, 0)  # e.g. a stale release

    assert not control._pressed
    assert control.activations == []


def test_only_one_frame_timer_is_ever_live(control, monkeypatch) -> None:
    from mochi.presence import voice_control

    added: list[int] = []
    real_timeout_add = GLib.timeout_add

    def recording_timeout_add(*args):
        source_id = real_timeout_add(*args)
        added.append(source_id)
        return source_id

    monkeypatch.setattr(voice_control.GLib, "timeout_add", recording_timeout_add)
    settings = Gtk.Settings.get_default()
    animations = settings.props.gtk_enable_animations
    settings.props.gtk_enable_animations = False
    try:
        # Reduced motion: showing needs no further frames, then hovering the
        # circle waits out the label delay and does.
        control.set_pet_hovered(True)
        control._set_hovered(True)
        context = GLib.MainContext.default()
        live = [i for i in added if (s := context.find_source_by_id(i)) and not s.is_destroyed()]
        assert len(live) <= 1
        assert live == ([control._frame_source_id] if control._frame_source_id else [])
    finally:
        settings.props.gtk_enable_animations = animations


def test_destroy_also_destroys_the_panel_window(control) -> None:
    panel_window = control._panel.window
    control.toggle_placeholder()

    control.destroy()

    assert panel_window not in Gtk.Window.list_toplevels()


def test_under_reserves_room_for_the_margin_and_the_label(control, monkeypatch) -> None:
    from mochi.presence import voice_control

    seen = {}
    real_place_control = voice_control.place_control

    def capture(sprite, work_area, *, reserve_below, side):
        seen["reserve_below"] = reserve_below
        return real_place_control(sprite, work_area, reserve_below=reserve_below, side=side)

    monkeypatch.setattr(voice_control, "place_control", capture)
    control._placement_for(100.0, 100.0)

    label_height = control.label.get_preferred_size()[1].height
    assert label_height > 0  # measured before the label is ever shown
    assert seen["reserve_below"] == MARGIN_PX + label_height
