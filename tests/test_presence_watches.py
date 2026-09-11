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
