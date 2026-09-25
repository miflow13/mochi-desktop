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
    assert 'if ! TMP_VENV="$(mktemp -d "$APP_HOME/venv.new.XXXXXX")"; then' in text
    assert '"$SYSTEM_PYTHON" -m venv --system-site-packages "$TMP_VENV"' in text
    assert 'if ! "$SYSTEM_PYTHON" -m venv --system-site-packages "$TMP_VENV"; then' in text
    assert 'if ! "$TMP_VENV/bin/python" -m pip install "setuptools>=69" wheel; then' in text
    assert 'if ! "$TMP_VENV/bin/python" -m pip install --no-deps --no-build-isolation "$ROOT"; then' in text
    backup_move = 'mv "$VENV" "$BACKUP_VENV"'
    replacement_move = 'mv "$TMP_VENV" "$VENV"'
    restore_move = 'if ! mv "$BACKUP_VENV" "$VENV"; then'
    cleanup_failed_replacement = 'rm -rf "$VENV"'
    cleanup_failed_tmp = 'rm -rf "$TMP_VENV"'
    assert backup_move in text
    assert replacement_move in text
    assert restore_move in text
    assert cleanup_failed_replacement in text
    assert cleanup_failed_tmp in text
    replacement_index = text.index(replacement_move)
    cleanup_failed_replacement_index = text.index(cleanup_failed_replacement, replacement_index)
    cleanup_failed_tmp_index = text.index(cleanup_failed_tmp, replacement_index)
    restore_index = text.index(restore_move, replacement_index)

    assert text.index(backup_move) < replacement_index
    assert replacement_index < cleanup_failed_replacement_index
    assert cleanup_failed_replacement_index < cleanup_failed_tmp_index
    assert replacement_index < restore_index
