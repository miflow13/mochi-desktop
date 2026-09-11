import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'io.github.mochi_desktop.Mochi.TypingMonitor';
const OBJECT_PATH = '/io/github/mochi_desktop/Mochi/TypingMonitor';
const INTERFACE_NAME = 'io.github.mochi_desktop.Mochi.TypingMonitor';
const TYPING_SIGNAL_NAME = 'Pulse';
const USER_IDLE_SIGNAL_NAME = 'UserIdle';
const USER_ACTIVE_SIGNAL_NAME = 'UserActive';
const FILE_BROWSING_STARTED_SIGNAL_NAME = 'FileBrowsingStarted';
const FILE_BROWSING_STOPPED_SIGNAL_NAME = 'FileBrowsingStopped';
const YOUTUBE_FOCUSED_STARTED_SIGNAL_NAME = 'YouTubeFocusedStarted';
const YOUTUBE_FOCUSED_STOPPED_SIGNAL_NAME = 'YouTubeFocusedStopped';
const APP_CATEGORY_SIGNAL_NAME = 'AppCategoryChanged';
const DEVELOPER_MENU_SIGNAL_NAME = 'DeveloperMenuRequested';
const DEVELOPER_MENU_KEYBINDING = 'developer-menu-shortcut';

// These are application identifiers only. Window titles, folder names, file
// names, and paths are never inspected or transmitted to Mochi.
const FILE_MANAGER_MARKERS = [
    'org.gnome.nautilus',
    'nautilus',
    'org.kde.dolphin',
    'dolphin',
    'thunar',
    'nemo',
    'pcmanfm',
    'pcmanfm-qt',
    'caja',
];

// Presence receives only one of these broad categories. The raw application
// identity used to classify it remains inside GNOME Shell.
const EDITOR_MARKERS = [
    'code',
    'code-oss',
    'vscodium',
    'codium',
    'cursor',
    'zed',
    'sublime_text',
    'sublime-text',
    'org.gnome.builder',
    'gnome-builder',
    'jetbrains-',
    'pycharm',
    'idea',
    'kate',
];
const TERMINAL_MARKERS = [
    'org.gnome.terminal',
    'gnome-terminal',
    'org.gnome.ptyxis',
    'ptyxis',
    'kitty',
    'alacritty',
    'wezterm',
    'org.gnome.console',
    'kgx',
    'konsole',
    'foot',
];
const PIXEL_ART_MARKERS = [
    'pixelorama',
    'com.orama-interactive.pixelorama',
];
const MEDIA_APP_MARKERS = [
    'org.videolan.vlc',
    'vlc',
    'mpv',
    'celluloid',
    'org.gnome.totem',
    'totem',
    'showtime',
];

// Keep the existing two-minute sleep behavior, but drive it from Mutter's
// server-global idle monitor instead of Mochi-local interaction timestamps.
const USER_IDLE_AFTER_MS = 120_000;

// We cannot observe client-window key events through global.stage on Wayland.
// GNOME 50 also does not expose Meta.Backend.get_last_input_device(); that
// getter was added in Mutter 51. Instead, remember only the TYPE reported by
// Meta.Backend's existing last-device-changed signal, then use the server-global
// idle monitor to notice each new input event.
//
// Privacy boundary: we never inspect key symbols, keycodes, Unicode values,
// modifiers, text, shortcuts, file names, folder names, or application content.
// Application identity is inspected only inside GNOME Shell and reduced to a
// coarse category before it crosses D-Bus.
const POLL_INTERVAL_MS = 50;
const EVENT_TIME_EPSILON_MS = 12;
const VIDEO_FOCUS_HEARTBEAT_MS = 1_000;
const BROWSER_MARKERS = [
    'google-chrome',
    'com.google.chrome',
    'chromium',
    'chrome',
    'firefox',
    'mozilla.firefox',
    'brave',
    'vivaldi',
    'microsoft-edge',
    'microsoft.edge',
    'msedge',
];
const BROWSER_TITLE_NAMES = [
    'google chrome',
    'chromium',
    'chrome',
    'mozilla firefox',
    'firefox',
    'brave',
    'vivaldi',
    'microsoft edge',
];

