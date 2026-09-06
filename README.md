# Mochi 🌱

A tiny friend for your Linux desktop.

Mochi is a lightweight animated desktop buddy that hangs out while you work,
write, code, or browse.

> Mochi is early experimental software. v0.1 is intentionally tiny and its
> Linux desktop integration is still evolving.

## Current vertical slice

- An original pixel-art Mochi in a transparent, undecorated 128 px window
- A real pixel-art sprite atlas with idle, blink, walk, reaction, and sleep poses
- Three quiet click reactions: bounce, squish, and excited
- A right-click menu with **Sleep/Wake**, **Reset Position**, and **Quit Mochi**
- Bounded layer-shell dragging with position restored between launches
- A focused animation player and explicit state machine ready for more states
- JSON configuration support at `~/.config/mochi/config.json`
- Debug state-transition logging with `--debug`

Mochi also chooses occasional quiet idle actions, walks a bounded horizontal
distance, and falls asleep after two minutes without interaction.

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
mochi --preview-animations
```

## How the first slice works

`app.py` creates a borderless, non-focusable GTK window and removes GTK's themed
background with transparent CSS. `sprites.py` loads the 1448×1086 RGBA sheet
once, crops the 25 explicit (non-grid) frame rectangles in memory, and keeps the
resulting Cairo surfaces cached for Mochi's lifetime. Caching avoids decoding the PNG
and allocating new crops on every frame.

GTK calls the animation player every 16 ms. Elapsed time accumulates until the
animation's frame duration is reached; only then does the player advance. The
drawing widget renders the cached crop at exactly ½ scale with Cairo's `NEAREST`
filter, keeping pixel edges crisp instead of interpolating them.

Animation definitions contain a name, ordered frames, duration, loop flag, and
next animation. The state machine describes behavior (`WALKING`, `SLEEPING`, and
so on), while the player describes what is visible. A blink decision changes the
behavior state to `BLINKING`; the completed `blink` animation then selects its
declared `idle` successor.

A small pointer movement begins a drag. With layer shell, the drag updates
lower-left edge margins; on GNOME/XWayland it uses the compositor's native move.
Both paths save the final position. Walking interpolates between a clamped start
and target while the six-frame walk loop plays. A release without movement is a
click and randomly selects bounce, squish, or excited.

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
- always-on-top placement is not guaranteed on native Wayland;
- absolute position save/restore and walking need layer shell or XWayland;
- the compositor may show the window in its normal placement policy at launch.

On X11, layer shell reports unsupported and Mochi uses that fallback. X11
compositors may offer more placement freedom, but GTK4 still encourages
compositor-managed movement.

## Development

Run the test suite with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

To preview the sprite animations, launch the developer mode and left-click Mochi
to advance through Idle, Blink, Walk, Bounce, Squish, Excited, Sleep, and Wake:

```bash
PYTHONPATH=src python3 -m mochi --preview-animations --debug
```

When adding new art later, edit `FRAME_RECTANGLES` and `ANIMATIONS` in
`src/mochi/sprites.py`. Input, timing, and behavior code do not need to know where
a pose lives in the sheet.

Key modules are deliberately small:

- `state.py`: named states and logged transitions
- `animation.py`: frames and time-based playback
- `sprites.py`: atlas rectangles, animation definitions, loading, and rendering
- `behavior.py`: randomized behavior choices
- `buddy.py`: input, behavior timing, and animation/state coordination
- `app.py`: GTK application/window setup
- `config.py`: robust JSON persistence

## Roadmap

- **v0.1:** refine timing and clean source-art edge artifacts if desired
- **v0.2:** richer sprites and moods, configurable idle timing, sound toggle
- **v0.3:** screen-edge sitting and gentle window awareness
- **v0.4:** character skins and accessories
- **v1.0:** polished animations, settings, and Fedora/Linux packages
# mochi-desktop
