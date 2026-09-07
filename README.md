# Mochi 🌱

> Private development repository.

Mochi is a small Linux desktop companion currently under active development.
<img width="512" height="512" alt="squish" src="https://github.com/user-attachments/assets/e1f84167-e764-4fd3-842e-298931eecabd" />


The project is still experimental and is **not ready for public release yet**. Features, artwork, behavior, architecture, and documentation may change significantly while development continues.

## Current status

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — Make Mochi Feel Alive

Current focus:

- ✅ Core desktop buddy MVP
- ✅ Idle / breathing animation
- ✅ Blink behavior
- 🚧 Bounce / squish reactions
- ⏳ Walking polish
- ⏳ Sleep / wake transitions
- ⏳ Animation transition polish
- ⏳ Nametag / status UI
- ⏳ Desktop reliability testing

## Current development goals

Phase 2 is focused on making Mochi feel like a small creature peacefully living on the desktop.

The priority is:

- subtle animation
- expressive reactions
- smooth state transitions
- crisp pixel rendering
- low resource usage
- non-intrusive desktop behavior

## Development principles

Mochi should feel:

- quiet
- cozy
- playful
- lightweight
- expressive
- unobtrusive

The goal is not to make an assistant that constantly demands attention.

The goal is:

> There is a tiny creature peacefully living on your desktop.

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

Primary target:

- Linux
- Fedora
- GNOME
- Wayland

Current implementation uses Python and GTK4/PyGObject.

## Project structure

```text
mochi-desktop/
├── assets/
│   └── mochi/
├── docs/
├── src/
│   └── mochi/
├── tests/
├── README.md
└── pyproject.toml
