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

STAGE_DIR="$TMP_DIR/$UUID"
mkdir -p "$STAGE_DIR/schemas"
cp "$SOURCE_DIR/metadata.json" "$SOURCE_DIR/extension.js" "$SOURCE_DIR/README.md" "$STAGE_DIR/"
cp "$SOURCE_DIR"/schemas/*.xml "$STAGE_DIR/schemas/"

if ! command -v glib-compile-schemas >/dev/null 2>&1; then
    echo "glib-compile-schemas was not found." >&2
    exit 1
fi
glib-compile-schemas "$STAGE_DIR/schemas"

python3 - "$STAGE_DIR" "$TMP_DIR/$UUID.shell-extension.zip" <<'PY'
from pathlib import Path
import sys
import zipfile

source = Path(sys.argv[1])
output = Path(sys.argv[2])
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        archive.write(path, path.relative_to(source))
PY

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
