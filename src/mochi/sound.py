"""Centralized, optional audio playback for Mochi interaction events."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from enum import StrEnum
from typing import Protocol


class AudioBackend(Protocol):
    def play(self, path: Path, volume: float) -> None: ...


class FocusAmbienceBackend(Protocol):
    """Long-running local loop backend, intentionally separate from cues."""

    def start(self, path: Path, volume: float) -> object: ...

    def pause(self, handle: object) -> None: ...

    def resume(self, handle: object) -> None: ...

    def stop(self, handle: object) -> None: ...


class SoundEvent(StrEnum):
    CLICK = "click"
    EAT = "eat"
    PET = "pet"
    PICKUP = "pickup"
    DROP = "drop"
    LEVEL_UP = "level_up"
    SPAWN = "spawn"
    EXIT = "exit"
    MENU_OPEN = "menu_open"


@dataclass(frozen=True)
class CommandAudioBackend:
    """Small process-based backend using an available desktop audio player."""

    executable: str
    kind: str

    def play(self, path: Path, volume: float) -> None:
        if self.kind == "pw-play":
            command = (self.executable, "--volume", str(volume), str(path))
        elif self.kind == "paplay":
            pulse_volume = round(volume * 65_536)
            command = (self.executable, f"--volume={pulse_volume}", str(path))
        else:
            raise ValueError(f"Unsupported audio backend: {self.kind}")
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


@dataclass(frozen=True)
class FfplayFocusAmbienceBackend:
    """Loop one local file with ffplay when an approved backend is available."""

    executable: str

    def start(self, path: Path, volume: float) -> object:
        return subprocess.Popen(
            (
                self.executable,
                "-nodisp",
                "-loglevel",
                "quiet",
                "-stream_loop",
                "-1",
                "-volume",
                str(round(max(0.0, min(volume, 1.0)) * 100)),
                str(path),
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def pause(self, handle: object) -> None:
        if isinstance(handle, subprocess.Popen):
            handle.send_signal(signal.SIGSTOP)

    def resume(self, handle: object) -> None:
        if isinstance(handle, subprocess.Popen):
            handle.send_signal(signal.SIGCONT)

    def stop(self, handle: object) -> None:
        if isinstance(handle, subprocess.Popen) and handle.poll() is None:
            handle.terminate()


class FocusAmbienceManager:
    """Optional local focus soundscape lifecycle, independent from SoundManager.

    No bundled focus assets means this remains dormant until approved `.ogg` or
    `.wav` files are added to ``assets/audio/focus`` (or the installed
    equivalent). The manager intentionally owns at most one long-lived process.
    """

    DEFAULT_VOLUME = 0.35
    SUPPORTED_SUFFIXES = frozenset((".ogg", ".wav"))

    def __init__(
        self,
        *,
        asset_root: Path | None = None,
        backend: FocusAmbienceBackend | None = None,
        volume: float = DEFAULT_VOLUME,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self.asset_root = asset_root or self._find_asset_root()
        self.backend = backend if backend is not None else self._detect_backend()
        self.volume = SoundManager._clamp_volume(volume)
        self._selected_name: str | None = None
        self._active_name: str | None = None
        self._handle: object | None = None
        self._paused = False

    @property
    def available_soundscapes(self) -> tuple[str, ...]:
        if not self.asset_root.is_dir():
            return ()
        return tuple(
            path.stem
            for path in sorted(self.asset_root.iterdir())
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES
        )

    @property
    def selected_name(self) -> str | None:
        return self._selected_name

    @property
    def active_name(self) -> str | None:
        return self._active_name

    @property
    def paused(self) -> bool:
        return self._paused

    def select(self, name: str | None) -> bool:
        """Choose an installed local soundscape without starting playback."""
        if name is None:
            self.stop()
            self._selected_name = None
            return True
        path = self._path_for(name)
        if path is None:
            self._logger.debug("Focus soundscape unavailable: %s", name)
            return False
        self._selected_name = path.stem
        return True

    def start_selected(self) -> bool:
        if self._selected_name is None:
            return False
        return self.start(self._selected_name)

    def start(self, name: str) -> bool:
        path = self._path_for(name)
        if path is None or self.backend is None or self.volume <= 0:
            return False
        if self._active_name == name and self._handle is not None:
            self.resume()
            return True

        self.stop()
        try:
            self._handle = self.backend.start(path, self.volume)
        except OSError as error:
            self._logger.debug("Could not start focus soundscape %s: %s", path, error)
            self._handle = None
            return False
        self._active_name = name
        self._paused = False
        return True

    def pause(self) -> None:
        if self._handle is None or self._paused or self.backend is None:
            return
        try:
            self.backend.pause(self._handle)
        except OSError as error:
            self._logger.debug("Could not pause focus soundscape: %s", error)
            return
        self._paused = True

    def resume(self) -> None:
        if self._handle is None or not self._paused or self.backend is None:
            return
        try:
            self.backend.resume(self._handle)
        except OSError as error:
            self._logger.debug("Could not resume focus soundscape: %s", error)
            return
        self._paused = False

    def stop(self) -> None:
        handle = self._handle
        self._handle = None
        self._active_name = None
        self._paused = False
        if handle is None or self.backend is None:
            return
        try:
            self.backend.stop(handle)
        except OSError as error:
            self._logger.debug("Could not stop focus soundscape: %s", error)

    def set_volume(self, volume: float) -> None:
        self.volume = SoundManager._clamp_volume(volume)
        active_name = self._active_name
        was_paused = self._paused
        if active_name is None:
            return
        # Long-running backends generally cannot adjust gain in place. A
        # user-driven slider change is rare, so restart only here—not on timer
        # ticks—to keep exactly one ambience process alive during focus.
        self.stop()
        if self.start(active_name) and was_paused:
            self.pause()

    def _path_for(self, name: str) -> Path | None:
        candidate = self.asset_root / Path(str(name)).name
        if candidate.suffix:
            if candidate.suffix.lower() not in self.SUPPORTED_SUFFIXES:
                return None
            return candidate if candidate.is_file() else None
        for suffix in self.SUPPORTED_SUFFIXES:
            path = candidate.with_suffix(suffix)
            if path.is_file():
                return path
        return None

    @staticmethod
    def _detect_backend() -> FocusAmbienceBackend | None:
        executable = shutil.which("ffplay")
        return FfplayFocusAmbienceBackend(executable) if executable is not None else None

    @staticmethod
    def _find_asset_root() -> Path:
        audio_root = SoundManager._find_asset_root()
        return audio_root / "focus"


class SoundManager:
    """Maps semantic events to replaceable files and applies global settings."""

    DEFAULT_VOLUME = 0.6
    EVENT_FILES = {
        SoundEvent.CLICK: "mochi_chirp_01.ogg",
        SoundEvent.PET: "pet.wav",
        SoundEvent.EAT: "mochi_eat.wav",
        SoundEvent.PICKUP: "pickup.ogg",
        SoundEvent.DROP: "drop.ogg",
        SoundEvent.LEVEL_UP: "level_up.ogg",
        SoundEvent.SPAWN: "spawn.ogg",
        SoundEvent.EXIT: "exit.ogg",
        SoundEvent.MENU_OPEN: "menu_open.ogg",
    }

    # Keep lifecycle cues quieter than direct interaction sounds.
    EVENT_GAINS = {
        SoundEvent.SPAWN: 0.35,
        SoundEvent.EXIT: 0.28,
        SoundEvent.MENU_OPEN: 0.22,
    }

    def __init__(
        self,
        volume: float = DEFAULT_VOLUME,
        muted: bool = False,
        asset_root: Path | None = None,
        backend: AudioBackend | None = None,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self.asset_root = asset_root or self._find_asset_root()
        self.backend = backend if backend is not None else self._detect_backend()
        self.volume = self._clamp_volume(volume)
        self.muted = bool(muted)
        self._missing_logged: set[SoundEvent] = set()

    def play(self, event: SoundEvent) -> bool:
        filename = self.EVENT_FILES.get(event)
        if filename is None:
            self._logger.warning("Unknown sound event: %s", event)
            return False
        if self.muted or self.volume <= 0:
            return False

        path = self.asset_root / filename
        if not path.is_file():
            if event not in self._missing_logged:
                self._logger.debug("Sound unavailable for %s: %s", event, path)
                self._missing_logged.add(event)
            return False
        if self.backend is None:
            self._logger.debug("No supported audio player found; skipping %s", event)
            return False

        effective_volume = self.volume * self.EVENT_GAINS.get(event, 1.0)
        try:
            self.backend.play(path, effective_volume)
        except OSError as error:
            self._logger.warning("Could not play sound %s: %s", path, error)
            return False
        return True

    def play_level_up(self) -> bool:
        """Public hook for the future progression system."""
        return self.play(SoundEvent.LEVEL_UP)

    def set_volume(self, volume: float) -> None:
        self.volume = self._clamp_volume(volume)

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)

    @staticmethod
    def _clamp_volume(volume: float) -> float:
        return max(0.0, min(float(volume), 1.0))

    @staticmethod
    def _detect_backend() -> AudioBackend | None:
        for executable, kind in (
            ("pw-play", "pw-play"),
            ("paplay", "paplay"),
        ):
            path = shutil.which(executable)
            if path is not None:
                return CommandAudioBackend(path, kind)
        return None

    @staticmethod
    def _find_asset_root() -> Path:
        candidates = (
            Path(__file__).resolve().parents[2] / "assets" / "audio",
            Path(sys.prefix) / "share" / "mochi" / "audio",
        )
        return next((path for path in candidates if path.is_dir()), candidates[0])
