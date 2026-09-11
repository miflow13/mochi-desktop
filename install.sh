#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="io.github.mochi_desktop.Mochi"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_HOME="$DATA_HOME/mochi-desktop"
VENV="$APP_HOME/venv"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/mochi"
UNINSTALL_LAUNCHER="$BIN_DIR/mochi-uninstall"
INSTALLED_UNINSTALLER="$APP_HOME/uninstall.sh"
APPLICATIONS_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/$APP_ID.desktop"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/$APP_ID.png"
DESKTOP_TEMPLATE="$ROOT/packaging/$APP_ID.desktop.in"
ICON_SOURCE="$ROOT/assets/mochi/master/mochi_default.png"

log() {
    printf '\n🌱 %s\n' "$1"
}

warn() {
    printf '\n⚠ %s\n' "$1" >&2
}

if [[ ! -f "$ROOT/pyproject.toml" || ! -f "$DESKTOP_TEMPLATE" ]]; then
    echo "Run install.sh from a complete Mochi repository checkout." >&2
    exit 1
fi

if command -v dnf >/dev/null 2>&1 && command -v rpm >/dev/null 2>&1; then
    packages=(
        python3
        python3-pip
        python3-setuptools
        python3-wheel
        python3-gobject
        python3-cairo
        gtk4
        libX11
        xorg-x11-server-Xwayland
        pipewire-utils
        glib2
        gnome-shell
    )
    missing=()
    for package in "${packages[@]}"; do
        if ! rpm -q "$package" >/dev/null 2>&1; then
            missing+=("$package")
        fi
    done

    if ((${#missing[@]})); then
        log "Installing Fedora dependencies"
        sudo dnf install -y "${missing[@]}"
    else
        log "Fedora dependencies already installed"
    fi
else
    warn "Automatic dependency installation currently supports Fedora only."
    warn "Continuing with the packages already available on this system."
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to install Mochi." >&2
    exit 1
fi

log "Checking GTK4 / PyGObject"
python3 - <<'PY'
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: F401

print("GTK4 / PyGObject OK")
PY

log "Installing Mochi into $APP_HOME"
mkdir -p "$APP_HOME" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"
rm -rf "$VENV"
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/python" -m pip install --no-deps --no-build-isolation "$ROOT"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/mochi" "\$@"
EOF
chmod 0755 "$LAUNCHER"

install -m 0755 "$ROOT/uninstall.sh" "$INSTALLED_UNINSTALLER"
cat > "$UNINSTALL_LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$INSTALLED_UNINSTALLER" "\$@"
EOF
chmod 0755 "$UNINSTALL_LAUNCHER"

install -m 0644 "$ICON_SOURCE" "$ICON_FILE"
sed "s|@MOCHI_EXEC@|$LAUNCHER|g" "$DESKTOP_TEMPLATE" > "$DESKTOP_FILE"
chmod 0644 "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

log "Installing Mochi's GNOME helper"
if [[ -x "$ROOT/scripts/install-typing-extension.sh" ]]; then
    "$ROOT/scripts/install-typing-extension.sh"
else
    bash "$ROOT/scripts/install-typing-extension.sh"
fi

log "Installation complete"
printf '%s\n' \
    "Open Mochi from the GNOME app grid, or run: $LAUNCHER" \
    "Right-click Mochi and choose Close to close him." \
    "Uninstall later with: $UNINSTALL_LAUNCHER" \
    "" \
    "If the GNOME helper reported that it could not enable yet, log out and" \
    "back in once before testing typing/context awareness."
