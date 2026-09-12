"""Run the helper's actual watch methods against Mutter-style watch semantics."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_global_idle_watch_is_retained_across_repeated_cycles():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the GNOME helper watch harness")
    source = (Path(__file__).resolve().parents[1] /
              "gnome-extension/mochi-typing@miflow13/extension.js").read_text()
    methods = source[source.index("    _armPresenceIdleWatch() {"):
                     source.index("    _sampleInput(allowPulse) {")]
    script = """
const assert = require('node:assert/strict');
const USER_IDLE_AFTER_MS = 120000;
const USER_IDLE_SIGNAL_NAME = 'idle', USER_ACTIVE_SIGNAL_NAME = 'active';
class Presence { METHODS }
const p = new Presence();
const watches = new Map();
let next = 0;
p._presenceIdleWatchId = p._presenceActiveWatchId = 0;
p._presenceIsIdle = false;
const events = [];
p._emitSignal = event => events.push(event);
p._idleMonitor = {
    add_idle_watch(ms, callback) {
        assert.equal(ms, 120000);
        watches.set(++next, callback);
        return next;
    },
    add_user_active_watch(callback) {
        watches.set(++next, callback);
        return next;
    },
};
p._armPresenceIdleWatch();
const idleId = p._presenceIdleWatchId;
for (let cycle = 0; cycle < 3; cycle++) {
    watches.get(idleId)();
    watches.get(idleId)(); // Duplicate idle notification must not restart sleep.
    assert.equal(p._presenceIdleWatchId, idleId);
    const activeId = p._presenceActiveWatchId;
    const active = watches.get(activeId);
    watches.delete(activeId); // Mutter active watches are one-shot.
    active();
    assert.equal(watches.size, 1);
    assert.equal(p._presenceActiveWatchId, 0);
}
assert.deepEqual(events, ['idle', 'active', 'idle', 'active', 'idle', 'active']);
""".replace("METHODS", methods)
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)


def test_helper_sync_replays_semantic_state_and_disconnects_on_disable():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the GNOME helper watch harness")
    source = (Path(__file__).resolve().parents[1] /
              "gnome-extension/mochi-typing@miflow13/extension.js").read_text()
    # Run the actual extension with only GNOME's platform objects stubbed.
    source = "\n".join(line for line in source.splitlines()
                       if not line.startswith("import "))
    source = source.replace("export default class", "class")
    script = """
const assert = require('node:assert/strict');
const events = [], subscriptions = new Map();
let acquired;
const connection = {
    signal_subscribe(sender, iface, signal, path, arg, flags, callback) {
        subscriptions.set(17, callback);
        assert.equal(signal, 'SyncStateRequested');
        return 17;
    },
    signal_unsubscribe(id) { assert.equal(id, 17); subscriptions.delete(id); },
    emit_signal(destination, path, iface, signal, payload) {
        events.push([signal, payload?.value ?? null]);
    },
};
const Gio = {
    DBus: {session: connection}, DBusSignalFlags: {NONE: 0},
    BusNameOwnerFlags: {NONE: 0},
    bus_own_name_on_connection(conn, name, flags, callback) {
        acquired = callback; return 5;
    },
    bus_unown_name(id) { assert.equal(id, 5); },
};
const GLib = {
    PRIORITY_DEFAULT: 0, SOURCE_CONTINUE: true,
    timeout_add() { return 1; }, Source: {remove() {}},
    get_monotonic_time() { return 1000; },
    Variant: class { constructor(signature, value) { this.value = value; } },
};
const Main = {wm: {addKeybinding() {}, removeKeybinding() {}}};
const Meta = {KeyBindingFlags: {NONE: 0}}, Shell = {ActionMode: {ALL: 0}};
const Extension = class { getSettings() { return {}; } };
const idleMonitor = {
    get_idletime() { return 0; }, add_idle_watch() { return 9; }, remove_watch() {},
};
global.backend = {
    connect() { return 1; }, disconnect() {},
    get_core_idle_monitor() { return idleMonitor; },
};
global.display = {
    connect() { return 1; }, disconnect() {}, get_focus_window() { return null; },
};
__EXTENSION_SOURCE__
const helper = new MochiTypingActivityExtension();
helper.enable();
assert.equal(subscriptions.size, 1);
acquired();
assert.deepEqual(events, [
    ['UserActive', null], ['FileBrowsingStopped', null],
    ['YouTubeFocusedStopped', null], ['AppCategoryChanged', ['unknown']],
]);
events.length = 0;
helper._presenceIsIdle = helper._fileBrowsingActive = helper._youtubeFocusedActive = true;
helper._appCategory = 'editor';
subscriptions.get(17)();
assert.deepEqual(events, [
    ['UserIdle', null], ['FileBrowsingStarted', null],
    ['YouTubeFocusedStarted', null], ['AppCategoryChanged', ['editor']],
]);
assert.ok(events.every(([name]) => name !== 'Pulse' && name !== 'DeveloperMenuRequested'));
helper.disable();
assert.equal(subscriptions.size, 0);
events.length = 0;
helper._publishCurrentState();
assert.deepEqual(events, []);
""".replace("__EXTENSION_SOURCE__", source)
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
