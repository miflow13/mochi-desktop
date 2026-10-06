"""Load and save Mochi's tiny JSON configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from mochi.care import BondState
from mochi.pocket_hover import DEFAULT_POCKET_HOVER_DELAY_MS, normalize_hover_delay_ms
from mochi.update.constants import DEFAULT_UPDATE_CHANNEL, UPDATE_CHANNELS


@dataclass(frozen=True)
class Position:
    x: int
    y: int


class ConfigStore:
    DEFAULT_SIZE = 112
    MIN_SIZE = 64
    MAX_SIZE = 256
    SIZE_STEP = 16
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

    def load_edge_roam(self) -> bool:
        """Return whether autonomous wandering should stay on screen edges."""
        try:
            edge_roam = self._load()["edge_roam"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return edge_roam if isinstance(edge_roam, bool) else False

    def save_edge_roam(self, enabled: bool) -> None:
        data = self._load_or_empty()
        data["edge_roam"] = bool(enabled)
        self._save(data)
        self._logger.debug("Edge roam: %s", bool(enabled))

    def load_pocket_hover_delay_ms(self) -> int:
        """Return how long resting on Mochi takes to open Pocket; 0 is off."""
        try:
            value = self._load()["pocket_hover_delay_ms"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return DEFAULT_POCKET_HOVER_DELAY_MS
        return normalize_hover_delay_ms(value)

    def save_pocket_hover_delay_ms(self, delay_ms: int) -> None:
        data = self._load_or_empty()
        data["pocket_hover_delay_ms"] = normalize_hover_delay_ms(delay_ms)
        self._save(data)
        self._logger.debug("Pocket hover delay: %s ms", data["pocket_hover_delay_ms"])

    def load_update_checks_enabled(self) -> bool:
        try:
            enabled = self._load()["update_checks_enabled"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return True
        return enabled if isinstance(enabled, bool) else True

    def save_update_checks_enabled(self, enabled: bool) -> None:
        data = self._load_or_empty()
        data["update_checks_enabled"] = bool(enabled)
        self._save(data)

    def load_update_channel(self) -> str:
        try:
            channel = self._load()["update_channel"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return DEFAULT_UPDATE_CHANNEL
        return channel if channel in UPDATE_CHANNELS else DEFAULT_UPDATE_CHANNEL

    def save_update_channel(self, channel: str) -> None:
        if channel not in UPDATE_CHANNELS:
            raise ValueError(f"unknown update channel: {channel!r}")
        data = self._load_or_empty()
        data["update_channel"] = channel
        self._save(data)

    def load_last_update_check(self) -> float | None:
        try:
            value = self._load()["last_update_check"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    def save_last_update_check(self, timestamp: float) -> None:
        data = self._load_or_empty()
        data["last_update_check"] = float(timestamp)
        self._save(data)

    def load_dismissed_update_commit(self) -> str | None:
        try:
            value = self._load()["dismissed_update_commit"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    def save_dismissed_update_commit(self, commit: str | None) -> None:
        data = self._load_or_empty()
        if commit is None or not str(commit).strip():
            data.pop("dismissed_update_commit", None)
        else:
            data["dismissed_update_commit"] = str(commit).strip()
        self._save(data)

    def load_bond_state(self) -> BondState:
        """Return Mochi's persisted, non-decaying bond progress."""
        try:
            data = self._load()
        except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
            return BondState()

        if "bond_xp" in data:
            return BondState(
                level=data.get("bond_level", 1),
                xp=data.get("bond_xp", 0),
            )

        # Migrate the earlier four-step care preview proportionally into the
        # smooth XP bar so local testers do not lose relationship progress.
        if "bond_points" in data or "bond_phases" in data:
            try:
                level = max(1, int(data.get("bond_level", 1)))
            except (TypeError, ValueError):
                level = 1
            raw_steps = data.get("bond_points", data.get("bond_phases", 0))
            try:
                steps = max(0, min(4, int(raw_steps)))
            except (TypeError, ValueError):
                steps = 0
            base = BondState(level=level)
            migrated_xp = round(base.xp_required * (steps / 4))
            return BondState(level=level, xp=migrated_xp)

        return BondState()

    def save_bond_state(self, state: BondState) -> None:
        """Persist bond level/XP without storing animation state."""
        normalized = BondState(level=state.level, xp=state.xp)
        data = self._load_or_empty()
        data["bond_level"] = normalized.level
        data["bond_xp"] = normalized.xp
        data.pop("bond_points", None)
        data.pop("bond_phases", None)
        self._save(data)
        self._logger.debug(
            "Bond saved: level=%d progress=%d/%d XP",
            normalized.level,
            normalized.xp,
            normalized.xp_required,
        )

    def has_started_before(self) -> bool:
        """Whether Mochi has completed at least one non-preview startup."""
        try:
            started = self._load()["has_started_before"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return started if isinstance(started, bool) else False

    def mark_started(self) -> None:
        """Persist the first-launch boundary without retaining session events."""
        data = self._load_or_empty()
        data["has_started_before"] = True
        self._save(data)

    def has_seen_intro(self) -> bool:
        """Only a successfully displayed introduction counts as seen."""
        try:
            return self._load().get("has_seen_intro") is True
        except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
            return False

    def mark_intro_seen(self) -> None:
        data = self._load_or_empty()
        data["has_seen_intro"] = True
        self._save(data)

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
        except (TypeError, ValueError) as error:
            self._preserve_corrupt_config(error)

    def _load(self) -> dict[str, object]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("configuration root must be an object")
        return data

    def _load_or_empty(self) -> dict[str, object]:
        try:
            return self._load()
        except FileNotFoundError:
            return {}
        except (TypeError, ValueError) as error:
            self._preserve_corrupt_config(error)
            return {}

    def _preserve_corrupt_config(self, error: Exception) -> None:
        """Move unreadable JSON aside before a caller replaces the config."""
        backup_path = self.path.with_name(
            f"{self.path.name}.corrupt-{uuid4().hex}"
        )
        while backup_path.exists():
            backup_path = self.path.with_name(
                f"{self.path.name}.corrupt-{uuid4().hex}"
            )
        try:
            self.path.replace(backup_path)
        except FileNotFoundError:
            return
        self._logger.warning(
            "Invalid config %s preserved as %s: %s",
            self.path,
            backup_path,
            error,
        )

    def _save(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        temporary_path.replace(self.path)
