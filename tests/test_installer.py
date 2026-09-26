"""Behavioral regression checks for the Linux installer."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _link_system_tool(bin_dir: Path, name: str) -> None:
    target = shutil.which(name)
    assert target is not None, f"required test utility is unavailable: {name}"
    (bin_dir / name).symlink_to(target)


def _make_toolbox(
    tmp_path: Path,
    *,
    with_gnome_extensions: bool,
) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    log_dir = tmp_path / "logs"
    bin_dir.mkdir()
    log_dir.mkdir()

    for name in (
        "bash",
        "cat",
        "chmod",
        "cp",
        "date",
        "dirname",
        "grep",
        "install",
        "mkdir",
        "mktemp",
        "mv",
        "rm",
        "sed",
    ):
        _link_system_tool(bin_dir, name)

    _write_executable(
        bin_dir / "rpm",
        """#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$MOCHI_TEST_LOG_DIR/rpm.log"
exit 0
""",
    )
    _write_executable(
        bin_dir / "dnf",
        """#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$MOCHI_TEST_LOG_DIR/dnf.log"
exit 0
""",
    )
    _write_executable(
        bin_dir / "gdbus",
        """#!/bin/bash
printf '(false,)\n'
""",
    )
    _write_executable(
        bin_dir / "glib-compile-schemas",
        """#!/bin/bash
exit 0
""",
    )
    _write_executable(
        bin_dir / "sleep",
        """#!/bin/bash
exit 0
""",
    )
    _write_executable(
        bin_dir / "python3",
        """#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$MOCHI_TEST_LOG_DIR/python.log"

if [[ "$1" == "-" ]]; then
    payload="$(cat)"
    if [[ "$payload" == *'metadata.version("mochi-desktop")'* ]]; then
        printf '0.3.0a1\n'
        exit 0
    fi
    if [[ "$payload" == *"_base_executable"* ]]; then
        printf '%s\n' "$0"
        exit 0
    fi
    if [[ "$payload" == *"from importlib import metadata"* ]]; then
        if [[ "$FAKE_BUILD_TOOLS_READY" == "1" ]]; then
            if [[ "$payload" == *'metadata.version("wheel")'* && "$FAKE_WHEEL_READY" != "1" ]]; then
                exit 1
            fi
            exit 0
        fi
        exit 1
    fi
    exit 0
fi

if [[ "$1" == "-m" && "$2" == "venv" ]]; then
    mkdir -p "$4/bin"
    cp "$0" "$4/bin/python"
    chmod +x "$4/bin/python"
    printf '#!%s/bin/python\nexit 0\n' "$4" > "$4/bin/mochi"
    printf '#!%s/bin/python\nexit 0\n' "$4" > "$4/bin/pip"
    printf 'export VIRTUAL_ENV=%s\n' "$4" > "$4/bin/activate"
    printf 'command = python3 -m venv %s\n' "$4" > "$4/pyvenv.cfg"
    chmod +x "$4/bin/mochi"
    chmod +x "$4/bin/pip"
    exit 0
fi

if [[ "$1" == "-m" && "$2" == "pip" && "$3" == "install" && "$*" == *"--no-deps --no-build-isolation"* ]]; then
    if [[ "$FAKE_PROJECT_INSTALL_TERMINATES" == "1" ]]; then
        kill -TERM "$PPID"
        exit 143
    fi
    if [[ "$FAKE_PROJECT_INSTALL_READY" != "1" ]]; then
        exit 42
    fi
    venv_bin="$(dirname "$0")"
    printf '#!%s\nexit 0\n' "$0" > "$venv_bin/mochi"
    chmod +x "$venv_bin/mochi"
    exit 0
fi

exit 0
""",
    )

    if with_gnome_extensions:
        _write_executable(
            bin_dir / "gnome-extensions",
            """#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$MOCHI_TEST_LOG_DIR/gnome-extensions.log"
case "$1" in
    info)
        printf 'State: ACTIVE\n'
        ;;
    install|enable)
        exit 0
        ;;
