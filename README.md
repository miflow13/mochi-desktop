# Mochi 🌱



<img width="1130" height="790" alt="Screenshot From 2026-09-08 21-05-33" src="https://github.com/user-attachments/assets/7b15c5ce-2ac3-4026-a37c-2ac13d2c6250" />




Mochi is a small Linux desktop companion currently under active development.

The project is still experimental and is **not ready for public release yet**.
Features, artwork, behavior, architecture, and documentation may change
significantly while development continues.


## Current status

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — Make Mochi Feel Alive

- ✅ Core desktop buddy MVP
- ✅ Idle / breathing animation
- ✅ Natural blink behavior
- ✅ Bounce / squish reactions
- ✅ Manifest-driven 128×128 pixel-art assets
- ✅ Two-dimensional wandering
- ✅ Dangling drag animation
- 🚧 Walking polish
- 🚧 Sleep / wake polish
- ⏳ Nametag / status UI
- ⏳ Desktop reliability testing

<p align="center">
<img width="738" height="592" alt="mochi_demo1mp4 (2)" src="https://github.com/user-attachments/assets/79e7eb9b-8c14-4c22-86eb-fc7ea9878451" />
</p>


Mochi has a transparent, undecorated window; a right-click menu for sleep,
size, position reset, and quitting; persistent configuration; and cached,
nearest-neighbor animation rendering. He chooses occasional quiet idle actions,
wanders around the screen, and falls asleep after extended inactivity.

## Development goals

Phase 2 is focused on making Mochi feel like a small creature peacefully living
on the desktop. Mochi should remain quiet, cozy, playful, lightweight,
expressive, and unobtrusive.

## Planned roadmap
<p align="center">
  <img width="220" height="220" alt="Mochi squish animation" src="https://github.com/user-attachments/assets/be1abde7-8379-4923-98a7-68dcaf41d7b0" />
  &nbsp;&nbsp;
  <img width="220" height="220" alt="Mochi bounce animation" src="https://github.com/user-attachments/assets/68a79eb4-81f1-47cf-8891-1211bb1f8726" />
  &nbsp;&nbsp;
  <img width="220" height="220" alt="Mochi wake animation" src="https://github.com/user-attachments/assets/862b0ca0-8ec6-4ebd-a67a-0d9ad4a02b4c"![Uploading sprite-animation (2).gif…]()
 />
</p>

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
├── animation-gifs/
├── assets/
│   └── mochi/
├── src/
│   └── mochi/
├── tests/
├── tools/
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

Useful commands:

```bash
mochi --debug
mochi --reset-position
mochi --preview-animations
python3 -m unittest discover -s tests -v
python3 tools/export_animation_gifs.py
```

## Animation architecture

`sprite_loader.py` reads the authoritative asset manifest and loads every fixed
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
- `app.py`: GTK application and window setup
- `config.py`: JSON persistence

When adding or replacing art, update `assets/mochi/manifest.json`. Sprite paths
remain isolated from input and behavior code.
