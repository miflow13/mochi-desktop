#!/usr/bin/env bash
set -euo pipefail

UUID="mochi-typing@miflow13"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT/gnome-extension/$UUID"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_HOME="$DATA_HOME/mochi-desktop"
AUTOSTART_DIR="$CONFIG_HOME/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/mochi-enable-gnome-helper-once.desktop"
ONE_SHOT_SOURCE="$ROOT/scripts/enable-gnome-helper-once.sh"
ONE_SHOT_INSTALLED="$APP_HOME/enable-gnome-helper-once.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

install_one_time_enable() {
    mkdir -p "$APP_HOME" "$AUTOSTART_DIR"
    install -m 0755 "$ONE_SHOT_SOURCE" "$ONE_SHOT_INSTALLED"
    cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Mochi GNOME Helper Setup
Comment=Finish Mochi's one-time GNOME helper setup
Exec="$ONE_SHOT_INSTALLED"
OnlyShowIn=GNOME;
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
}

clear_one_time_enable() {
    rm -f "$AUTOSTART_FILE" "$ONE_SHOT_INSTALLED"
}

extension_is_active() {
    gnome-extensions info "$UUID" 2>/dev/null | grep -Eq 'State:[[:space:]]+ACTIVE'
}

if ! command -v gnome-extensions >/dev/null 2>&1; then
    echo "gnome-extensions was not found. Install GNOME Shell's extension tools first." >&2
    exit 1
fi

# The source file does not need to carry an executable bit in the checkout.
# install_one_time_enable() deliberately installs it as mode 0755.
if [[ ! -f "$ONE_SHOT_SOURCE" ]]; then
    echo "Missing one-time GNOME helper setup script: $ONE_SHOT_SOURCE" >&2
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
if gnome-extensions enable "$UUID" 2>/dev/null && extension_is_active; then
    clear_one_time_enable
    echo "Enabled $UUID."
else
    install_one_time_enable
    echo "GNOME Shell has not loaded the new extension yet."
    echo "On Wayland, log out and back in once."
    echo "Mochi will automatically enable the helper after your next login."
    echo "No second terminal command is required."
fi

echo "Mochi can launch now; ambient awareness connects when the helper is active."
echo "Check state with:"
echo "  gnome-extensions info $UUID"
