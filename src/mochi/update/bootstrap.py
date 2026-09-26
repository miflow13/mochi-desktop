"""Bootstrap Mochi's updater outside the runtime it is about to replace."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable

from .model import UpdateTarget


UPDATER_ASSET_DIRS = ("idle", "wave", "sad_idle", "focus")


def _default_app_home() -> Path:
    data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    return data_home / "mochi-desktop"


def _default_source_package() -> Path:
    return Path(__file__).resolve().parent


def _default_asset_root() -> Path:
    candidates = (
        Path(__file__).resolve().parents[3] / "assets" / "mochi",
        Path(sys.prefix) / "share" / "mochi",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[-1]


def _select_base_python() -> Path:
    base = getattr(sys, "_base_executable", None)
    if base:
        base_path = Path(base)
        if os.access(base_path, os.X_OK):
            return base_path
    return Path("/usr/bin/python3")


def _runner_source() -> str:
    return """from __future__ import annotations

import json
from pathlib import Path

from mochi.update.model import UpdateMetadata, UpdateTarget
from mochi.update.worker import UpdateWorker


request_path = Path(__file__).with_name("request.json")
request = json.loads(request_path.read_text(encoding="utf-8"))
target = UpdateTarget(
    commit=request["commit"],
    metadata=UpdateMetadata(
        version=request["version"],
        channel=request["channel"],
        highlights=tuple(request.get("highlights", ())),
    ),
)
worker = UpdateWorker()
raise SystemExit(
    worker.run(
        target,
        wait_pid=request.get("wait_pid"),
        on_progress=lambda progress: print(
            f"{progress.stage.value}: {progress.message}",
            flush=True,
        ),
    )
)
"""


def bootstrap_updater(
    target: UpdateTarget,
    *,
    gui: bool,
    wait_pid: int | None = None,
    app_home: Path | None = None,
    source_package: Path | None = None,
    asset_root: Path | None = None,
    base_python: Path | None = None,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> subprocess.Popen:
    """Copy the critical updater out of Mochi's active venv and launch it."""

    selected_app_home = Path(app_home) if app_home is not None else _default_app_home()
    selected_source = (
        Path(source_package) if source_package is not None else _default_source_package()
    )
    selected_assets = (
        Path(asset_root) if asset_root is not None else _default_asset_root()
    )
    selected_python = Path(base_python) if base_python is not None else _select_base_python()

    bootstrap_root = selected_app_home / "update-bootstrap"
    bootstrap_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="update-", dir=bootstrap_root))

    try:
        package_root = workspace / "mochi"
        update_destination = package_root / "update"
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        shutil.copytree(selected_source, update_destination)

        copied_asset_root = workspace / "assets" / "mochi"
        copied_asset_root.mkdir(parents=True, exist_ok=True)
        for directory_name in UPDATER_ASSET_DIRS:
            source = selected_assets / directory_name
            destination = copied_asset_root / directory_name
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                destination.mkdir(parents=True, exist_ok=True)

        request = {
            "commit": target.commit,
            "version": target.metadata.version,
            "channel": target.metadata.channel,
            "highlights": list(target.metadata.highlights),
            "wait_pid": wait_pid,
            "gui": bool(gui),
        }
        (workspace / "request.json").write_text(
            json.dumps(request, indent=2) + "\n",
            encoding="utf-8",
        )
        runner = workspace / "runner.py"
        runner.write_text(_runner_source(), encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(workspace)
        env["MOCHI_UPDATER_ASSET_ROOT"] = str(copied_asset_root)
        env["MOCHI_UPDATER_WORKSPACE"] = str(workspace)

        return popen(
            [str(selected_python), str(runner)],
            env=env,
        )
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
