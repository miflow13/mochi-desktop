#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="io.github.mochi_desktop.Mochi"
HELPER_UUID="mochi-typing@miflow13"
HELPER_BUS_NAME="io.github.mochi_desktop.Mochi.TypingMonitor"
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

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    BOLD=$'\033[1m'
    DIM=$'\033[2m'
    GREEN=$'\033[38;5;114m'
    YELLOW=$'\033[38;5;221m'
    CYAN=$'\033[38;5;117m'
    RESET=$'\033[0m'
else
    BOLD=""
    DIM=""
    GREEN=""
    YELLOW=""
    CYAN=""
    RESET=""
fi

banner() {
    printf '\n%s%s' "$GREEN" "$BOLD"
    cat <<'EOF'
        🌱
     Mochi
  Linux desktop buddy
EOF
    printf '%s\n' "$RESET"
}

step() {
    printf '\n%s🌱 %s%s\n' "$GREEN" "$1" "$RESET"
}

ok() {
    printf '%s✓%s %s\n' "$GREEN" "$RESET" "$1"
}

warn() {
    printf '%s⚠%s %s\n' "$YELLOW" "$RESET" "$1" >&2
}

helper_is_active() {
    local result=""

    if command -v gdbus >/dev/null 2>&1; then
        result="$(
            gdbus call --session \
                --dest org.freedesktop.DBus \
                --object-path /org/freedesktop/DBus \
                --method org.freedesktop.DBus.NameHasOwner \
                "$HELPER_BUS_NAME" 2>/dev/null || true
        )"
        if [[ "$result" == *"true"* ]]; then
            return 0
        fi
    fi

    if command -v gnome-extensions >/dev/null 2>&1; then
        if gnome-extensions info "$HELPER_UUID" 2>/dev/null | grep -Eq 'State:[[:space:]]+ACTIVE'; then
            return 0
        fi
    fi

    return 1
}

show_gnome_reload_notice() {
    printf '\n%s%s' "$YELLOW" "$BOLD"
    cat <<'EOF'
╭──────────────────────────────────────────────────────────────╮
│  ⚠  ONE-TIME GNOME SETUP REQUIRED                           │
╰──────────────────────────────────────────────────────────────╯
EOF
    printf '%s' "$RESET"
    cat <<'EOF'

Mochi is installed, but GNOME has not loaded Mochi's desktop-awareness
helper in this login session yet.

LOG OUT OF GNOME, THEN LOG BACK IN ONCE.

Until you do, Mochi can still run, but these features may be limited:
  • typing reactions
  • application/context awareness
  • file-browsing reactions
  • focused YouTube/media awareness

You do not need to reinstall Mochi.
After you log back in, just launch Mochi normally. Ambient awareness will
connect automatically when the GNOME helper becomes active.
EOF
}

show_ready_notice() {
    printf '\n%s%s✓ Mochi is ready.%s\n' "$GREEN" "$BOLD" "$RESET"
    printf '%sGNOME desktop awareness is active in this session.%s\n' "$DIM" "$RESET"
}

install_launcher() {
    local destination="$1"
    local target="$2"
    local temporary

    # Redirection follows an existing symlink. A launcher left by an older
    # install can therefore point into a removed virtual environment and make
    # `cat > ~/.local/bin/mochi` fail with "No such file or directory".
    # Write beside it, then rename over any file or dangling symlink.
    temporary="$(mktemp "$BIN_DIR/.mochi-launcher.XXXXXX")"
    cat > "$temporary" <<EOF
#!/usr/bin/env bash
exec "$target" "\$@"
EOF
    chmod 0755 "$temporary"
    mv -f "$temporary" "$destination"
}

banner

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
        gtk4-layer-shell
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
        step "Installing Fedora dependencies"
        sudo dnf install -y "${missing[@]}"
    else
        step "Checking Fedora dependencies"
        ok "Required Fedora packages are already installed"
    fi
else
    warn "Automatic dependency installation currently supports Fedora only."
    warn "Continuing with the packages already available on this system."
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to install Mochi." >&2
    exit 1
fi

step "Checking GTK4 / PyGObject"
python3 - <<'PY'
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: F401

print("✓ GTK4 / PyGObject OK")
PY

step "Installing Mochi"
printf '%sTarget:%s %s\n' "$DIM" "$RESET" "$APP_HOME"
mkdir -p "$APP_HOME" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"
rm -rf "$VENV"
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/python" -m pip install --no-deps --no-build-isolation "$ROOT"

install_launcher "$LAUNCHER" "$VENV/bin/mochi"

install -m 0755 "$ROOT/uninstall.sh" "$INSTALLED_UNINSTALLER"
install_launcher "$UNINSTALL_LAUNCHER" "$INSTALLED_UNINSTALLER"

install -m 0644 "$ICON_SOURCE" "$ICON_FILE"
sed "s|@MOCHI_EXEC@|$LAUNCHER|g" "$DESKTOP_TEMPLATE" > "$DESKTOP_FILE"
chmod 0644 "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

step "Installing Mochi's GNOME helper"
if [[ -x "$ROOT/scripts/install-typing-extension.sh" ]]; then
    "$ROOT/scripts/install-typing-extension.sh"
else
    bash "$ROOT/scripts/install-typing-extension.sh"
fi

# Give an extension that enabled immediately a moment to claim its D-Bus name.
sleep 0.25

step "Installation complete"
printf '%sLaunch:%s      %s\n' "$CYAN" "$RESET" "$LAUNCHER"
printf '%sApplication:%s GNOME app grid → Mochi\n' "$CYAN" "$RESET"
printf '%sUninstall:%s   %s\n' "$CYAN" "$RESET" "$UNINSTALL_LAUNCHER"

if helper_is_active; then
    show_ready_notice
elif [[ "${XDG_CURRENT_DESKTOP:-}" == *GNOME* || "${DESKTOP_SESSION:-}" == *gnome* ]]; then
    show_gnome_reload_notice
else
    printf '\n'
    warn "GNOME desktop-awareness helper is not active in this session."
    printf 'On GNOME Wayland, a one-time logout/login may be required after installation.\n'
fi

printf '\n%sMochi will also remind you above the character if GNOME setup is still pending.%s\n\n' "$DIM" "$RESET"
