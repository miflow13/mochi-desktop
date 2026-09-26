"""Transactional updater and rollback regression coverage."""

from __future__ import annotations

import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import threading

from mochi.update.model import InstalledBuild, UpdateMetadata, UpdateTarget
from mochi.update.storage import InstallMetadataStore
from mochi.update.worker import (
    READY_TIMEOUT_SECONDS,
    UpdatePaths,
    UpdateStage,
    UpdateWorker,
)


def _target(commit: str = "abc123") -> UpdateTarget:
    return UpdateTarget(
        commit=commit,
        metadata=UpdateMetadata(
            version="0.4.0a1",
            channel="main",
            highlights=("new tricks",),
        ),
    )


def _make_source_archive(path: Path, *, unsafe: bool = False) -> None:
    with tarfile.open(path, "w:gz") as archive:
        if unsafe:
            info = tarfile.TarInfo("../../escaped.txt")
            payload = b"nope"
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
            return

        root = "mochi-desktop-abc123"
        files = {
            f"{root}/pyproject.toml": b"[project]\nname='mochi-desktop'\n",
            f"{root}/install.sh": b"#!/bin/bash\nexit 0\n",
            f"{root}/src/mochi/__init__.py": b"",
            f"{root}/assets/mochi/manifest.json": b"{}\n",
        }
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o755 if name.endswith("install.sh") else 0o644
            archive.addfile(info, io.BytesIO(payload))


class _Harness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        stage_returncode: int = 0,
        refresh_returncode: int = 0,
        ready: bool = True,
    ) -> None:
        self.archive = tmp_path / "source.tar.gz"
        _make_source_archive(self.archive)
        self.stage_returncode = stage_returncode
        self.refresh_returncode = refresh_returncode
        self.ready = ready
        self.download_urls: list[str] = []
        self.commands: list[tuple[str, ...]] = []
        self.launches: list[tuple[str, ...]] = []
        self.waited_pids: list[int] = []
        self.ready_timeouts: list[float] = []

    def download(self, url: str, destination: Path, on_bytes) -> None:
        self.download_urls.append(url)
        shutil.copy2(self.archive, destination)
        size = destination.stat().st_size
        on_bytes(size, size)

    def run_command(self, args, *, cwd=None, env=None):
        argv = tuple(str(value) for value in args)
        self.commands.append(argv)

        if "--stage-runtime" in argv:
            target = Path(argv[argv.index("--stage-runtime") + 1])
            if self.stage_returncode == 0:
                (target / "bin").mkdir(parents=True, exist_ok=True)
                for name in ("python", "mochi"):
                    path = target / "bin" / name
                    path.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
                    path.chmod(0o755)
                (target / "share" / "mochi" / "master").mkdir(
                    parents=True, exist_ok=True
                )
                (target / "share" / "mochi" / "manifest.json").write_text(
                    "{}\n", encoding="utf-8"
                )
                (target / "share" / "mochi" / "master" / "mochi_default.png").touch()
            return subprocess.CompletedProcess(
                list(argv), self.stage_returncode, stdout="", stderr=""
            )

        if "--refresh-integrations" in argv:
            return subprocess.CompletedProcess(
                list(argv), self.refresh_returncode, stdout="", stderr=""
            )

        # Candidate validation commands.
        return subprocess.CompletedProcess(list(argv), 0, stdout="0.4.0a1\n", stderr="")

    def launch(self, args, *, env=None):
        argv = tuple(str(value) for value in args)
        self.launches.append(argv)
        return object()

    def wait_for_pid(self, pid: int) -> None:
        self.waited_pids.append(pid)

    def wait_for_ready(self, path: Path, timeout_seconds: float) -> bool:
        self.ready_timeouts.append(timeout_seconds)
        if self.ready:
            path.write_text("ready\n", encoding="utf-8")
        return self.ready


def _paths(tmp_path: Path) -> UpdatePaths:
    app_home = tmp_path / "data" / "mochi-desktop"
    final = app_home / "venv"
    (final / "bin").mkdir(parents=True)
    old_mochi = final / "bin" / "mochi"
    old_mochi.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    old_mochi.chmod(0o755)
    (final / "old.marker").write_text("old", encoding="utf-8")
    return UpdatePaths.for_environment(
        data_home=tmp_path / "data",
        temp_root=tmp_path / "work",
    )


def _worker(
    tmp_path: Path,
    harness: _Harness,
    paths: UpdatePaths,
) -> tuple[UpdateWorker, InstallMetadataStore]:
    store = InstallMetadataStore(paths.app_home / "install.json")
    return (
        UpdateWorker(
            paths=paths,
            install_store=store,
            download_archive=harness.download,
            run_command=harness.run_command,
            launch_command=harness.launch,
            wait_for_pid=harness.wait_for_pid,
            wait_for_ready=harness.wait_for_ready,
            now_iso=lambda: "2026-09-26T13:00:00+00:00",
        ),
        store,
    )


