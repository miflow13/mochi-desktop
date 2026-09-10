#!/usr/bin/env bash
set -euo pipefail

UUID="mochi-typing@miflow13"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT/gnome-extension/$UUID"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if ! command -v gnome-extensions >/dev/null 2>&1; then
    echo "gnome-extensions was not found. Install GNOME Shell's extension tools first." >&2
    exit 1
fi

(
    cd "$SOURCE_DIR"
    python3 - "$TMP_DIR/$UUID.shell-extension.zip" <<'PY'
from pathlib import Path
import sys
import zipfile

output = Path(sys.argv[1])
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in ("metadata.json", "extension.js", "README.md"):
        archive.write(name, name)
PY
)

gnome-extensions install --force "$TMP_DIR/$UUID.shell-extension.zip"

echo "Installed $UUID."
if gnome-extensions enable "$UUID" 2>/dev/null; then
    echo "Enabled $UUID."
else
    echo "GNOME Shell has not loaded the new extension yet."
    echo "On Wayland, log out and back in once, then run:"
    echo "  gnome-extensions enable $UUID"
fi

echo "Check state with:"
echo "  gnome-extensions info $UUID"
