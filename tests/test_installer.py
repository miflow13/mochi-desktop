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
    if [[ "$payload" == *"_base_executable"* ]]; then
        printf '%s\n' "$0"
        exit 0
    fi
    if [[ "$payload" == *"metadata.version(\"setuptools\")"* ]]; then
        if [[ "$FAKE_BUILD_TOOLS_READY" == "1" ]]; then
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
    printf '#!/bin/bash\nexit 0\n' > "$4/bin/mochi"
    chmod +x "$4/bin/mochi"
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
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir, log_dir = _make_toolbox(
        tmp_path,
        with_gnome_extensions=with_gnome_extensions,
    )
    home = tmp_path / "home"
    home.mkdir()

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
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(INSTALLER)],
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
    )

    assert result.returncode == 0, result.stdout + result.stderr
    python_log = _read_log(log_dir, "python.log")
    assert "-m venv --system-site-packages" in python_log
    assert "-m pip install setuptools>=69 wheel" not in python_log
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
    assert "-m pip install setuptools>=69 wheel" in python_log
    assert "Installing Python build tooling" in result.stdout
