"""Load and save Mochi's tiny JSON configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path


@dataclass(frozen=True)
class Position:
    x: int
    y: int


class ConfigStore:
    DEFAULT_SIZE = 128
    MIN_SIZE = 64
    MAX_SIZE = 256
    DEFAULT_VOLUME = 0.6

    def __init__(self, path: Path | None = None) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.path = path or config_home / "mochi" / "config.json"
        self._logger = logging.getLogger(__name__)

    def load_position(self) -> Position | None:
        try:
            data = self._load()
            if "x" not in data and "y" not in data:
                return None
            return Position(x=int(data["x"]), y=int(data["y"]))
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._logger.warning("Ignoring invalid config %s: %s", self.path, error)
            return None

    def save_position(self, position: Position) -> None:
        data = self._load_or_empty()
        data.update({"x": position.x, "y": position.y})
        self._save(data)
        self._logger.debug("Position saved: %d, %d", position.x, position.y)

    def load_size(self) -> int:
        try:
            size = int(self._load()["size"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return self.DEFAULT_SIZE
        return max(self.MIN_SIZE, min(size, self.MAX_SIZE))

    def save_size(self, size: int) -> None:
        size = max(self.MIN_SIZE, min(round(size), self.MAX_SIZE))
        data = self._load_or_empty()
        data["size"] = size
        self._save(data)
        self._logger.debug("Size saved: %d", size)

    def load_volume(self) -> float:
        try:
            volume = float(self._load()["volume"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return self.DEFAULT_VOLUME
        return max(0.0, min(volume, 1.0))

    def save_volume(self, volume: float) -> None:
        volume = max(0.0, min(float(volume), 1.0))
        data = self._load_or_empty()
        data["volume"] = volume
        self._save(data)
        self._logger.debug("Volume saved: %.0f%%", volume * 100)

    def load_muted(self) -> bool:
        try:
            muted = self._load()["muted"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return muted if isinstance(muted, bool) else False

    def save_muted(self, muted: bool) -> None:
        data = self._load_or_empty()
        data["muted"] = bool(muted)
        self._save(data)
        self._logger.debug("Audio muted: %s", bool(muted))

    def load_stay_put(self) -> bool:
        """Return whether autonomous walking is disabled."""
        try:
            stay_put = self._load()["stay_put"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return stay_put if isinstance(stay_put, bool) else False

    def save_stay_put(self, enabled: bool) -> None:
        data = self._load_or_empty()
        data["stay_put"] = bool(enabled)
        self._save(data)
        self._logger.debug("Stay put: %s", bool(enabled))

    def reset_position(self) -> None:
        try:
            data = self._load()
            data.pop("x", None)
            data.pop("y", None)
            if data:
                self._save(data)
            else:
                self.path.unlink()
            self._logger.info("Saved Mochi position reset")
        except FileNotFoundError:
            pass
        except (TypeError, ValueError, json.JSONDecodeError):
            self.path.unlink(missing_ok=True)

    def _load(self) -> dict[str, object]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("configuration root must be an object")
        return data

    def _load_or_empty(self) -> dict[str, object]:
        try:
            return self._load()
        except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        temporary_path.replace(self.path)
