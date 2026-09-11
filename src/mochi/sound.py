"""Centralized, optional audio playback for Mochi interaction events."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
import subprocess
import sys
from enum import StrEnum
from typing import Protocol


class AudioBackend(Protocol):
    def play(self, path: Path, volume: float) -> None: ...


class SoundEvent(StrEnum):
    CLICK = "click"
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


class SoundManager:
    """Maps semantic events to replaceable files and applies global settings."""

    DEFAULT_VOLUME = 0.6
    EVENT_FILES = {
        SoundEvent.CLICK: "mochi_chirp_01.ogg",
        SoundEvent.PET: "pet.wav",
        SoundEvent.PICKUP: "pickup.ogg",
        SoundEvent.DROP: "drop.ogg",
        SoundEvent.LEVEL_UP: "level_up.ogg",
        SoundEvent.SPAWN: "spawn.ogg",
        SoundEvent.EXIT: "exit.ogg",
        SoundEvent.MENU_OPEN: "menu_open.ogg",
    }
    FEDORA_CLICK_FILES = (
        "mochi_chirp_01.ogg",
        "mochi_chirp_fedora_02.ogg",
        "mochi_chirp_fedora_03.ogg",
        "mochi_chirp_fedora_04.ogg",
        "mochi_chirp_fedora_05.ogg",
        "mochi_chirp_fedora_06.ogg",
    )

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
        return self._play_filename(event, filename)

    def play_fedora_click(self, position: int) -> bool:
        """Play one of six authored click pitches for the Fedora easter egg."""
        index = max(1, min(int(position), len(self.FEDORA_CLICK_FILES))) - 1
        filename = self.FEDORA_CLICK_FILES[index]
        path = self.asset_root / filename
        if not path.is_file() and filename != self.EVENT_FILES[SoundEvent.CLICK]:
            # Installed builds from before the easter egg should still click.
            return self.play(SoundEvent.CLICK)
        return self._play_filename(SoundEvent.CLICK, filename)

    def _play_filename(self, event: SoundEvent, filename: str) -> bool:
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