esac
exit 0
""",
        )

    return bin_dir, log_dir


def _run_installer(
    tmp_path: Path,
    *,
    current_desktop: str = "",
    session_desktop: str = "",
    desktop_session: str = "",
    with_gnome_extensions: bool = False,
    build_tools_ready: bool = True,
    wheel_ready: bool = True,
    project_install_ready: bool = True,
    project_install_terminates: bool = False,
    existing_venv_marker: str | None = None,
    installer_args: tuple[str, ...] = (),
    installed_commit: str = "test-commit",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir, log_dir = _make_toolbox(
        tmp_path,
        with_gnome_extensions=with_gnome_extensions,
    )
    home = tmp_path / "home"
    home.mkdir()
    if existing_venv_marker is not None:
        venv = home / ".local" / "share" / "mochi-desktop" / "venv"
        venv.mkdir(parents=True)
        (venv / "old-install.marker").write_text(
            existing_venv_marker,
            encoding="utf-8",
        )
        (venv / "bin").mkdir()
        _write_executable(venv / "bin" / "mochi", "#!/bin/bash\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "PATH": str(bin_dir),
            "HOME": str(home),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CURRENT_DESKTOP": current_desktop,
            "XDG_SESSION_DESKTOP": session_desktop,
            "DESKTOP_SESSION": desktop_session,
            "NO_COLOR": "1",
            "MOCHI_TEST_LOG_DIR": str(log_dir),
            "FAKE_BUILD_TOOLS_READY": "1" if build_tools_ready else "0",
            "FAKE_WHEEL_READY": "1" if wheel_ready else "0",
            "FAKE_PROJECT_INSTALL_READY": "1" if project_install_ready else "0",
            "FAKE_PROJECT_INSTALL_TERMINATES": (
                "1" if project_install_terminates else "0"
            ),
            "MOCHI_INSTALLED_COMMIT": installed_commit,
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(INSTALLER), *installer_args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, log_dir


def _read_log(log_dir: Path, name: str) -> str:
    path = log_dir / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_installer_shell_syntax_is_valid() -> None:
    subprocess.run(
        ["bash", "-n", str(INSTALLER)],
        check=True,
        cwd=ROOT,
    )


@pytest.mark.parametrize(
    ("current_desktop", "session_desktop"),
    [
        ("gnome", ""),
        ("", "GNOME"),
    ],
)
def test_gnome_detection_installs_gnome_dependency_and_helper(
    tmp_path: Path,
    current_desktop: str,
    session_desktop: str,
) -> None:
    result, log_dir = _run_installer(
        tmp_path,
        current_desktop=current_desktop,
        session_desktop=session_desktop,
        with_gnome_extensions=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gnome-shell" in _read_log(log_dir, "rpm.log")
    helper_log = _read_log(log_dir, "gnome-extensions.log")
    assert "install --force" in helper_log
    assert "enable mochi-typing@miflow13" in helper_log
    assert "GNOME desktop awareness is active" in result.stdout


def test_non_gnome_desktop_skips_gnome_dependency_and_helper(tmp_path: Path) -> None:
    result, log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        session_desktop="niri",
        with_gnome_extensions=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gnome-shell" not in _read_log(log_dir, "rpm.log")
    assert not (log_dir / "gnome-extensions.log").exists()
    output = result.stdout + result.stderr
    assert "Skipping GNOME helper" in output
    assert "Non-GNOME desktop detected" in output


def test_gnome_without_extension_tooling_degrades_without_logout_advice(
    tmp_path: Path,
) -> None:
    result, log_dir = _run_installer(
        tmp_path,
        current_desktop="GNOME",
        with_gnome_extensions=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gnome-shell" in _read_log(log_dir, "rpm.log")
    output = result.stdout + result.stderr
    assert "skipping Mochi's optional awareness helper" in output
    assert "GNOME desktop-awareness helper is unavailable" in output
    assert "LOG OUT OF GNOME" not in output


def test_installer_reuses_compatible_private_venv_build_tools(tmp_path: Path) -> None:
    result, log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        build_tools_ready=True,
        wheel_ready=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    python_log = _read_log(log_dir, "python.log")
    assert "-m venv --system-site-packages" in python_log
    assert "-m pip install setuptools>=69" not in python_log
    assert "-m pip install --no-deps --no-build-isolation" in python_log
    assert "Python build tooling is already available" in result.stdout


def test_installer_bootstraps_missing_private_venv_build_tools(tmp_path: Path) -> None:
    result, log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        build_tools_ready=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    python_log = _read_log(log_dir, "python.log")
    assert "-m venv --system-site-packages" in python_log
    assert "-m pip install setuptools>=69" in python_log
    assert "Installing Python build tooling" in result.stdout


def test_installer_preserves_transactional_private_venv_replacement() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "trap rollback_private_venv EXIT" in text
    assert '"$SYSTEM_PYTHON" -m venv --system-site-packages "$VENV"' in text
    assert 'if ! ensure_python_build_tools "$VENV/bin/python"; then' in text
    assert 'if ! "$VENV/bin/python" -m pip install --no-deps --no-build-isolation "$ROOT"; then' in text

    backup_move = 'mv "$VENV" "$BACKUP_VENV"'
    create_venv = '"$SYSTEM_PYTHON" -m venv --system-site-packages "$VENV"'
    restore_move = 'mv "$BACKUP_VENV" "$VENV"'
    cleanup_failed_replacement = 'rm -rf "$VENV"'

    assert backup_move in text
    assert restore_move in text
    assert cleanup_failed_replacement in text

    backup_index = text.index(backup_move)
    create_index = text.index(create_venv)
    install_index = text.index(
        'if ! "$VENV/bin/python" -m pip install --no-deps --no-build-isolation "$ROOT"; then'
    )

    assert backup_index < create_index < install_index
    assert text.index(cleanup_failed_replacement) < backup_index
    assert text.index(restore_move) < backup_index


def test_installer_console_script_uses_final_venv_path(tmp_path: Path) -> None:
    result, _log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    venv = tmp_path / "home" / ".local" / "share" / "mochi-desktop" / "venv"
    console_script = venv / "bin" / "mochi"
    first_line = console_script.read_text(encoding="utf-8").splitlines()[0]

    assert "venv.new." not in first_line
    assert first_line == f"#!{venv / 'bin' / 'python'}"


def test_installer_virtual_environment_has_no_temporary_path_references(
    tmp_path: Path,
) -> None:
    result, _log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    venv = tmp_path / "home" / ".local" / "share" / "mochi-desktop" / "venv"
    for relative_path in ("bin/mochi", "bin/pip", "bin/activate", "pyvenv.cfg"):
        text = (venv / relative_path).read_text(encoding="utf-8")
        assert "venv.new." not in text, relative_path
        assert str(venv) in text, relative_path


@pytest.mark.parametrize("existing_venv_marker", [None, "working-old-install"])
def test_project_install_failure_restores_or_removes_environment(
    tmp_path: Path,
    existing_venv_marker: str | None,
) -> None:
    result, _log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        project_install_ready=False,
        existing_venv_marker=existing_venv_marker,
    )

    assert result.returncode != 0
    app_home = tmp_path / "home" / ".local" / "share" / "mochi-desktop"
    venv = app_home / "venv"
    if existing_venv_marker is None:
        assert not venv.exists()
    else:
        assert (venv / "old-install.marker").read_text(encoding="utf-8") == existing_venv_marker
    assert not tuple(app_home.glob("venv.backup.*"))
    assert not tuple(app_home.glob("venv.new.*"))



def test_normal_install_writes_installed_build_metadata(tmp_path: Path) -> None:
    result, _log_dir = _run_installer(tmp_path, current_desktop="niri")

    assert result.returncode == 0, result.stdout + result.stderr
    install_json = (
        tmp_path
        / "home"
        / ".local"
        / "share"
        / "mochi-desktop"
        / "install.json"
    )
    data = __import__("json").loads(install_json.read_text(encoding="utf-8"))
    assert data["version"] == "0.3.0a1"
    assert data["commit"] == "test-commit"
    assert data["channel"] == "main"
    assert data["installed_at"]


def test_stage_runtime_builds_candidate_without_touching_current_install(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    candidate = home / ".local" / "share" / "mochi-desktop" / "venv.update"

    result, log_dir = _run_installer(
        tmp_path,
        current_desktop="GNOME",
        with_gnome_extensions=True,
        existing_venv_marker="working-old-install",
        installer_args=("--stage-runtime", str(candidate)),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    final_venv = home / ".local" / "share" / "mochi-desktop" / "venv"
    assert (final_venv / "old-install.marker").read_text(encoding="utf-8") == (
        "working-old-install"
    )
    assert (candidate / "bin" / "mochi").exists()
    assert not (home / ".local" / "bin" / "mochi").exists()
    assert not (
        home
        / ".local"
        / "share"
        / "applications"
        / "io.github.mochi_desktop.Mochi.desktop"
    ).exists()
    assert not (log_dir / "gnome-extensions.log").exists()
    assert not (
        home / ".local" / "share" / "mochi-desktop" / "install.json"
    ).exists()


def test_stage_runtime_failure_preserves_current_install(tmp_path: Path) -> None:
    home = tmp_path / "home"
    candidate = home / ".local" / "share" / "mochi-desktop" / "venv.update"

    result, _log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        existing_venv_marker="working-old-install",
        project_install_ready=False,
        installer_args=("--stage-runtime", str(candidate)),
    )

    assert result.returncode != 0
    final_venv = home / ".local" / "share" / "mochi-desktop" / "venv"
    assert (final_venv / "old-install.marker").read_text(encoding="utf-8") == (
        "working-old-install"
    )
    assert not candidate.exists()


def test_refresh_integrations_reuses_final_runtime_without_rebuilding(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"

    result, log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        existing_venv_marker="working-old-install",
        installer_args=("--refresh-integrations",),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    python_log = _read_log(log_dir, "python.log")
    assert "-m venv" not in python_log
    assert "-m pip install --no-deps --no-build-isolation" not in python_log

    launcher = home / ".local" / "bin" / "mochi"
    launcher_text = launcher.read_text(encoding="utf-8")
    final_mochi = (
        home
        / ".local"
        / "share"
        / "mochi-desktop"
        / "venv"
        / "bin"
        / "mochi"
    )
    assert str(final_mochi) in launcher_text
    assert not (
        home / ".local" / "share" / "mochi-desktop" / "install.json"
    ).exists()

def test_abnormal_exit_restores_previous_environment(tmp_path: Path) -> None:
    result, _log_dir = _run_installer(
        tmp_path,
        current_desktop="niri",
        project_install_terminates=True,
        existing_venv_marker="working-old-install",
    )

    assert result.returncode != 0
    app_home = tmp_path / "home" / ".local" / "share" / "mochi-desktop"
    venv = app_home / "venv"
    assert (venv / "old-install.marker").read_text(encoding="utf-8") == "working-old-install"
    assert not tuple(app_home.glob("venv.backup.*"))
    assert not tuple(app_home.glob("venv.new.*"))
