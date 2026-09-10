# Mochi Typing Activity GNOME Extension

This optional GNOME Shell extension gives Mochi broad keyboard **activity** detection on GNOME/Wayland.

It deliberately does **not** read, store, log, or transmit key symbols, keycodes, Unicode values, modifiers, shortcuts, passwords, or text. It only checks whether a captured Shell event is a key press and emits a zero-argument D-Bus `Pulse` signal.

## Local development install

From the Mochi repository root:

```bash
./scripts/install-typing-extension.sh
```

`gnome-extensions install` loads newly installed extensions in the next GNOME Shell session. On Wayland, log out and back in once after the first install, then enable it if needed:

```bash
gnome-extensions enable mochi-typing@miflow13
gnome-extensions info mochi-typing@miflow13
```

The expected state is `ACTIVE`.
