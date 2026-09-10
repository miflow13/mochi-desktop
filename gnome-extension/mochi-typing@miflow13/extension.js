import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'io.github.mochi_desktop.Mochi.TypingMonitor';
const OBJECT_PATH = '/io/github/mochi_desktop/Mochi/TypingMonitor';
const INTERFACE_NAME = 'io.github.mochi_desktop.Mochi.TypingMonitor';
const SIGNAL_NAME = 'Pulse';

// We cannot observe client-window key events through global.stage on Wayland.
// GNOME 50 also does not expose Meta.Backend.get_last_input_device(); that
// getter was added in Mutter 51. Instead, remember only the TYPE reported by
// Meta.Backend's existing last-device-changed signal, then use the server-global
// idle monitor to notice each new input event.
//
// Privacy boundary: we never inspect key symbols, keycodes, Unicode values,
// modifiers, text, shortcuts, or application content. The only D-Bus payload is
// a zero-argument Pulse indicating anonymous keyboard activity.
const POLL_INTERVAL_MS = 50;
const EVENT_TIME_EPSILON_MS = 12;

export default class MochiTypingActivityExtension extends Extension {
    enable() {
        this._connection = Gio.DBus.session;
        this._nameReady = false;
        this._pollSourceId = 0;
        this._lastInputEventAtMs = null;
        this._lastInputWasKeyboard = false;
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

        this._nameOwnerId = Gio.bus_own_name_on_connection(
            this._connection,
            BUS_NAME,
            Gio.BusNameOwnerFlags.NONE,
            () => {
                this._nameReady = true;
            },
            () => {
                this._nameReady = false;
            },
        );

        // Establish a baseline so pre-existing activity does not emit a pulse
        // when the extension starts.
        this._sampleInput(false);

        this._pollSourceId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            POLL_INTERVAL_MS,
            () => {
                this._sampleInput(true);
                return GLib.SOURCE_CONTINUE;
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

        if (!allowPulse || !this._nameReady || this._connection === null)
            return;

        // GNOME 50 does not have get_last_input_device(). The signal above
        // maintains only whether the most recently active hardware class is a
        // keyboard. Once the keyboard becomes current, repeated keypresses keep
        // this true while each idle-time reset produces a fresh anonymous pulse.
        if (!this._lastInputWasKeyboard)
            return;

        try {
            this._connection.emit_signal(
                null,
                OBJECT_PATH,
                INTERFACE_NAME,
                SIGNAL_NAME,
                null,
            );
        } catch (_error) {
            // Never log event data. Dropping an activity pulse is harmless.
        }
    }

    disable() {
        if (this._pollSourceId) {
            GLib.Source.remove(this._pollSourceId);
            this._pollSourceId = 0;
        }

        if (this._lastDeviceChangedId) {
            global.backend.disconnect(this._lastDeviceChangedId);
            this._lastDeviceChangedId = 0;
        }

        this._idleMonitor = null;
        this._lastInputEventAtMs = null;
        this._lastInputWasKeyboard = false;
        this._nameReady = false;

        if (this._nameOwnerId) {
            Gio.bus_unown_name(this._nameOwnerId);
            this._nameOwnerId = 0;
        }

        this._connection = null;
    }
}
