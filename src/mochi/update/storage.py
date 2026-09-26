"""Persistence for the installed Mochi build identity."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .model import InstalledBuild


class InstallMetadataStore:
    def __init__(self, path: Path | None = None) -> None:
        data_home = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
        self.path = path or data_home / "mochi-desktop" / "install.json"

    def load(self) -> InstalledBuild | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None

            version = data["version"]
            commit = data.get("commit")
            channel = data["channel"]
            installed_at = data["installed_at"]

            if not isinstance(version, str) or not version.strip():
                return None
            if commit is not None and (
                not isinstance(commit, str) or not commit.strip()
            ):
                return None
            if not isinstance(channel, str) or not channel.strip():
                return None
            if not isinstance(installed_at, str) or not installed_at.strip():
                return None

            return InstalledBuild(
                version=version,
                commit=commit,
                channel=channel,
                installed_at=installed_at,
            )
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, build: InstalledBuild) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(
                {
                    "version": build.version,
                    "commit": build.commit,
                    "channel": build.channel,
                    "installed_at": build.installed_at,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
