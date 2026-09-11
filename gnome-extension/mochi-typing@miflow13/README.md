# Mochi Desktop Activity GNOME Extension

This optional GNOME Shell extension gives Mochi privacy-safe desktop activity signals on GNOME/Wayland.

It currently provides:

- `Pulse` — anonymous keyboard activity used by the typing-reactive emote and presence intensity tracking.
- `UserIdle` — emitted after 120 seconds of real server-global inactivity.
- `UserActive` — emitted on the first real input after `UserIdle`.
- `FileBrowsingStarted` / `FileBrowsingStopped` — semantic focus state for supported file managers such as GNOME Files/Nautilus.
- `YouTubeFocusedStarted` / `YouTubeFocusedStopped` — a privacy-reduced focused-YouTube boolean used by watch-along behavior.
- `AppCategoryChanged` — a coarse category only: `vscode`, `editor`, `terminal`, `browser`, `media`, `pixel_art`, or `unknown`.

Presence uses Mutter's server-global idle monitor. Typing inspects only the broad input-device type needed to distinguish keyboard activity. File browsing and app category are classified inside GNOME Shell from application identifiers and reduced to semantic state before reaching Mochi. General app-category detection never sends application IDs or window titles. The extension never stores or transmits key symbols, keycodes, Unicode values, modifiers, shortcuts, passwords, typed text, pointer coordinates, file names, folder names, paths, or application content.

The existing YouTube-focus helper may transiently inspect the focused browser title only to reduce it to a yes/no YouTube state; the title itself is never retained, logged, or transmitted.

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
