"""Transactional exact-commit updater used by the external Mochi updater."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
from collections.abc import Callable
from urllib.request import Request, urlopen

from .checker import OFFICIAL_REPOSITORY
from .model import InstalledBuild, UpdateTarget
from .storage import InstallMetadataStore


READY_TIMEOUT_SECONDS = 10.0


class UpdateStage(Enum):
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    SWAPPING = "swapping"
    REFRESHING = "refreshing"
    RESTARTING = "restarting"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class UpdateProgress:
    stage: UpdateStage
    message: str
    downloaded: int | None = None
    total: int | None = None


@dataclass(frozen=True)
class UpdatePaths:
    app_home: Path
    final_venv: Path
    update_venv: Path
    backup_venv: Path
    temp_root: Path
    ready_file: Path

    @classmethod
    def for_environment(
        cls,
        *,
        data_home: Path | None = None,
        temp_root: Path | None = None,
    ) -> "UpdatePaths":
        if data_home is None:
            data_home = Path(
                os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
            )
        app_home = Path(data_home) / "mochi-desktop"
        selected_temp_root = Path(temp_root) if temp_root is not None else app_home / "updates"
        app_home.mkdir(parents=True, exist_ok=True)
        selected_temp_root.mkdir(parents=True, exist_ok=True)
        return cls(
            app_home=app_home,
            final_venv=app_home / "venv",
            update_venv=app_home / "venv.update",
            backup_venv=app_home / "venv.backup",
            temp_root=selected_temp_root,
            ready_file=app_home / "update-ready",
        )


def _default_download(
    url: str,
    destination: Path,
    on_bytes: Callable[[int, int | None], None],
) -> None:
    request = Request(url, headers={"User-Agent": "Mochi-Desktop-Updater"})
    with urlopen(request, timeout=20) as response:  # noqa: S310
        total_header = response.headers.get("Content-Length")
        total = int(total_header) if total_header and total_header.isdigit() else None
        downloaded = 0
        with destination.open("wb") as output:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                on_bytes(downloaded, total)


def _default_run_command(args, *, cwd=None, env=None):
    return subprocess.run(
        [str(value) for value in args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _default_launch_command(args, *, env=None):
    return subprocess.Popen(
        [str(value) for value in args],
        env=env,
        start_new_session=True,
    )


def _default_wait_for_pid(pid: int) -> None:
    if pid <= 0:
        return
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        time.sleep(0.1)


def _default_wait_for_ready(path: Path, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.1)
    return path.exists()


def _default_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UpdateWorker:
    def __init__(
        self,
        *,
        paths: UpdatePaths | None = None,
        install_store: InstallMetadataStore | None = None,
        download_archive: Callable[[str, Path, Callable[[int, int | None], None]], None]
        | None = None,
        run_command: Callable[..., object] | None = None,
        launch_command: Callable[..., object] | None = None,
        wait_for_pid: Callable[[int], None] | None = None,
        wait_for_ready: Callable[[Path, float], bool] | None = None,
        now_iso: Callable[[], str] | None = None,
    ) -> None:
        self.paths = paths or UpdatePaths.for_environment()
        self._install_store = install_store or InstallMetadataStore(
            self.paths.app_home / "install.json"
        )
        self._download_archive = download_archive or _default_download
        self._run_command = run_command or _default_run_command
        self._launch_command = launch_command or _default_launch_command
        self._wait_for_pid = wait_for_pid or _default_wait_for_pid
        self._wait_for_ready = wait_for_ready or _default_wait_for_ready
        self._now_iso = now_iso or _default_now_iso

    def run(
        self,
        target: UpdateTarget,
        *,
        wait_pid: int | None,
        on_progress: Callable[[UpdateProgress], None],
    ) -> int:
        workspace = Path(tempfile.mkdtemp(prefix="mochi-update-", dir=self.paths.temp_root))
        archive_path = workspace / "source.tar.gz"
        extracted_path = workspace / "source"
        swapped = False
        failure_code = 1

        try:
            self._recover_stale_paths()

            url = (
                f"https://codeload.github.com/{OFFICIAL_REPOSITORY}/tar.gz/"
                f"{target.commit}"
            )
            on_progress(UpdateProgress(UpdateStage.DOWNLOADING, "Getting the newest Mochi…"))

            def report_bytes(downloaded: int, total: int | None) -> None:
                on_progress(
                    UpdateProgress(
                        UpdateStage.DOWNLOADING,
                        "Getting the newest Mochi…",
                        downloaded=downloaded,
                        total=total,
                    )
                )

            self._download_archive(url, archive_path, report_bytes)

            on_progress(UpdateProgress(UpdateStage.VERIFYING, "Verifying update…"))
            source_root = self._extract_and_validate_source(archive_path, extracted_path)

            on_progress(UpdateProgress(UpdateStage.INSTALLING, "Installing Mochi…"))
            env = os.environ.copy()
            env["MOCHI_INSTALLED_COMMIT"] = target.commit
            stage = self._run_command(
                [
                    source_root / "install.sh",
                    "--stage-runtime",
                    self.paths.update_venv,
                ],
                cwd=source_root,
                env=env,
            )
            if getattr(stage, "returncode", 1) != 0:
                failure_code = int(getattr(stage, "returncode", 1) or 1)
                return failure_code

            installed_version = self._validate_candidate()

            if wait_pid is not None:
                self._wait_for_pid(wait_pid)

            on_progress(UpdateProgress(UpdateStage.SWAPPING, "Finishing update…"))
            if not self.paths.final_venv.exists():
                raise RuntimeError("current Mochi runtime is missing before swap")
            if self.paths.backup_venv.exists():
                shutil.rmtree(self.paths.backup_venv)
            self.paths.final_venv.rename(self.paths.backup_venv)
            self.paths.update_venv.rename(self.paths.final_venv)
            swapped = True

            on_progress(
                UpdateProgress(UpdateStage.REFRESHING, "Refreshing desktop integration…")
            )
            refresh = self._run_command(
                [source_root / "install.sh", "--refresh-integrations"],
                cwd=source_root,
                env=env,
            )
            if getattr(refresh, "returncode", 1) != 0:
                failure_code = int(getattr(refresh, "returncode", 1) or 1)
                self._rollback_and_relaunch()
                swapped = False
                return failure_code

            self.paths.ready_file.unlink(missing_ok=True)
            on_progress(UpdateProgress(UpdateStage.RESTARTING, "Restarting Mochi…"))
            self._launch_command(
                [
                    self.paths.final_venv / "bin" / "mochi",
                    "--update-ready-file",
                    self.paths.ready_file,
                ],
                env=os.environ.copy(),
            )

            if not self._wait_for_ready(self.paths.ready_file, READY_TIMEOUT_SECONDS):
                self._rollback_and_relaunch()
                swapped = False
                return 1

            self._install_store.save(
                InstalledBuild(
                    version=installed_version,
                    commit=target.commit,
                    channel=target.metadata.channel,
                    installed_at=self._now_iso(),
                )
            )
            if self.paths.backup_venv.exists():
                shutil.rmtree(self.paths.backup_venv)
            swapped = False
            on_progress(UpdateProgress(UpdateStage.SUCCESS, "All updated!"))
            return 0
        except Exception as error:
            if swapped:
                try:
                    self._rollback_and_relaunch()
                    swapped = False
                except Exception:
                    pass
            on_progress(UpdateProgress(UpdateStage.FAILED, str(error)))
            return failure_code
        finally:
            self.paths.ready_file.unlink(missing_ok=True)
            if self.paths.update_venv.exists():
                shutil.rmtree(self.paths.update_venv, ignore_errors=True)
            shutil.rmtree(workspace, ignore_errors=True)

    def _recover_stale_paths(self) -> None:
        if self.paths.update_venv.exists():
            shutil.rmtree(self.paths.update_venv, ignore_errors=True)

        if not self.paths.final_venv.exists() and self.paths.backup_venv.exists():
            self.paths.backup_venv.rename(self.paths.final_venv)
        elif self.paths.final_venv.exists() and self.paths.backup_venv.exists():
            shutil.rmtree(self.paths.backup_venv, ignore_errors=True)

    def _extract_and_validate_source(
        self,
        archive_path: Path,
        destination: Path,
    ) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        destination_root = destination.resolve()

        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise ValueError("update archive is empty")

            for member in members:
                if member.issym() or member.islnk():
                    raise ValueError("update archive contains a link")
                member_path = (destination / member.name).resolve()
                if member_path != destination_root and destination_root not in member_path.parents:
                    raise ValueError("update archive contains an unsafe path")

            archive.extractall(destination, members=members)  # noqa: S202

        roots = [path for path in destination.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise ValueError("update archive must contain one repository root")
        source_root = roots[0]

        required = (
            source_root / "pyproject.toml",
            source_root / "install.sh",
            source_root / "src" / "mochi",
            source_root / "assets" / "mochi",
        )
        if not all(path.exists() for path in required):
            raise ValueError("update archive is missing required Mochi files")
        return source_root

    def _validate_candidate(self) -> str:
        python = self.paths.update_venv / "bin" / "python"
        mochi = self.paths.update_venv / "bin" / "mochi"
        manifest = self.paths.update_venv / "share" / "mochi" / "manifest.json"
        default_art = (
            self.paths.update_venv
            / "share"
            / "mochi"
            / "master"
            / "mochi_default.png"
        )

        for executable in (python, mochi):
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise RuntimeError(f"candidate executable is missing: {executable}")
        for asset in (manifest, default_art):
            if not asset.exists():
                raise RuntimeError(f"candidate runtime asset is missing: {asset}")

        result = self._run_command(
            [
                python,
                "-c",
                (
                    "from importlib import metadata; "
                    "import mochi; "
                    "print(metadata.version('mochi-desktop'))"
                ),
            ],
            cwd=None,
            env=os.environ.copy(),
        )
        if getattr(result, "returncode", 1) != 0:
            raise RuntimeError("candidate Mochi import/version check failed")
        version = str(getattr(result, "stdout", "")).strip().splitlines()
        if not version or not version[-1].strip():
            raise RuntimeError("candidate Mochi version is unavailable")
        return version[-1].strip()

    def _rollback_and_relaunch(self) -> None:
        if self.paths.final_venv.exists():
            shutil.rmtree(self.paths.final_venv, ignore_errors=True)
        if not self.paths.backup_venv.exists():
            raise RuntimeError("previous Mochi runtime is unavailable for rollback")
        self.paths.backup_venv.rename(self.paths.final_venv)
        self._launch_command(
            [self.paths.final_venv / "bin" / "mochi"],
            env=os.environ.copy(),
        )
