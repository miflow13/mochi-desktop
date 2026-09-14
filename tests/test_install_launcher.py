"""Exercise the installer's launcher replacement without installing the app."""
from pathlib import Path
import subprocess


def test_launcher_replaces_dangling_symlink_and_preserves_arguments(tmp_path):
    installer = (Path(__file__).resolve().parents[1] / 'install.sh').read_text()
    start = installer.index('install_launcher() {')
    function = installer[start:installer.index('\n}\n', start) + 3]
    target = tmp_path / 'target with spaces'
    target.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    target.chmod(0o755)
    launcher = tmp_path / 'mochi'
    launcher.symlink_to(tmp_path / 'removed-venv/bin/mochi')
    subprocess.run(['bash', '-c', function + '\nBIN_DIR="$1"\ninstall_launcher "$2" "$3"',
                    'launcher-test', str(tmp_path), str(launcher), str(target)], check=True)
    assert not launcher.is_symlink()
    result = subprocess.run([str(launcher), 'two words', '--debug'],
                            check=True, capture_output=True, text=True)
    assert result.stdout == 'two words\n--debug\n'
