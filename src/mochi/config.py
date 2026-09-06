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
    def __init__(self, path: Path | None = None) -> None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.path = path or config_home / "mochi" / "config.json"
        self._logger = logging.getLogger(__name__)

    def load_position(self) -> Position | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Position(x=int(data["x"]), y=int(data["y"]))
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._logger.warning("Ignoring invalid config %s: %s", self.path, error)
            return None

    def save_position(self, position: Position) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps({"x": position.x, "y": position.y}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
        self._logger.debug("Position saved: %d, %d", position.x, position.y)

    def reset_position(self) -> None:
        try:
            self.path.unlink()
            self._logger.info("Saved Mochi position reset")
        except FileNotFoundError:
            pass
