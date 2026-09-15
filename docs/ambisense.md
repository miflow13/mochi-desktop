# AmbiSense

**AmbiSense** is the name of Mochi's lightweight local ambient-awareness system.

It turns privacy-reduced desktop signals into small behavior decisions without reading the content of what the user types.

The implementation continues to use `presence` internally (`PresenceEngine`, `PresenceBuddyMixin`, and related modules). Those names describe the code architecture; **AmbiSense** is the user-facing subsystem name.

## Returning after suspend

When Mochi stays running through suspend, `SessionSignalMonitor` observes
logind's `PrepareForSleep` signal and the current session's `LockedHint` and
`Active` properties. It resolves the concrete session object through
`GetSession("auto")`, since convenience session paths do not emit changes.
These are read-only observations of the
[logind interface](https://github.com/systemd/systemd/blob/main/man/org.freedesktop.login1.xml).

Suspend, locking, and leaving the active session suppress ambient speech and
expire pending environmental observations. After resume, Mochi reads the lock
state again and waits until the session is unlocked and active. The combined
cycle requests one `welcome_back` greeting from the canonical phrase pool,
including short suspends that never meet the normal idle-return threshold.
Repeated notifications do not request extra greetings. Unlocking without
suspending also counts as a return.

The greeting waits for normal speech ownership and global cooldowns, including
Mochi's wake animation, menu/drag activity, quiet mode, and existing bubbles.
A higher-priority system event can speak first without losing the greeting.
Successful delivery consumes the pending greeting and records its cooldown.
Animation previews do not start the session monitor. If logind or its session
properties are unavailable, this optional feature stays disabled.

Manual check: run Mochi with debug logging, suspend the desktop, resume and
unlock it. Expect one `[session] away` / `[session] returned` pair, followed by
one delivered `welcome_back` after any wake animation. Repeat with a short
suspend and with lock/unlock alone. No greeting should be delivered while the
lock screen remains active. Automated tests exercise both unlock/resume signal
orders; they do not suspend the host running the test suite.
