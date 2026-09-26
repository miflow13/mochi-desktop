"""Quiet, exact-commit update discovery for installed Mochi builds."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from urllib.request import Request, urlopen

from mochi.config import ConfigStore

from .constants import OFFICIAL_REPOSITORY
from .model import (
    UpdateCheckResult,
    UpdateMetadata,
    UpdateStatus,
    UpdateTarget,
)
from .storage import InstallMetadataStore


AUTO_CHECK_INTERVAL_SECONDS = 86_400
DEFAULT_NETWORK_TIMEOUT_SECONDS = 3.0


def _default_read_url(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": "Mochi-Desktop-Update-Checker"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


class GitHubUpdateSource:
    def __init__(
        self,
        *,
        read_url: Callable[[str, float], bytes] | None = None,
        timeout_seconds: float = DEFAULT_NETWORK_TIMEOUT_SECONDS,
    ) -> None:
        self._read_url = read_url or _default_read_url
        self._timeout_seconds = float(timeout_seconds)

    def resolve_main_sha(self) -> str:
        url = (
            "https://api.github.com/repos/"
            f"{OFFICIAL_REPOSITORY}/commits/main"
        )
        data = json.loads(
            self._read_url(url, self._timeout_seconds).decode("utf-8")
        )
        if not isinstance(data, dict):
            raise ValueError("GitHub commit response must be an object")
        sha = data.get("sha")
        if not isinstance(sha, str) or not sha.strip():
            raise ValueError("GitHub commit response did not include a SHA")
        return sha.strip()

    def compare_commits(self, installed_commit: str, target_commit: str) -> str:
        installed_commit = str(installed_commit).strip()
        target_commit = str(target_commit).strip()
        if not installed_commit or not target_commit:
            raise ValueError("both installed and target commits are required")

        url = (
            "https://api.github.com/repos/"
            f"{OFFICIAL_REPOSITORY}/compare/{installed_commit}...{target_commit}"
        )
        data = json.loads(
            self._read_url(url, self._timeout_seconds).decode("utf-8")
        )
        if not isinstance(data, dict):
            raise ValueError("GitHub compare response must be an object")

        status = data.get("status")
        if status not in {"identical", "ahead", "behind", "diverged"}:
            raise ValueError("GitHub compare response has an invalid status")
        return status

    def fetch_metadata(self, commit: str) -> UpdateMetadata:
        commit = str(commit).strip()
        if not commit:
            raise ValueError("target commit is required")
        url = (
            "https://raw.githubusercontent.com/"
            f"{OFFICIAL_REPOSITORY}/{commit}/update.json"
        )
        data = json.loads(
            self._read_url(url, self._timeout_seconds).decode("utf-8")
        )
        if not isinstance(data, dict):
            raise ValueError("update metadata root must be an object")

        version = data.get("version")
        channel = data.get("channel")
        highlights = data.get("highlights", ())
        if not isinstance(version, str) or not version.strip():
            raise ValueError("update metadata version is invalid")
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("update metadata channel is invalid")
        if not isinstance(highlights, (list, tuple)):
            raise ValueError("update metadata highlights are invalid")

        return UpdateMetadata(
            version=version.strip(),
            channel=channel.strip(),
            highlights=tuple(str(item) for item in highlights),
        )


class UpdateChecker:
    def __init__(
        self,
        *,
        config: ConfigStore,
        install_store: InstallMetadataStore,
        source: GitHubUpdateSource | object | None = None,
    ) -> None:
        self._config = config
        self._install_store = install_store
        self._source = source or GitHubUpdateSource()

    def check(
        self,
        *,
        manual: bool = False,
        now: float | None = None,
    ) -> UpdateCheckResult:
        checked_at = time.time() if now is None else float(now)

        if not manual and not self._config.load_update_checks_enabled():
            return UpdateCheckResult(
                status=UpdateStatus.CHECK_FAILED,
                error="automatic update checks are disabled",
            )

        if not manual:
            last_check = self._config.load_last_update_check()
            if (
                last_check is not None
                and checked_at - last_check < AUTO_CHECK_INTERVAL_SECONDS
            ):
                return UpdateCheckResult(
                    status=UpdateStatus.CHECK_FAILED,
                    error="automatic update check is not due yet",
                )

        installed = self._install_store.load()
        if installed is None or not installed.commit:
            return UpdateCheckResult(
                status=UpdateStatus.CHECK_FAILED,
                error="installed commit is unknown",
            )

        try:
            target_commit = self._source.resolve_main_sha()
        except Exception as error:
            self._config.save_last_update_check(checked_at)
            return UpdateCheckResult(
                status=UpdateStatus.CHECK_FAILED,
                error=str(error),
            )

        self._config.save_last_update_check(checked_at)

        if target_commit == installed.commit:
            return UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        try:
            relation = self._source.compare_commits(installed.commit, target_commit)
        except Exception as error:
            return UpdateCheckResult(
                status=UpdateStatus.CHECK_FAILED,
                error=str(error),
            )

        if relation != "ahead":
            return UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        try:
            metadata = self._source.fetch_metadata(target_commit)
        except Exception:
            metadata = UpdateMetadata(
                version="latest main",
                channel="main",
                highlights=(),
            )

        target = UpdateTarget(commit=target_commit, metadata=metadata)
        return UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            target=target,
            announce=(
                self._config.load_dismissed_update_commit()
                != target_commit
            ),
        )
