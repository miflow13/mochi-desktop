"""Update discovery and exact-target regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from mochi.config import ConfigStore
from mochi.update.checker import (
    AUTO_CHECK_INTERVAL_SECONDS,
    GitHubUpdateSource,
    UpdateChecker,
)
from mochi.update.model import InstalledBuild, UpdateMetadata, UpdateStatus
from mochi.update.storage import InstallMetadataStore


class _FakeSource:
    def __init__(
        self,
        *,
        sha: str = "new-sha",
        metadata: UpdateMetadata | None = None,
        resolve_error: Exception | None = None,
        metadata_error: Exception | None = None,
        relation: str = "ahead",
        compare_error: Exception | None = None,
    ) -> None:
        self.sha = sha
        self.metadata = metadata or UpdateMetadata(
            version="0.4.0a1",
            channel="main",
            highlights=("one", "two"),
        )
        self.resolve_error = resolve_error
        self.metadata_error = metadata_error
        self.relation = relation
        self.compare_error = compare_error
        self.calls: list[object] = []

    def resolve_main_sha(self) -> str:
        self.calls.append("resolve")
        if self.resolve_error is not None:
            raise self.resolve_error
        return self.sha

    def compare_commits(self, installed_commit: str, target_commit: str) -> str:
        self.calls.append(("compare", installed_commit, target_commit))
        if self.compare_error is not None:
            raise self.compare_error
        return self.relation

    def fetch_metadata(self, commit: str) -> UpdateMetadata:
        self.calls.append(("metadata", commit))
        if self.metadata_error is not None:
            raise self.metadata_error
        return self.metadata


def _checker(
    tmp_path: Path,
    *,
    installed_commit: str | None = "old-sha",
    source: _FakeSource | None = None,
) -> tuple[UpdateChecker, ConfigStore, _FakeSource]:
    config = ConfigStore(tmp_path / "config.json")
    install_store = InstallMetadataStore(tmp_path / "install.json")
    if installed_commit is not None:
        install_store.save(
            InstalledBuild(
                version="0.3.0a1",
                commit=installed_commit,
                channel="main",
                installed_at="2026-09-26T12:00:00+00:00",
            )
        )
    fake_source = source or _FakeSource()
    return (
        UpdateChecker(config=config, install_store=install_store, source=fake_source),
        config,
        fake_source,
    )


def test_same_commit_is_up_to_date_without_fetching_metadata(tmp_path: Path) -> None:
    source = _FakeSource(sha="same-sha")
    checker, _config, source = _checker(
        tmp_path, installed_commit="same-sha", source=source
    )

    result = checker.check(manual=True, now=1_000.0)

    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.target is None
    assert source.calls == ["resolve"]


def test_new_commit_returns_exact_target_and_metadata(tmp_path: Path) -> None:
    checker, _config, source = _checker(tmp_path)

    result = checker.check(manual=True, now=1_000.0)

    assert result.status is UpdateStatus.UPDATE_AVAILABLE
    assert result.target is not None
    assert result.target.commit == "new-sha"
    assert result.target.metadata.version == "0.4.0a1"
    assert result.announce is True
    assert source.calls == [
        "resolve",
        ("compare", "old-sha", "new-sha"),
        ("metadata", "new-sha"),
    ]


def test_automatic_check_inside_24_hour_cooldown_does_not_touch_network(
    tmp_path: Path,
) -> None:
    checker, config, source = _checker(tmp_path)
    config.save_last_update_check(500.0)

    result = checker.check(
        manual=False,
        now=500.0 + AUTO_CHECK_INTERVAL_SECONDS - 1,
    )

    assert result.status is UpdateStatus.CHECK_FAILED
    assert source.calls == []


def test_manual_check_bypasses_automatic_cooldown(tmp_path: Path) -> None:
    checker, config, source = _checker(tmp_path)
    config.save_last_update_check(500.0)

    result = checker.check(manual=True, now=501.0)

    assert result.status is UpdateStatus.UPDATE_AVAILABLE
    assert source.calls[0] == "resolve"


def test_resolve_network_failure_is_safe_and_records_check_time(tmp_path: Path) -> None:
    source = _FakeSource(resolve_error=TimeoutError("offline"))
    checker, config, _source = _checker(tmp_path, source=source)

    result = checker.check(manual=False, now=1_234.5)

    assert result.status is UpdateStatus.CHECK_FAILED
    assert "offline" in (result.error or "")
    assert config.load_last_update_check() == 1_234.5


def test_unknown_installed_commit_never_claims_update_available(tmp_path: Path) -> None:
    checker, _config, source = _checker(tmp_path, installed_commit=None)

    result = checker.check(manual=True, now=1_000.0)

    assert result.status is UpdateStatus.CHECK_FAILED
    assert result.target is None
    assert source.calls == []


def test_main_behind_feature_build_is_not_offered_as_an_update(tmp_path: Path) -> None:
    source = _FakeSource(sha="main-sha", relation="behind")
    checker, _config, source = _checker(
        tmp_path,
        installed_commit="feature-sha",
        source=source,
    )

    result = checker.check(manual=True, now=1_000.0)

    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.target is None
    assert source.calls == [
        "resolve",
        ("compare", "feature-sha", "main-sha"),
    ]


def test_diverged_build_is_not_offered_main_as_an_update(tmp_path: Path) -> None:
    source = _FakeSource(sha="main-sha", relation="diverged")
    checker, _config, source = _checker(
        tmp_path,
        installed_commit="branch-sha",
        source=source,
    )

    result = checker.check(manual=True, now=1_000.0)

    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.target is None
    assert source.calls == [
        "resolve",
        ("compare", "branch-sha", "main-sha"),
    ]


def test_bad_metadata_falls_back_without_losing_known_target(tmp_path: Path) -> None:
    source = _FakeSource(metadata_error=ValueError("bad metadata"))
    checker, _config, _source = _checker(tmp_path, source=source)

    result = checker.check(manual=True, now=1_000.0)

    assert result.status is UpdateStatus.UPDATE_AVAILABLE
    assert result.target is not None
    assert result.target.commit == "new-sha"
    assert result.target.metadata.channel == "main"
    assert result.target.metadata.highlights == ()


def test_dismissed_commit_is_not_reannounced_but_newer_commit_is(tmp_path: Path) -> None:
    checker, config, _source = _checker(tmp_path)
    config.save_dismissed_update_commit("new-sha")

    dismissed = checker.check(manual=True, now=1_000.0)
    assert dismissed.status is UpdateStatus.UPDATE_AVAILABLE
    assert dismissed.announce is False

    newer_source = _FakeSource(sha="newer-sha")
    checker = UpdateChecker(
        config=config,
        install_store=InstallMetadataStore(tmp_path / "install.json"),
        source=newer_source,
    )
    newer = checker.check(manual=True, now=2_000.0)

    assert newer.status is UpdateStatus.UPDATE_AVAILABLE
    assert newer.target is not None
    assert newer.target.commit == "newer-sha"
    assert newer.announce is True


def test_github_source_pins_metadata_to_resolved_commit() -> None:
    calls: list[tuple[str, float]] = []

    def read_url(url: str, timeout: float) -> bytes:
        calls.append((url, timeout))
        if url.endswith("/commits/main"):
            return json.dumps({"sha": "abc123"}).encode()
        if url.endswith("/compare/old123...abc123"):
            return json.dumps({"status": "ahead"}).encode()
        if url.endswith("/abc123/update.json"):
            return json.dumps(
                {
                    "version": "0.4.0a1",
                    "channel": "main",
                    "highlights": ["one", "two", "three", "four"],
                }
            ).encode()
        raise AssertionError(url)

    source = GitHubUpdateSource(read_url=read_url, timeout_seconds=2.5)

    commit = source.resolve_main_sha()
    relation = source.compare_commits("old123", commit)
    metadata = source.fetch_metadata(commit)

    assert commit == "abc123"
    assert relation == "ahead"
    assert metadata.highlights == ("one", "two", "three")
    assert calls == [
        (
            "https://api.github.com/repos/miflow13/mochi-desktop/commits/main",
            2.5,
        ),
        (
            "https://api.github.com/repos/miflow13/mochi-desktop/compare/old123...abc123",
            2.5,
        ),
        (
            "https://raw.githubusercontent.com/miflow13/mochi-desktop/abc123/update.json",
            2.5,
        ),
    ]
