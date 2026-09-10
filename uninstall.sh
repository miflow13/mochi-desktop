#!/usr/bin/env bash
set -euo pipefail

APP_ID="io.github.mochi_desktop.Mochi"
EXTENSION_UUID="mochi-typing@miflow13"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_HOME="$DATA_HOME/mochi-desktop"
LAUNCHER="$HOME/.local/bin/mochi"
UNINSTALL_LAUNCHER="$HOME/.local/bin/mochi-uninstall"
DESKTOP_FILE="$DATA_HOME/applications/$APP_ID.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png"
EXTENSION_DIR="$DATA_HOME/gnome-shell/extensions/$EXTENSION_UUID"
PURGE=false

if [[ "${1:-}" == "--purge" ]]; then
    PURGE=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: mochi-uninstall [--purge]" >&2
    exit 2
fi

printf '\n🌱 Removing Mochi\n'

if command -v pgrep >/dev/null 2>&1 && command -v pkill >/dev/null 2>&1; then
    if pgrep -u "$USER" -f "$APP_HOME/venv/bin/mochi" >/dev/null 2>&1; then
        pkill -u "$USER" -f "$APP_HOME/venv/bin/mochi" || true
    fi
fi

if command -v gnome-extensions >/dev/null 2>&1; then
    gnome-extensions disable "$EXTENSION_UUID" >/dev/null 2>&1 || true
fi

rm -f "$LAUNCHER" "$UNINSTALL_LAUNCHER" "$DESKTOP_FILE" "$ICON_FILE"
rm -rf "$EXTENSION_DIR"

if $PURGE; then
    rm -rf "$CONFIG_HOME/mochi"
    echo "Mochi and saved settings were removed."
else
    echo "Mochi was removed. Saved settings were kept in $CONFIG_HOME/mochi."
    echo "Reinstall later to keep using them, or delete $CONFIG_HOME/mochi to reset Mochi."
fi

# Remove this installed script and its private environment last. The shell has
# already read the running script, so deleting APP_HOME here is safe.
rm -rf "$APP_HOME"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
fi

if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi
