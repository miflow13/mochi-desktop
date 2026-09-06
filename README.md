# Mochi 🌱

A tiny friend for your Linux desktop.

Mochi is a lightweight animated desktop buddy that hangs out while you work,
write, code, or browse.

> Mochi is early experimental software. v0.1 is intentionally tiny and its
> Linux desktop integration is still evolving.

## Current vertical slice

- An original, code-drawn 128 px Mochi in a transparent, undecorated window
- Three quiet click reactions: blink, bounce, and squish
- A right-click menu with **Sleep/Wake**, **Reset Position**, and **Quit Mochi**
- Bounded layer-shell dragging with position restored between launches
- A focused animation player and explicit state machine ready for more states
- JSON configuration support at `~/.config/mochi/config.json`
- Debug state-transition logging with `--debug`

Automatic sleep, autonomous behavior, and walking are the next v0.1 increments;
they are not in this first slice.

## Installation

On Fedora, install the runtime packages:

```bash
sudo dnf install python3 python3-gobject gtk4 gtk4-layer-shell
```

Run directly from a checkout without installing:

```bash
PYTHONPATH=src python3 -m mochi
```

Or install it into a virtual environment/system environment, then run `mochi`:

```bash
python3 -m pip install -e .
mochi
```

Useful options:

```bash
mochi --debug
mochi --reset-position
```

## How the first slice works

`app.py` creates a borderless, non-focusable GTK window and applies transparent
CSS. `buddy.py` draws only the character and shadow with Cairo, so the compact
128 px window visually disappears around it.

GTK calls the animation player every 16 ms. The player changes frames according
to each animation's own frame duration, while the drawing widget only renders
the current frame. A finished reaction moves the explicit state machine back to
`IDLE`. This separation is what will let PNG frames replace the Cairo drawing.

A small pointer movement begins a drag. With layer shell, the drag updates
lower-left edge margins and clamps them to the monitor. Mochi saves those margins
on release and restores them at launch. A release without movement is a click and
randomly selects a blink, bounce, or squish.

## Wayland notes

Wayland deliberately prevents ordinary applications from choosing or reading
absolute top-level window positions. Mochi therefore uses `gtk4-layer-shell`
when the running compositor supports the protocol. It creates a top-layer surface
with no keyboard focus or reserved screen space, anchored from the lower-left so
margins act as safe coordinates.

**Fedora GNOME limitation:** GNOME's Mutter compositor does not currently expose
the layer-shell protocol, even when the `gtk4-layer-shell` library is installed.
On a GNOME Wayland session, Mochi automatically runs its small buddy window
through XWayland. This mirrors the Linux Codex pet's split approach: only the pet
uses X11 compatibility while the desktop and other applications remain native
Wayland. Set `MOCHI_NATIVE_WAYLAND=1` to test the native fallback.
Layer shell remains available on supporting Wayland compositors.

If layer shell is unavailable, the GTK fallback still launches and:

- user-initiated dragging works;
- always-on-top placement is not guaranteed;
- absolute position save/restore and programmatic walking cannot be reliable;
- the compositor may show the window in its normal placement policy at launch.

On X11, layer shell reports unsupported and Mochi uses that fallback. X11
compositors may offer more placement freedom, but GTK4 still encourages
compositor-managed movement.

## Development

The non-GUI tests use only the standard library:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Key modules are deliberately small:

- `state.py`: named states and logged transitions
- `animation.py`: frames and time-based playback
- `behavior.py`: reaction definitions and choices
- `buddy.py`: input and placeholder rendering
- `app.py`: GTK application/window setup
- `config.py`: robust JSON persistence

## Roadmap

- **v0.1:** safe walking, sleep and idle behavior, and a right-click menu
- **v0.2:** richer sprites and moods, configurable idle timing, sound toggle
- **v0.3:** screen-edge sitting and gentle window awareness
- **v0.4:** character skins and accessories
- **v1.0:** polished animations, settings, and Fedora/Linux packages
# mochi-desktop
