"""Tests for Mochi updater identity and installed-build persistence."""

from __future__ import annotations

import json
from pathlib import Path

from mochi.update.model import InstalledBuild, UpdateMetadata
from mochi.update.storage import InstallMetadataStore


def test_update_metadata_keeps_at_most_three_non_empty_highlights() -> None:
    metadata = UpdateMetadata(
        version="0.4.0a1",
        channel="main",
        highlights=(" first ", "", "second", "third", "fourth"),
    )

    assert metadata.highlights == ("first", "second", "third")


def test_install_metadata_store_missing_and_malformed_return_none(tmp_path: Path) -> None:
    path = tmp_path / "install.json"
    store = InstallMetadataStore(path)

    assert store.load() is None

    path.write_text("not json\n", encoding="utf-8")
    assert store.load() is None

    path.write_text('{"version": 3}\n', encoding="utf-8")
    assert store.load() is None


def test_install_metadata_store_round_trips_build_identity_atomically(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested" / "install.json"
    store = InstallMetadataStore(path)
    build = InstalledBuild(
        version="0.3.0a1",
        commit="97b770344aad2314967ea014c698305e54820a5f",
        channel="main",
        installed_at="2026-09-26T12:00:00+00:00",
    )

    store.save(build)

    assert store.load() == build
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": build.version,
        "commit": build.commit,
        "channel": build.channel,
        "installed_at": build.installed_at,
    }
    assert not path.with_suffix(".tmp").exists()
