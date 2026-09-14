"""Load and save Mochi's tiny JSON configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import math
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
        self._reported_errors: set[str] = set()

    def load_position(self) -> Position | None:
        try:
            data = self._load()
            if "x" not in data and "y" not in data:
                return None
            x = self._integer(data["x"])
            y = self._integer(data["y"])
            if not all(-(2**31) <= value < 2**31 for value in (x, y)):
                raise ValueError("position exceeds desktop coordinate range")
            return Position(x=x, y=y)
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError) as error:
            self._report_error("read", error)
            return None

    def save_position(self, position: Position) -> None:
        data = self._load_or_empty()
        data.update({"x": position.x, "y": position.y})
        self._save(data)
        self._logger.debug("Position save requested: %d, %d", position.x, position.y)

    def load_size(self) -> int:
        try:
            size = self._integer(self._load()["size"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
            return self.DEFAULT_SIZE
        return max(self.MIN_SIZE, min(size, self.MAX_SIZE))

    def save_size(self, size: int) -> None:
        size = max(self.MIN_SIZE, min(round(size), self.MAX_SIZE))
        data = self._load_or_empty()
        data["size"] = size
        self._save(data)
        self._logger.debug("Size save requested: %d", size)

    def load_volume(self) -> float:
        try:
            value = self._load()["volume"]
            if isinstance(value, bool):
                raise ValueError("volume must be numeric")
            volume = float(value)
            if not math.isfinite(volume):
                raise ValueError("volume must be finite")
        except (FileNotFoundError, KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
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
        except (FileNotFoundError, KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
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
        except (FileNotFoundError, KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
            return False
        return stay_put if isinstance(stay_put, bool) else False

    def save_stay_put(self, enabled: bool) -> None:
        data = self._load_or_empty()
        data["stay_put"] = bool(enabled)
        self._save(data)
        self._logger.debug("Stay put: %s", bool(enabled))

    def load_edge_roam(self) -> bool:
        """Return whether autonomous wandering should stay on screen edges."""
        try:
            edge_roam = self._load()["edge_roam"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError):
            return False
        return edge_roam if isinstance(edge_roam, bool) else False

    def save_edge_roam(self, enabled: bool) -> None:
        data = self._load_or_empty()
        data["edge_roam"] = bool(enabled)
        self._save(data)
        self._logger.debug("Edge roam: %s", bool(enabled))

    def reset_position(self) -> None:
        data = self._load_or_empty()
        data.pop("x", None)
        data.pop("y", None)
        if data:
            self._save(data)
        else:
            try:
                self.path.unlink(missing_ok=True)
            except OSError as error:
                self._report_error("write", error)

    @staticmethod
    def _integer(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError("expected an integer, not a boolean")
        return int(value)

    def _report_error(self, operation: str, error: Exception) -> None:
        # Saving can happen after each walk. Report an unavailable config once
        # per operation rather than filling logs throughout the session.
        if operation not in self._reported_errors:
            self._reported_errors.add(operation)
            self._logger.warning("Could not %s config %s: %s", operation, self.path, error)

    def _load(self) -> dict[str, object]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("configuration root must be an object")
        except FileNotFoundError:
            return {}
        except (OSError, TypeError, ValueError) as error:
            self._report_error("read", error)
            return {}
        return data

    def _load_or_empty(self) -> dict[str, object]:
        return self._load()

    def _save(self, data: dict[str, object]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            temporary_path.replace(self.path)
        except OSError as error:
            # Persistence must never abort an animation completion/input callback.
            # The previous config remains intact if the atomic replace fails.
            self._report_error("write", error)
