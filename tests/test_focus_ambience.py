"""Lifecycle coverage for optional local focus soundscapes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from mochi.presence.focus_session import FocusWindow
from mochi.sound import GStreamerFocusAmbienceBackend, FocusAmbienceManager


class _Backend:
    def __init__(self) -> None:
        self.started: list[tuple[Path, float]] = []
        self.started_handles: list[object] = []
        self.paused: list[object] = []
        self.resumed: list[object] = []
        self.volume_changes: list[tuple[object, float]] = []
        self.stopped: list[object] = []

    def start(self, path: Path, volume: float) -> object:
        handle = object()
        self.started.append((path, volume))
        self.started_handles.append(handle)
        return handle

    def pause(self, handle: object) -> None:
        self.paused.append(handle)

    def resume(self, handle: object) -> None:
        self.resumed.append(handle)

    def set_volume(self, handle: object, volume: float) -> None:
        self.volume_changes.append((handle, volume))

    def stop(self, handle: object) -> None:
        self.stopped.append(handle)


def test_gstreamer_backend_updates_volume_on_the_existing_player(tmp_path) -> None:
    soundscape = tmp_path / "rain.wav"
    soundscape.touch()
    player = Mock()
    gst = Mock()
    gst.ElementFactory.make.return_value = player
    gst.State.PLAYING = "playing"
    gst.State.NULL = "null"
    gst.StateChangeReturn.FAILURE = "failure"
    player.set_state.return_value = "success"
    backend = GStreamerFocusAmbienceBackend(gst)

    handle = backend.start(soundscape, 0.4)
    backend.set_volume(handle, 0.7)

    gst.ElementFactory.make.assert_called_once_with("playbin", None)
    assert player.set_state.call_args_list == [(("playing",), {})]
    assert player.set_property.call_args_list[-1] == (("volume", 0.7), {})


def test_live_volume_drag_streams_each_change_to_the_backend() -> None:
    window = object.__new__(FocusWindow)
    window._rain_volume = 0.2
    window._on_rain_volume_change = Mock()
    window._sync_rain_controls = Mock()
    scale = Mock()
    scale.get_value.side_effect = (0.3, 0.4, 0.5)

    window._handle_rain_volume_changed(scale)
    window._handle_rain_volume_changed(scale)
    window._handle_rain_volume_changed(scale)

    assert window._on_rain_volume_change.call_args_list == [
        ((0.3,), {}),
        ((0.4,), {}),
        ((0.5,), {}),
    ]


def test_focus_ambience_discovers_only_approved_local_loop_types(tmp_path) -> None:
    (tmp_path / "rain.ogg").touch()
    (tmp_path / "forest.wav").touch()
    (tmp_path / "notes.mp3").touch()

    manager = FocusAmbienceManager(asset_root=tmp_path, backend=_Backend())

    assert manager.available_soundscapes == ("forest", "rain")


def test_focus_ambience_has_no_selection_or_process_without_assets(tmp_path) -> None:
    backend = _Backend()
    manager = FocusAmbienceManager(asset_root=tmp_path, backend=backend)

    assert manager.available_soundscapes == ()
    assert manager.select("rain") is False
    assert manager.start_selected() is False
    assert backend.started == []


def test_focus_ambience_uses_one_long_lived_backend_handle(tmp_path) -> None:
    (tmp_path / "rain.ogg").touch()
    backend = _Backend()
    manager = FocusAmbienceManager(asset_root=tmp_path, backend=backend, volume=0.4)

    assert manager.select("rain") is True
    assert manager.start_selected() is True
    assert manager.start_selected() is True
    assert len(backend.started) == 1
    assert backend.started[0] == (tmp_path / "rain.ogg", 0.4)

    manager.pause()
    manager.resume()
    manager.stop()

    assert len(backend.paused) == 1
    assert len(backend.resumed) == 1
    assert len(backend.stopped) == 1
    assert manager.active_name is None
    assert manager.selected_name == "rain"


def test_changing_ambience_volume_does_not_restart_the_active_loop(tmp_path) -> None:
    (tmp_path / "rain.ogg").touch()
    backend = _Backend()
    manager = FocusAmbienceManager(asset_root=tmp_path, backend=backend, volume=0.2)
    manager.select("rain")
    manager.start_selected()

    manager.set_volume(0.7)

    assert backend.started == [(tmp_path / "rain.ogg", 0.2)]
    assert backend.volume_changes == [(backend.started_handles[0], 0.7)]
    assert backend.stopped == []
    assert manager.active_name == "rain"
