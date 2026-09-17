"""Regression checks for the Fedora installer shell script."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"


def test_installer_shell_syntax_is_valid() -> None:
    subprocess.run(
        ["bash", "-n", str(INSTALLER)],
        check=True,
        cwd=ROOT,
    )


def test_installer_uses_base_python_for_gi_and_private_venv() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert 'getattr(sys, "_base_executable", None) or sys.executable' in text
    assert '"$SYSTEM_PYTHON" - <<\'PY\'' in text
    assert '"$SYSTEM_PYTHON" -m venv --system-site-packages "$VENV"' in text
