# Mochi 🌱

> Private development repository.

<p align="center">
  <img width="220" height="220" alt="Mochi squish animation" src="docs/previews/squish.gif" />
</p>

Mochi is a small Linux desktop companion currently under active development.

The project is still experimental and is **not ready for public release yet**.
Features, artwork, behavior, architecture, and documentation may change
significantly while development continues.

## Current status

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — Make Mochi Feel Alive

- ✅ Core desktop buddy MVP
- ✅ Idle / breathing animation
- ✅ Canonical PixelLab idle artwork
- ✅ Bounce / squish reactions
- ✅ Manifest-driven 128×128 pixel-art assets
- ✅ Two-dimensional wandering
- ✅ Dangling drag animation
- 🚧 Walking polish
- 🚧 Sleep / wake polish
- ⏳ Nametag / status UI
- ⏳ Desktop reliability testing

Mochi has a transparent, undecorated window; a right-click menu for sleep,
size, position reset, and quitting; persistent configuration; and cached,
nearest-neighbor animation rendering. He chooses occasional quiet idle actions,
wanders around the screen, and falls asleep after extended inactivity.
Optional interaction sounds use replaceable files under `assets/audio/` and are
silently skipped when those files are absent.

## Development goals

Phase 2 is focused on making Mochi feel like a small creature peacefully living
on the desktop. Mochi should remain quiet, cozy, playful, lightweight,
expressive, and unobtrusive.

> There is a tiny creature peacefully living on your desktop.

## Canonical artwork

PixelLab Mochi is the only canonical character design. Runtime character art
lives under `assets/mochi/` and is declared by its single `manifest.json`.
New animations must match the PixelLab design, use normalized transparent
128×128 canvases, retain bottom-center anchoring, and use nearest-neighbor
scaling.

Until matching PixelLab animation frames are supplied, blink, walk, bounce,
sleep, wake, excited, hurt/sad, curious, and sit intentionally display the
canonical neutral idle frame while their existing behavior continues. Squish
and velocity-based drag use their dedicated PixelLab artwork.

## Planned roadmap

### v0.1 — Exists

Core desktop buddy functionality.

### v0.2 — Feels alive

Animation polish, reactions, sleep/wake behavior, status UI, and desktop reliability.

### v0.3 — Needs care

Health, fullness, feeding, XP, and leveling.

### v0.4 — Develops personality

Unlockable behaviors, expressions, traits, and cosmetic progression.

### v0.5 — Lives on your desktop

Deeper interactions with windows, cursor behavior, screen edges, and the desktop environment.

## Development environment

The primary target is Fedora Linux with GNOME and Wayland. Mochi uses Python,
GTK4, PyGObject, and XWayland where GNOME's native Wayland restrictions require it.

## Project structure

```text
mochi-desktop/
├── assets/
│   ├── audio/
│   └── mochi/           # authoritative animation frames and manifest
├── docs/
│   └── previews/
├── scripts/
│   └── art/
├── src/
│   └── mochi/
├── tests/
├── README.md
└── pyproject.toml
```

## Installation

Install Fedora runtime packages:

```bash
sudo dnf install python3 python3-gobject gtk4 gtk4-layer-shell
```

Install Mochi from the checkout and launch it:

```bash
python3 -m pip install -e .
mochi
```

Install the optional development dependency with
`python3 -m pip install -e '.[dev]'` when regenerating sprites or preview GIFs.

Useful commands:

```bash
mochi --debug
mochi --reset-position
mochi --preview-animations
python3 -m unittest discover -s tests -v
python3 scripts/export_animation_gifs.py
```

## Animation architecture

`sprite_loader.py` reads the authoritative PixelLab asset manifest and loads every fixed
128×128 RGBA frame once. `sprites.py` retains those cached Cairo surfaces, while
`animation.py` advances them using per-frame durations. Rendering uses nearest-
neighbor filtering and bottom-center anchoring throughout.

Key modules:

- `state.py`: named behavior states and logged transitions
- `animation.py`: frames and time-based playback
- `sprite_loader.py`: manifest validation and one-time PNG loading
- `sprites.py`: animation mapping, cached surfaces, and rendering
- `behavior.py`: weighted behavior choices
- `buddy.py`: input, timers, movement, and state coordination
- `drag_motion.py`: velocity-based dangling pose selection while dragging
- `sound.py`: optional, centralized interaction audio playback
- `status.py` / `status_overlay.py`: status presentation state and GTK overlay
- `app.py`: GTK application and window setup
- `config.py`: JSON persistence

When adding or replacing art, update `assets/mochi/manifest.json`. Do not add
legacy or alternate Mochi designs as fallbacks; Git history provides historical
recovery. Sprite paths remain isolated from input and behavior code.