def test_update_download_is_pinned_to_exact_target_sha(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target("deadbeef"), wait_pid=None, on_progress=lambda _p: None) == 0

    assert harness.download_urls == [
        "https://codeload.github.com/miflow13/mochi-desktop/tar.gz/deadbeef"
    ]
    assert not any("/commits/main" in url for url in harness.download_urls)


def test_unsafe_archive_is_rejected_before_install(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path)
    _make_source_archive(harness.archive, unsafe=True)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=None, on_progress=lambda _p: None) != 0

    assert harness.commands == []
    assert (paths.final_venv / "old.marker").read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "escaped.txt").exists()


def test_stage_failure_leaves_current_runtime_untouched(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path, stage_returncode=42)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=None, on_progress=lambda _p: None) == 42

    assert (paths.final_venv / "old.marker").read_text(encoding="utf-8") == "old"
    assert not paths.update_venv.exists()
    assert not paths.backup_venv.exists()


def test_worker_waits_for_running_mochi_only_after_candidate_is_staged(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path)
    events: list[UpdateStage] = []
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=4321, on_progress=lambda p: events.append(p.stage)) == 0

    assert harness.waited_pids == [4321]
    assert UpdateStage.INSTALLING in events
    assert UpdateStage.SWAPPING in events
    assert events.index(UpdateStage.INSTALLING) < events.index(UpdateStage.SWAPPING)


def test_successful_swap_waits_for_readiness_then_removes_backup_and_records_target(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path, ready=True)
    worker, store = _worker(tmp_path, harness, paths)

    assert worker.run(_target("good-sha"), wait_pid=123, on_progress=lambda _p: None) == 0

    assert not paths.backup_venv.exists()
    assert not paths.update_venv.exists()
    assert not (paths.final_venv / "old.marker").exists()
    build = store.load()
    assert build == InstalledBuild(
        version="0.4.0a1",
        commit="good-sha",
        channel="main",
        installed_at="2026-09-26T13:00:00+00:00",
    )
    assert harness.ready_timeouts == [READY_TIMEOUT_SECONDS]
    assert any("--update-ready-file" in launch for launch in harness.launches)


def test_refresh_failure_rolls_back_previous_runtime(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path, refresh_returncode=9)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=None, on_progress=lambda _p: None) == 9

    assert (paths.final_venv / "old.marker").read_text(encoding="utf-8") == "old"
    assert not paths.backup_venv.exists()
    assert harness.launches[-1][0].endswith("/venv/bin/mochi")


def test_readiness_timeout_restores_previous_runtime_and_relaunches_it(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path, ready=False)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=None, on_progress=lambda _p: None) != 0

    assert (paths.final_venv / "old.marker").read_text(encoding="utf-8") == "old"
    assert not paths.backup_venv.exists()
    assert harness.ready_timeouts == [READY_TIMEOUT_SECONDS]
    assert harness.launches[-1][0].endswith("/venv/bin/mochi")


def test_stale_backup_restores_when_final_runtime_is_missing(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    shutil.rmtree(paths.final_venv)
    (paths.backup_venv / "bin").mkdir(parents=True)
    (paths.backup_venv / "old.marker").write_text("recovered", encoding="utf-8")
    old_mochi = paths.backup_venv / "bin" / "mochi"
    old_mochi.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    old_mochi.chmod(0o755)

    harness = _Harness(tmp_path)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=None, on_progress=lambda _p: None) == 0

    assert not paths.backup_venv.exists()
    assert not paths.update_venv.exists()


def test_failure_cleans_temp_workspace_and_ready_file(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path, stage_returncode=3)
    worker, _store = _worker(tmp_path, harness, paths)

    assert worker.run(_target(), wait_pid=None, on_progress=lambda _p: None) == 3

    assert not paths.ready_file.exists()
    assert not paths.update_venv.exists()
    assert paths.temp_root.exists()
    assert list(paths.temp_root.iterdir()) == []


def test_cancel_before_swap_keeps_current_runtime_and_skips_install(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    harness = _Harness(tmp_path)
    worker, _store = _worker(tmp_path, harness, paths)
    cancel = threading.Event()
    cancel.set()

    result = worker.run(
        _target(),
        wait_pid=None,
        on_progress=lambda _p: None,
        cancel_event=cancel,
    )

    assert result == 130
    assert (paths.final_venv / "old.marker").read_text(encoding="utf-8") == "old"
    assert harness.commands == []
    assert not paths.backup_venv.exists()
