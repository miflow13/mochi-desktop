from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "enable-gnome-helper-once.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _environment(tmp_path: Path, fake_bin: Path) -> dict[str, str]:
    config_home = tmp_path / "config"
    state_home = tmp_path / "state"
    autostart = config_home / "autostart"
    autostart.mkdir(parents=True)
    (autostart / "mochi-enable-gnome-helper-once.desktop").write_text(
        "[Desktop Entry]\nType=Application\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_STATE_HOME": str(state_home),
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
            "MOCHI_HELPER_ENABLE_ATTEMPTS": "1",
            "MOCHI_HELPER_ENABLE_DELAY_SECONDS": "0",
        }
    )
    return env


def test_post_login_helper_enable_removes_autostart_after_verified_success(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "gnome-extensions",
        """#!/usr/bin/env bash
if [[ "$1" == "enable" ]]; then
    exit 0
fi
if [[ "$1" == "info" ]]; then
    printf 'State: ACTIVE\\n'
    exit 0
fi
exit 1
""",
    )
    _write_executable(
        fake_bin / "gdbus",
        """#!/usr/bin/env bash
printf '(true,)\\n'
""",
    )
    env = _environment(tmp_path, fake_bin)

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    autostart = Path(env["XDG_CONFIG_HOME"]) / "autostart" / "mochi-enable-gnome-helper-once.desktop"
    assert not autostart.exists()
    log = Path(env["XDG_STATE_HOME"]) / "mochi" / "gnome-helper-setup.log"
    assert "GNOME helper is active; removed one-time autostart entry." in log.read_text(
        encoding="utf-8"
    )


def test_post_login_helper_enable_keeps_autostart_when_helper_stays_inactive(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "gnome-extensions",
        """#!/usr/bin/env bash
if [[ "$1" == "enable" ]]; then
    exit 1
fi
if [[ "$1" == "info" ]]; then
    printf 'State: INACTIVE\\n'
    exit 0
fi
exit 1
""",
    )
    _write_executable(
        fake_bin / "gdbus",
        """#!/usr/bin/env bash
printf '(false,)\\n'
""",
    )
    env = _environment(tmp_path, fake_bin)

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    autostart = Path(env["XDG_CONFIG_HOME"]) / "autostart" / "mochi-enable-gnome-helper-once.desktop"
    assert autostart.exists()
    log = Path(env["XDG_STATE_HOME"]) / "mochi" / "gnome-helper-setup.log"
    assert "leaving one-time setup scheduled for the next login" in log.read_text(
        encoding="utf-8"
    )
