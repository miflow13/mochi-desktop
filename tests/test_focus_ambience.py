"""Lifecycle coverage for optional local focus soundscapes."""

from __future__ import annotations

from pathlib import Path

from mochi.sound import FocusAmbienceManager


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
