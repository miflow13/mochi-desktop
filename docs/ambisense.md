# AmbiSense

**AmbiSense** is Mochi's lightweight local ambient-awareness system. It turns
privacy-reduced desktop signals into behavior decisions without reading the
content of what the user types.

The implementation uses `presence` internally (`PresenceEngine`,
`PresenceBuddyMixin`, and related modules). Those names describe the code
architecture; AmbiSense is the user-facing subsystem name.

## Event flow

On GNOME, the desktop-awareness path is intentionally simple:

```text
GNOME Shell helper
→ observes coarse desktop activity
→ reduces it to anonymous / semantic signals
→ sends signals over D-Bus
→ Mochi's Python presence layer receives them
→ AmbiSense decides whether to react
```

The result may be speech, a contextual activity, a state transition, or no
visible response. Repeated detection of an already-active context must not
continuously restart its presentation.

## Signals

Depending on the desktop environment and available helpers, AmbiSense can use:

- anonymous typing activity and sustained typing intensity;
- active, idle, lock, suspend, and return state;
- coarse app categories such as editor, terminal, browser, media, or pixel-art
  software, plus content-free pulses when you switch windows or change
  browser tab;
- focused media playback, battery and charging transitions, network changes,
  and file-browsing activity.

These signals are intentionally lower-resolution than the underlying desktop
activity.

## Privacy model

Typing awareness is content-blind. Mochi does not store characters, inspect
typed text, reconstruct words, log key values, or persist typing history.

Application awareness is reduced to broad semantic categories before Mochi
reacts. The goal is to observe the shape of desktop activity without reading
the user's work.

Browser tab awareness is timing-only. While the focused window is a browser,
the GNOME helper watches its title change inside GNOME Shell, keeps a one-way
digest in memory to tell whether it changed, and sends Mochi a pulse with no
data. The title never leaves GNOME Shell, and the pulse goes out only within
two seconds of real keyboard or pointer input, so unread counters and autoplay
that retitle the page while you're hands-off do not count. Once the helper
classifies a browser window as YouTube, immediately when focus lands on it and
otherwise within about a second, tab tracking pauses and reads no further
title for that window. Until then, a title change on an already-tracked
window, including the one that takes it to YouTube, is handled like any other.
The existing YouTube check, which reduces a title to a yes or no, is
unchanged. Like the helper's other signals, the pulse's timing is visible on
the session bus.

AmbiSense is a local rule-based behavior engine, not an LLM or cloud AI
service.

## Session return

`SessionSignalMonitor` observes logind's `PrepareForSleep` signal and the
current session's `LockedHint` and `Active` properties. It resolves the
concrete session object through `GetSession("auto")`, because convenience
session paths do not emit property changes. These are read-only observations
of the [logind interface](https://github.com/systemd/systemd/blob/main/man/org.freedesktop.login1.xml).

Suspend, lock, and loss of the active session suppress ambient speech and
discard pending environmental observations. After resume, Mochi refreshes the
lock state and waits for an unlocked, active session. The completed lifecycle
requests one `welcome_back` greeting, including for short suspends that do not
meet the ordinary idle-return threshold. Unlocking without suspend also counts
as a return.

The greeting waits for normal dialogue ownership and global cooldowns. Wake
animations, menu or drag activity, quiet mode, existing bubbles, and a
higher-priority system event can defer it without losing it. Animation previews
do not start the session monitor. If logind or its session properties are
unavailable, this optional feature stays disabled.

## Detection and presentation

Detectors report meaningful context changes. The character/state layer decides
whether a reaction may interrupt current behavior and which animation or
dialogue, if any, represents it. Detection does not own animation state.

This separation lets Mochi handle overlapping signals while the user is
clicking, dragging, sleeping or waking the character, or triggering another
contextual state.

## Failure behavior

Ambient awareness degrades gracefully. If a helper or signal source is
unavailable, Mochi continues to function with reduced contextual behavior.

For setup and diagnosis, see [Troubleshooting and Regressions](wiki/Troubleshooting-and-Regressions.md).
