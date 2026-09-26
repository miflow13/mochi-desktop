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
INSTALL_METADATA="$APP_HOME/install.json"

INSTALL_MODE="full"
if (($#)); then
    case "$1" in
        --stage-runtime)
            if (($# != 2)) || [[ "$2" != /* ]]; then
                echo "--stage-runtime requires one absolute venv path." >&2
                exit 2
            fi
            INSTALL_MODE="stage"
            VENV="$2"
            ;;
        --refresh-integrations)
            if (($# != 1)); then
                echo "--refresh-integrations does not accept extra arguments." >&2
                exit 2
            fi
            INSTALL_MODE="refresh"
            ;;
        *)
            echo "Unknown installer option: $1" >&2
            exit 2
            ;;
    esac
fi

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

ensure_python_build_tools() {
    local python="$1"

    if "$python" - <<'PY'
from importlib import metadata
import re

try:
    setuptools_version = metadata.version("setuptools")
    import setuptools.build_meta  # noqa: F401
except (metadata.PackageNotFoundError, ImportError):
    raise SystemExit(1)

match = re.match(r"^(\d+)(?:\.(\d+))?", setuptools_version)
if match is None:
    raise SystemExit(1)

major, minor = (int(part or 0) for part in match.groups())
if (major, minor) < (69, 0):
    raise SystemExit(1)
PY
    then
        ok "Python build tooling is already available"
        return 0
    fi

    step "Installing Python build tooling"
    "$python" -m pip install "setuptools>=69"
}

install_integrations() {
    mkdir -p "$APP_HOME" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"

    if [[ ! -x "$VENV/bin/mochi" ]]; then
        warn "Mochi runtime is missing: $VENV/bin/mochi"
        return 1
    fi

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

    if $IS_GNOME; then
        step "Installing Mochi's GNOME helper"
        if command -v gnome-extensions >/dev/null 2>&1; then
            GNOME_HELPER_INSTALLABLE=true
            GNOME_HELPER_ATTEMPTED=true
            if [[ -x "$ROOT/scripts/install-typing-extension.sh" ]]; then
                "$ROOT/scripts/install-typing-extension.sh"
            else
                bash "$ROOT/scripts/install-typing-extension.sh"
            fi
            sleep 0.25
        else
            warn "GNOME extension tools were not found; skipping Mochi's optional awareness helper."
            warn "Mochi can still run, but GNOME-specific contextual reactions and global shortcuts will be limited."
        fi
    else
        step "Skipping GNOME helper"
        warn "Non-GNOME desktop detected; installing Mochi without the optional GNOME awareness helper."
    fi
}

write_install_metadata() {
    local version commit commit_json installed_at temporary

    version="$(
        "$VENV/bin/python" - <<'PY'
from importlib import metadata

print(metadata.version("mochi-desktop"))
PY
    )"
    if [[ -z "$version" ]]; then
        warn "Could not determine installed Mochi version."
        return 1
    fi

    commit="${MOCHI_INSTALLED_COMMIT:-}"
    if [[ -z "$commit" ]] && command -v git >/dev/null 2>&1; then
        commit="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
    fi
    if [[ -n "$commit" ]]; then
        commit_json="\"$commit\""
    else
        commit_json="null"
    fi

    installed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    temporary="$INSTALL_METADATA.tmp"
    cat > "$temporary" <<EOF
{
  "version": "$version",
  "commit": $commit_json,
  "channel": "main",
  "installed_at": "$installed_at"
}
EOF
    mv -f "$temporary" "$INSTALL_METADATA"
}

show_install_complete() {
    step "Installation complete"
    printf '%sLaunch:%s      %s\n' "$CYAN" "$RESET" "$LAUNCHER"
    printf '%sApplication:%s GNOME app grid → Mochi\n' "$CYAN" "$RESET"
    printf '%sUninstall:%s   %s\n' "$CYAN" "$RESET" "$UNINSTALL_LAUNCHER"

    if helper_is_active; then
        show_ready_notice
    elif $IS_GNOME && $GNOME_HELPER_INSTALLABLE && $GNOME_HELPER_ATTEMPTED; then
        show_gnome_reload_notice
    else
        printf '\n'
        warn "GNOME desktop-awareness helper is unavailable on this desktop."
        printf 'Mochi will run with reduced contextual awareness and without GNOME global shortcuts.\n'
    fi
    printf '\n'
}

banner

IS_GNOME=false
GNOME_HELPER_INSTALLABLE=false
GNOME_HELPER_ATTEMPTED=false
desktop="${XDG_CURRENT_DESKTOP:-} ${XDG_SESSION_DESKTOP:-} ${DESKTOP_SESSION:-}"
if [[ "${desktop,,}" == *gnome* ]]; then
    IS_GNOME=true
fi

if [[ ! -f "$ROOT/pyproject.toml" || ! -f "$DESKTOP_TEMPLATE" ]]; then
    echo "Run install.sh from a complete Mochi repository checkout." >&2
    exit 1
fi

if command -v dnf >/dev/null 2>&1 && command -v rpm >/dev/null 2>&1; then
    packages=(
        python3
        python3-pip
        python3-gobject
        python3-cairo
        gtk4
        gtk4-layer-shell
        gstreamer1
        gstreamer1-plugins-base
        libX11
        xorg-x11-server-Xwayland
        pipewire-utils
        glib2
    )
    if $IS_GNOME; then
        packages+=(gnome-shell)
    fi
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

# An activated development venv shadows `python3` in PATH. PyGObject is
# intentionally supplied by Fedora's RPM packages rather than pip, so a normal
# isolated dev venv cannot import `gi`. Resolve the interpreter that created
# the current Python environment and use that system interpreter for OS-level
# dependency checks and for creating Mochi's private --system-site-packages
# environment. This keeps ./install.sh reliable even when run from an active
# .venv.
SYSTEM_PYTHON="$(
    python3 - <<'PY'
import sys

print(getattr(sys, "_base_executable", None) or sys.executable)
PY
)"

if [[ ! -x "$SYSTEM_PYTHON" ]]; then
    if [[ -x /usr/bin/python3 ]]; then
        SYSTEM_PYTHON=/usr/bin/python3
    else
        SYSTEM_PYTHON="$(command -v python3)"
    fi
fi

step "Checking GTK4 / PyGObject"
"$SYSTEM_PYTHON" - <<'PY'
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: F401

print("✓ GTK4 / PyGObject OK")
PY

if [[ "$INSTALL_MODE" == "refresh" ]]; then
    install_integrations
    show_install_complete
    exit 0
fi

step "Installing Mochi"
printf '%sTarget:%s %s\n' "$DIM" "$RESET" "$APP_HOME"
mkdir -p "$APP_HOME" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICON_DIR"

BACKUP_VENV=""
VENV_INSTALL_IN_PROGRESS=false

rollback_private_venv() {
    local status=$?
    trap - EXIT
    set +e
    if [[ "$VENV_INSTALL_IN_PROGRESS" == "true" ]]; then
        if [[ -n "$BACKUP_VENV" && -d "$BACKUP_VENV" ]]; then
            rm -rf "$VENV"
            if ! mv "$BACKUP_VENV" "$VENV"; then
                warn "Failed to restore the previous Mochi environment."
            fi
        elif [[ -z "$BACKUP_VENV" ]]; then
            rm -rf "$VENV"
        fi
    fi
    exit "$status"
}

trap rollback_private_venv EXIT

if [[ -d "$VENV" ]]; then
    BACKUP_VENV="$APP_HOME/venv.backup.$$"
    rm -rf "$BACKUP_VENV"
    VENV_INSTALL_IN_PROGRESS=true
    if ! mv "$VENV" "$BACKUP_VENV"; then
        warn "Failed to back up existing Mochi environment."
        exit 1
    fi
else
    VENV_INSTALL_IN_PROGRESS=true
fi

if ! "$SYSTEM_PYTHON" -m venv --system-site-packages "$VENV"; then
    warn "Failed to create Mochi virtual environment."
    exit 1
fi

# Mochi uses setuptools.build_meta from pyproject.toml. Reuse compatible build
# tooling already visible through --system-site-packages when possible, and only
# ask pip to fetch a newer setuptools when the visible one is too old or missing.
if ! ensure_python_build_tools "$VENV/bin/python"; then
    warn "Failed to install Mochi build tooling into the new environment."
    exit 1
fi

if ! "$VENV/bin/python" -m pip install --no-deps --no-build-isolation "$ROOT"; then
    warn "Failed to install Mochi into the new environment."
    exit 1
fi

if [[ -n "$BACKUP_VENV" && -d "$BACKUP_VENV" ]]; then
    rm -rf "$BACKUP_VENV"
fi

VENV_INSTALL_IN_PROGRESS=false
trap - EXIT

if [[ "$INSTALL_MODE" == "stage" ]]; then
    step "Runtime staged"
    printf '%sTarget:%s %s\n' "$DIM" "$RESET" "$VENV"
    exit 0
fi

install_integrations
write_install_metadata
show_install_complete
exit 0