export default class MochiTypingActivityExtension extends Extension {
    enable() {
        this._connection = Gio.DBus.session;
        this._nameReady = false;
        this._pollSourceId = 0;
        this._lastInputEventAtMs = null;
        this._lastInputWasKeyboard = false;
        this._presenceIdleWatchId = 0;
        this._presenceActiveWatchId = 0;
        this._presenceIsIdle = false;
        this._fileBrowsingActive = false;
        this._youtubeFocusedActive = false;
        this._appCategory = 'unknown';
        this._videoFocusHeartbeatId = 0;
        this._focusChangedId = 0;
        this._settings = this.getSettings();

        Main.wm.addKeybinding(
            DEVELOPER_MENU_KEYBINDING,
            this._settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.ALL,
            () => {
                // Diagnostic only: no key identity, typed data, or window data.
                console.debug('[Mochi] Developer menu shortcut requested');
                this._emitSignal(DEVELOPER_MENU_SIGNAL_NAME);
            },
        );

        this._lastDeviceChangedId = global.backend.connect(
            'last-device-changed',
            (_backend, device) => {
                // Privacy boundary: inspect only the broad device TYPE. Never
                // inspect key symbols, codes, modifiers, text, or application data.
                this._lastInputWasKeyboard = device !== null &&
                    device.get_device_type() === Clutter.InputDeviceType.KEYBOARD_DEVICE;
            },
        );

        this._idleMonitor = global.backend.get_core_idle_monitor();

        this._focusChangedId = global.display.connect(
            'notify::focus-window',
            () => {
                this._updateFileBrowsingState();
                this._updateYouTubeFocusedState(false);
                this._updateAppCategory();
            },
        );
        this._updateFileBrowsingState();
        this._updateYouTubeFocusedState(false);
        this._updateAppCategory();
        this._videoFocusHeartbeatId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            VIDEO_FOCUS_HEARTBEAT_MS,
            () => {
                this._updateYouTubeFocusedState(true);
                this._updateAppCategory();
                return GLib.SOURCE_CONTINUE;
            },
        );

        this._nameOwnerId = Gio.bus_own_name_on_connection(
            this._connection,
            BUS_NAME,
            Gio.BusNameOwnerFlags.NONE,
            () => {
                this._nameReady = true;
                // If semantic state changed before D-Bus ownership completed,
                // publish the current state once ownership is ready.
                if (this._presenceIsIdle)
                    this._emitSignal(USER_IDLE_SIGNAL_NAME);
                if (this._fileBrowsingActive)
                    this._emitSignal(FILE_BROWSING_STARTED_SIGNAL_NAME);
                this._emitSignal(
                    this._youtubeFocusedActive
                        ? YOUTUBE_FOCUSED_STARTED_SIGNAL_NAME
                        : YOUTUBE_FOCUSED_STOPPED_SIGNAL_NAME,
                );
                this._emitAppCategory();
            },
            () => {
                this._nameReady = false;
            },
        );

        // Establish a baseline so pre-existing activity does not emit a typing
        // pulse when the extension starts.
        this._sampleInput(false);

