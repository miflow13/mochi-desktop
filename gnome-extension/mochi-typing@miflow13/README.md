# Mochi Desktop Activity GNOME Extension

This optional GNOME Shell extension gives Mochi privacy-safe desktop activity signals on GNOME/Wayland.

It currently provides:

- `Pulse` — anonymous keyboard activity used by the typing-reactive emote.
- `UserIdle` — emitted after 120 seconds of real server-global inactivity.
- `UserActive` — emitted on the first real input after `UserIdle`.

Presence uses Mutter's server-global idle monitor. Typing inspects only the broad input-device type needed to distinguish keyboard activity. The extension never reads, stores, logs, or transmits key symbols, keycodes, Unicode values, modifiers, shortcuts, passwords, text, pointer coordinates, application content, or window titles.

## Local development install

From the Mochi repository root:

```bash
./scripts/install-typing-extension.sh
```

On GNOME Wayland, a full logout/login may be required after changing extension JavaScript because the Shell can retain the previous loaded module. Then enable/check it with:

```bash
gnome-extensions enable mochi-typing@miflow13
gnome-extensions info mochi-typing@miflow13
```

The expected state is `ACTIVE`.
