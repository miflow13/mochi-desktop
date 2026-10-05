# Mochi Desktop Activity GNOME Extension

This optional GNOME Shell extension gives Mochi privacy-safe desktop activity signals on GNOME/Wayland.

It currently provides:

- `Pulse` — anonymous keyboard activity used by the typing-reactive emote and presence intensity tracking.
- `UserIdle` — emitted after 120 seconds of real server-global inactivity.
- `UserActive` — emitted on the first real input after `UserIdle`.
- `FileBrowsingStarted` / `FileBrowsingStopped` — semantic focus state for supported file managers such as GNOME Files/Nautilus.
- `YouTubeFocusedStarted` / `YouTubeFocusedStopped` — a privacy-reduced focused-YouTube boolean used by watch-along behavior.
- `AppCategoryChanged` — a coarse category only: `vscode`, `editor`, `terminal`, `browser`, `media`, `pixel_art`, or `unknown`.
- `AppFocusChanged` — emitted on focused-window changes with only that same coarse category, allowing curiosity feedback even when two windows share a category.
- `BrowserTabChanged` — zero-payload pulse when the focused browser window's title changes (a tab switch or a followed link), or when that same window leaves a YouTube tab for another tab, seen as that window's coarse category changing from media back to browser. Either way it is sent only within two seconds of real keyboard or pointer input, so title blinkers, autoplay, and unread counters that retitle the page while you're hands-off are ignored. A leading unread-count badge such as `(3)` is also stripped before titles are compared.
- `EmoteCatalogueRequested` — zero-payload request from the user-facing catalogue shortcut.

Presence uses Mutter's server-global idle monitor. Typing inspects only the broad input-device type needed to distinguish keyboard activity. File browsing and app category are classified inside GNOME Shell from application identifiers and reduced to semantic state before reaching Mochi. General app-category detection never sends application IDs or window titles. The extension never stores or transmits key symbols, keycodes, Unicode values, modifiers, shortcuts, passwords, typed text, pointer coordinates, file names, folder names, paths, or application content.

The existing YouTube-focus helper may transiently inspect the focused browser title only to reduce it to a yes/no YouTube state; the title itself is never retained, logged, or transmitted.

Tab awareness observes title changes only on the focused window while it is classified `browser`. Once the helper classifies a browser window as YouTube (`media`) — immediately when focus lands on it, otherwise within about a second — tab tracking pauses and reads no further title for that window; the YouTube-focus check above is unchanged. Until then, title changes on an already-tracked window, including the one that takes it to YouTube, are handled like any other: reduced to a digest, and they can send `BrowserTabChanged`. To detect a change the extension keeps a one-way SHA-256 digest of the current title (with any leading unread badge such as `(3)` removed) in memory; the title itself is never stored, logged, or sent. The digest is defense in depth rather than a hard boundary, since GNOME Shell already holds window titles, but it means no extension log or state dump contains a title in readable form. `BrowserTabChanged` carries no payload and reveals only *when* you changed tab or page; like every signal here, its timing is visible to other processes on your session bus.

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


## Emote catalogue shortcut

`Ctrl + Alt + E` opens Mochi's large emote collection window. Like the developer shortcut, GNOME Shell reduces the keybinding to a zero-payload semantic D-Bus signal; Mochi never receives the pressed keys themselves.