        this._pollSourceId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            POLL_INTERVAL_MS,
            () => {
                this._sampleInput(true);
                return GLib.SOURCE_CONTINUE;
            },
        );

        this._armPresenceIdleWatch();
    }

    _emitSignal(signalName) {
        if (!this._nameReady || this._connection === null)
            return;

        try {
            this._connection.emit_signal(
                null,
                OBJECT_PATH,
                INTERFACE_NAME,
                signalName,
                null,
            );
        } catch (_error) {
            // Never log input-, window-, or file-related data. Dropping a
            // semantic signal is safe.
        }
    }

    _emitAppCategory() {
        if (!this._nameReady || this._connection === null)
            return;

        try {
            this._connection.emit_signal(
                null,
                OBJECT_PATH,
                INTERFACE_NAME,
                APP_CATEGORY_SIGNAL_NAME,
                new GLib.Variant('(s)', [this._appCategory]),
            );
        } catch (_error) {
            // Category is best-effort. Never fall back to transmitting raw
            // application identity when this semantic signal cannot be sent.
        }
    }

    _updateAppCategory() {
        const category = this._classifyAppCategory(global.display.get_focus_window());
        if (category === this._appCategory)
            return;
        this._appCategory = category;
        this._emitAppCategory();
    }

    _classifyAppCategory(window) {
        if (window === null)
            return 'unknown';

        const identities = [];
        for (const methodName of [
            'get_gtk_application_id',
            'get_wm_class',
            'get_wm_class_instance',
        ]) {
            try {
                const method = window[methodName];
                if (typeof method !== 'function')
                    continue;
                const value = method.call(window);
                if (typeof value === 'string' && value.length > 0)
                    identities.push(value.toLowerCase());
            } catch (_error) {
                // Unknown identity means unknown category; never inspect title
                // as a fallback for general application classification.
            }
        }

        const matches = markers => identities.some(identity =>
            markers.some(marker => identity === marker || identity.includes(marker))
        );
        if (matches(PIXEL_ART_MARKERS))
            return 'pixel_art';
        if (matches(EDITOR_MARKERS))
            return 'editor';
        if (matches(TERMINAL_MARKERS))
            return 'terminal';
        if (matches(BROWSER_MARKERS))
            return this._isFocusedYouTubeWindow(window) ? 'media' : 'browser';
        if (matches(MEDIA_APP_MARKERS))
            return 'media';
        return 'unknown';
    }

    _updateFileBrowsingState() {
        const window = global.display.get_focus_window();
        const active = this._isFileManagerWindow(window);
        if (active === this._fileBrowsingActive)
            return;

        this._fileBrowsingActive = active;
        this._emitSignal(
            active
                ? FILE_BROWSING_STARTED_SIGNAL_NAME
                : FILE_BROWSING_STOPPED_SIGNAL_NAME,
        );
    }

    _isFileManagerWindow(window) {
        if (window === null)
            return false;

        const identities = [];
        for (const methodName of [
            'get_gtk_application_id',
            'get_wm_class',
            'get_wm_class_instance',
        ]) {
            try {
                const method = window[methodName];
                if (typeof method !== 'function')
                    continue;
                const value = method.call(window);
                if (typeof value === 'string' && value.length > 0)
                    identities.push(value.toLowerCase());
            } catch (_error) {
                // A missing identifier simply means this window cannot be
                // classified by that field. Never inspect its title instead.
            }
        }

        return identities.some(identity =>
            FILE_MANAGER_MARKERS.some(marker =>
                identity === marker || identity.includes(marker)
            )
        );
    }

    _updateYouTubeFocusedState(emitHeartbeat) {
        const window = global.display.get_focus_window();
        const active = this._isFocusedYouTubeWindow(window);
        const changed = active !== this._youtubeFocusedActive;

        this._youtubeFocusedActive = active;
        if (!changed && !emitHeartbeat)
            return;

        // Privacy boundary: only this boolean leaves GNOME Shell. The title
        // itself is never logged, stored, or sent over D-Bus.
        this._emitSignal(
            active
                ? YOUTUBE_FOCUSED_STARTED_SIGNAL_NAME
                : YOUTUBE_FOCUSED_STOPPED_SIGNAL_NAME,
        );
    }

    _isFocusedYouTubeWindow(window) {
        if (window === null)
            return false;

        const identities = [];
        for (const methodName of [
            'get_gtk_application_id',
            'get_wm_class',
            'get_wm_class_instance',
        ]) {
            try {
                const method = window[methodName];
                if (typeof method !== 'function')
                    continue;
                const value = method.call(window);
                if (typeof value === 'string' && value.length > 0)
                    identities.push(value.toLowerCase());
            } catch (_error) {
                // Missing identifiers simply make this window unclassifiable.
            }
        }

        const isBrowser = identities.some(identity =>
            BROWSER_MARKERS.some(marker => identity.includes(marker))
        );
        if (!isBrowser)
            return false;

        // Browser MPRIS data often omits the page URL. Inspect the focused title
        // only long enough to reduce it to a boolean; the raw title is never
        // logged, retained, or sent over D-Bus.
        let title = '';
        try {
            title = String(window.get_title() ?? '').trim().toLowerCase();
        } catch (_error) {
            return false;
        }

        if (title.includes('youtube music'))
            return false;

        // Chrome/Chromium/Firefox can append their own application name after
        // the page title, e.g. "Video - YouTube - Google Chrome". Strip only a
        // known browser suffix, then require YouTube to be the page-brand suffix.
        for (const browserName of BROWSER_TITLE_NAMES) {
            for (const separator of [' - ', ' – ', ' — ']) {
                const suffix = `${separator}${browserName}`;
                if (title.endsWith(suffix)) {
                    title = title.slice(0, -suffix.length).trim();
                    break;
                }
            }
        }

        return (
            title.endsWith(' - youtube') ||
            title.endsWith(' – youtube') ||
            title.endsWith(' — youtube') ||
            title === 'youtube'
        );
    }

    _armPresenceIdleWatch() {
        if (this._idleMonitor === null || this._presenceIdleWatchId)
            return;

        this._presenceIdleWatchId = this._idleMonitor.add_idle_watch(
            USER_IDLE_AFTER_MS,
            () => {
                this._presenceIdleWatchId = 0;
                if (!this._presenceIsIdle) {
                    this._presenceIsIdle = true;
                    this._emitSignal(USER_IDLE_SIGNAL_NAME);
                }
                this._armPresenceActiveWatch();
            },
        );
    }

    _armPresenceActiveWatch() {
        if (this._idleMonitor === null || this._presenceActiveWatchId)
            return;

        // Mutter documents this as a one-shot watch intended to be armed after
        // an idle watch fires. Any real user input (keyboard, pointer, touch,
        // etc.) wakes it; no input contents are inspected.
        this._presenceActiveWatchId = this._idleMonitor.add_user_active_watch(
            () => {
                this._presenceActiveWatchId = 0;
                if (this._presenceIsIdle) {
                    this._presenceIsIdle = false;
                    this._emitSignal(USER_ACTIVE_SIGNAL_NAME);
                }
                this._armPresenceIdleWatch();
            },
        );
    }

    _sampleInput(allowPulse) {
        if (this._idleMonitor === null)
            return;

        const idleMs = Number(this._idleMonitor.get_idletime());
        if (!Number.isFinite(idleMs) || idleMs < 0)
            return;

        const nowMs = GLib.get_monotonic_time() / 1000;
        const inputEventAtMs = nowMs - idleMs;

        // get_idletime() advances with monotonic time, so now-idle remains
        // approximately constant until a NEW input event resets idle time.
        const isNewInput = this._lastInputEventAtMs === null ||
            inputEventAtMs > this._lastInputEventAtMs + EVENT_TIME_EPSILON_MS;

        if (!isNewInput)
            return;

        // Record every new input event, not only keyboard events. That prevents
        // pointer activity from being mistaken for a later keyboard pulse.
        this._lastInputEventAtMs = inputEventAtMs;

        if (!allowPulse)
            return;

        // GNOME 50 does not have get_last_input_device(). The signal above
        // maintains only whether the most recently active hardware class is a
        // keyboard. Once the keyboard becomes current, repeated keypresses keep
        // this true while each idle-time reset produces a fresh anonymous pulse.
        if (this._lastInputWasKeyboard)
            this._emitSignal(TYPING_SIGNAL_NAME);
    }

    disable() {
        Main.wm.removeKeybinding(DEVELOPER_MENU_KEYBINDING);
        this._settings = null;

        if (this._pollSourceId) {
            GLib.Source.remove(this._pollSourceId);
            this._pollSourceId = 0;
        }
        if (this._videoFocusHeartbeatId) {
            GLib.Source.remove(this._videoFocusHeartbeatId);
            this._videoFocusHeartbeatId = 0;
        }

        if (this._idleMonitor !== null) {
            if (this._presenceIdleWatchId) {
                this._idleMonitor.remove_watch(this._presenceIdleWatchId);
                this._presenceIdleWatchId = 0;
            }
            if (this._presenceActiveWatchId) {
                this._idleMonitor.remove_watch(this._presenceActiveWatchId);
                this._presenceActiveWatchId = 0;
            }
        }

        if (this._lastDeviceChangedId) {
            global.backend.disconnect(this._lastDeviceChangedId);
            this._lastDeviceChangedId = 0;
        }

        if (this._focusChangedId) {
            global.display.disconnect(this._focusChangedId);
            this._focusChangedId = 0;
        }

        this._idleMonitor = null;
        this._lastInputEventAtMs = null;
        this._lastInputWasKeyboard = false;
        this._presenceIsIdle = false;
        this._fileBrowsingActive = false;
        this._youtubeFocusedActive = false;
        this._appCategory = 'unknown';
        this._nameReady = false;

        if (this._nameOwnerId) {
            Gio.bus_unown_name(this._nameOwnerId);
            this._nameOwnerId = 0;
        }

        this._connection = null;
    }
}
