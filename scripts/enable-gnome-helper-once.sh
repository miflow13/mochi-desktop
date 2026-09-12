#!/usr/bin/env bash
set -u

UUID="mochi-typing@miflow13"
BUS_NAME="io.github.mochi_desktop.Mochi.TypingMonitor"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
AUTOSTART_FILE="$CONFIG_HOME/autostart/mochi-enable-gnome-helper-once.desktop"
LOG_DIR="$STATE_HOME/mochi"
LOG_FILE="$LOG_DIR/gnome-helper-setup.log"
MAX_ATTEMPTS="${MOCHI_HELPER_ENABLE_ATTEMPTS:-30}"
DELAY_SECONDS="${MOCHI_HELPER_ENABLE_DELAY_SECONDS:-1}"

mkdir -p "$LOG_DIR"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"
}

helper_is_active() {
    if ! gnome-extensions info "$UUID" 2>/dev/null | grep -Eq 'State:[[:space:]]+ACTIVE'; then
        return 1
    fi

    # glib2/gdbus is part of Mochi's Fedora dependency set. If it is available,
    # also require the helper to own its session-bus name before declaring setup
    # complete. This catches an extension that is marked ACTIVE but failed to
    # initialize its D-Bus bridge.
    if command -v gdbus >/dev/null 2>&1; then
        local owner
        owner="$(
            gdbus call --session \
                --dest org.freedesktop.DBus \
                --object-path /org/freedesktop/DBus \
                --method org.freedesktop.DBus.NameHasOwner \
                "$BUS_NAME" 2>/dev/null || true
        )"
        [[ "$owner" == *"true"* ]] || return 1
    fi

    return 0
}

finish_setup() {
    rm -f "$AUTOSTART_FILE"
    log "GNOME helper is active; removed one-time autostart entry."
}

if ! command -v gnome-extensions >/dev/null 2>&1; then
    log "gnome-extensions is unavailable; leaving one-time setup scheduled."
    exit 0
fi

if helper_is_active; then
    finish_setup
    exit 0
fi

log "Post-login GNOME helper setup started."
attempt=1
while (( attempt <= MAX_ATTEMPTS )); do
    # A newly logged-in GNOME session can take a moment to discover user
    # extensions. Retry briefly instead of racing Shell startup once.
    gnome-extensions enable "$UUID" >> "$LOG_FILE" 2>&1 || true

    if helper_is_active; then
        finish_setup
        exit 0
    fi

    if (( attempt < MAX_ATTEMPTS )); then
        sleep "$DELAY_SECONDS"
    fi
    ((attempt += 1))
done

log "GNOME helper did not become active; leaving one-time setup scheduled for the next login."
exit 0
