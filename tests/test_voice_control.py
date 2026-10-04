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
