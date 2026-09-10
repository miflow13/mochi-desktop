# Mochi Desktop Activity GNOME Extension

This optional GNOME Shell extension gives Mochi privacy-safe desktop activity signals on GNOME/Wayland.

It currently provides:

- `Pulse` — anonymous keyboard activity used by the typing-reactive emote.
- `UserIdle` — emitted after 120 seconds of real server-global inactivity.
- `UserActive` — emitted on the first real input after `UserIdle`.
- `FileBrowsingStarted` / `FileBrowsingStopped` — semantic focus state for supported file managers such as GNOME Files/Nautilus.

Presence uses Mutter's server-global idle monitor. Typing inspects only the broad input-device type needed to distinguish keyboard activity. File browsing is classified inside GNOME Shell from application identifiers and reduced to a yes/no state before it reaches Mochi. The extension never reads, stores, logs, or transmits key symbols, keycodes, Unicode values, modifiers, shortcuts, passwords, text, pointer coordinates, window titles, file names, folder names, paths, or application content.

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

## Developer shortcut

`Ctrl + Alt + Shift + M` opens Mochi's private developer-tuning popover. The shortcut is handled inside GNOME Shell and emits only a zero-payload `DeveloperMenuRequested` signal; no key identity is sent to Mochi.
