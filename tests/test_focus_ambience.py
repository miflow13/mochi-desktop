"""Lifecycle coverage for optional local focus soundscapes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from mochi.presence.focus_session import FocusWindow
from mochi.sound import FfplayFocusAmbienceBackend, FocusAmbienceManager


class _Backend:
    def __init__(self) -> None:
        self.started: list[tuple[Path, float]] = []
        self.paused: list[object] = []
        self.resumed: list[object] = []
        self.stopped: list[object] = []

    def start(self, path: Path, volume: float) -> object:
        handle = object()
        self.started.append((path, volume))
        return handle

    def pause(self, handle: object) -> None:
        self.paused.append(handle)

    def resume(self, handle: object) -> None:
        self.resumed.append(handle)

    def stop(self, handle: object) -> None:
        self.stopped.append(handle)


def test_ffplay_backend_uses_the_supported_infinite_loop_option(tmp_path) -> None:
    soundscape = tmp_path / "rain.wav"
    soundscape.touch()
    process = Mock()

    with patch("mochi.sound.subprocess.Popen", return_value=process) as popen:
        assert FfplayFocusAmbienceBackend("/usr/bin/ffplay").start(
            soundscape,
            0.4,
        ) is process

    command = popen.call_args.args[0]
    assert command[command.index("-loop") + 1] == "0"
    assert "-stream_loop" not in command


def test_live_volume_drag_is_debounced_before_restarting_audio() -> None:
    window = object.__new__(FocusWindow)
    window._rain_volume = 0.2
    window._rain_volume_source_id = None
    window._on_rain_volume_change = Mock()
    window._sync_rain_controls = Mock()
    scale = Mock()
    scale.get_value.side_effect = (0.3, 0.4, 0.5)

    with patch(
        "mochi.presence.focus_session.GLib.timeout_add",
        side_effect=(71, 72, 73),
    ) as add, patch(
        "mochi.presence.focus_session.GLib.source_remove"
    ) as remove:
        window._handle_rain_volume_changed(scale)
        window._handle_rain_volume_changed(scale)
        window._handle_rain_volume_changed(scale)

    assert window._on_rain_volume_change.call_count == 0
    assert add.call_count == 3
    assert remove.call_count == 2
    assert window._rain_volume_source_id == 73

    assert window._commit_rain_volume_update() == 0
    window._on_rain_volume_change.assert_called_once_with(0.5)
    assert window._rain_volume_source_id is None


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


def test_changing_ambience_volume_restarts_only_the_active_loop(tmp_path) -> None:
    (tmp_path / "rain.ogg").touch()
    backend = _Backend()
    manager = FocusAmbienceManager(asset_root=tmp_path, backend=backend, volume=0.2)
    manager.select("rain")
    manager.start_selected()

    manager.set_volume(0.7)

    assert backend.started == [
        (tmp_path / "rain.ogg", 0.2),
        (tmp_path / "rain.ogg", 0.7),
    ]
    assert len(backend.stopped) == 1
    assert manager.active_name == "rain"
