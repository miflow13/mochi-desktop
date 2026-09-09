<div align="center">

# Mochi 🌱

### Your new Deskling Companion

<img width="800" height="475" alt="Mochi desktop companion" src="https://github.com/user-attachments/assets/afb00fa1-2983-4a45-b387-b75ad2b3ee60" />

**A tiny pixel-art companion quietly living on your Linux desktop.**

</div>

Mochi is a small Linux desktop companion currently under active development. He idles, reacts, wanders, sleeps, and generally tries to make your desktop feel a little more alive without getting in the way.

> [!IMPORTANT]
> Mochi is currently in **alpha development** and is not ready for a public release yet. Features, artwork, behavior, architecture, and documentation may change significantly while development continues.

---

<h2><img width="48" height="48" alt="Mochi being picked up" src="https://github.com/user-attachments/assets/dee6a7c8-2f70-475a-ae3b-74f1b959dbc6" /> Current status</h2>

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — *Make Mochi Feel Alive*

| Working now | In progress |
| --- | --- |
| ✅ Core desktop buddy MVP | 🚧 Walking polish |
| ✅ Idle / breathing behavior | 🚧 Sleep / wake polish |
| ✅ Natural blink behavior | 🚧 Pickup + drag animation refresh |
| ✅ Bounce / squish reactions | ⏳ New hover interaction UI |
| ✅ Manifest-driven pixel-art assets | ⏳ Desktop reliability testing |
| ✅ Two-dimensional wandering | |

<p align="center">
  <img width="738" height="592" alt="Mochi desktop demo" src="https://github.com/user-attachments/assets/79e7eb9b-8c14-4c22-86eb-fc7ea9878451" />
</p>

Mochi runs in a transparent, undecorated desktop window with persistent configuration, cached animation rendering, and crisp nearest-neighbor pixel scaling. He chooses occasional quiet idle actions, wanders around the screen, and falls asleep after extended inactivity.

A **right-click developer menu** is currently retained for testing while the future user-facing hover interaction is redesigned.

---

## Design goal

Phase 2 is focused on making Mochi feel less like a widget and more like a tiny creature peacefully sharing your desktop.

Mochi should stay:

**quiet · cozy · playful · lightweight · expressive · unobtrusive**

---

## Roadmap

<p align="center">
  <img width="220" height="220" alt="Mochi squish animation" src="https://github.com/user-attachments/assets/be1abde7-8379-4923-98a7-68dcaf41d7b0" />
  &nbsp;&nbsp;
  <img width="220" height="220" alt="Mochi bounce animation" src="https://github.com/user-attachments/assets/68a79eb4-81f1-47cf-8891-1211bb1f8726" />
  &nbsp;&nbsp;
  <img width="220" height="220" alt="Mochi wake animation" src="https://github.com/user-attachments/assets/862b0ca0-8ec6-4ebd-a67a-0d9ad4a02b4c" />
</p>

| Version | Focus |
| --- | --- |
| **v0.1 — Exists** | ~~Core desktop buddy functionality~~ |
| **v0.2 — Feels alive** | Animation polish, reactions, sleep/wake behavior, interaction polish, and reliability |
| **v0.3 — Needs care** | Health, fullness, feeding, XP, and leveling |
| **v0.4 — Develops personality** | Unlockable behaviors, expressions, traits, and cosmetic progression |
| **v0.5 — Lives on your desktop** | Deeper interactions with windows, cursor behavior, screen edges, and the desktop environment |

---

## Development environment

The primary target is **Fedora Linux with GNOME and Wayland**.

Mochi is built with:

- Python
- GTK4
- PyGObject
- Cairo
- XWayland where GNOME's native Wayland restrictions require it

### Installation

Install Fedora runtime packages:

```bash
sudo dnf install python3 python3-gobject gtk4 gtk4-layer-shell
```

Install Mochi from the checkout and launch it:

```bash
python3 -m pip install -e .
mochi
```

Useful development commands:

```bash
mochi --debug
mochi --reset-position
mochi --preview-animations
python3 -m unittest discover -s tests -v
python3 tools/export_animation_gifs.py
```

---

<details>
<summary><strong>Project structure</strong></summary>

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

</details>

<details>
<summary><strong>Animation architecture</strong></summary>

`sprite_loader.py` reads the authoritative asset manifest and loads every fixed RGBA frame once. `sprites.py` retains those cached Cairo surfaces, while `animation.py` advances them using per-frame durations. Rendering uses nearest-neighbor filtering and bottom-center anchoring throughout.

Key modules:

- `state.py` — named behavior states and logged transitions
- `animation.py` — frames and time-based playback
- `sprite_loader.py` — manifest validation and one-time PNG loading
- `sprites.py` — animation mapping, cached surfaces, and rendering
- `behavior.py` — weighted behavior choices
- `buddy.py` — input, timers, movement, and state coordination
- `app.py` — GTK application and window setup
- `config.py` — JSON persistence

When adding or replacing art, update `assets/mochi/manifest.json`. Sprite paths remain isolated from input and behavior code.

</details>

---

<div align="center">

### 🌱 Mochi is growing.

*Built one tiny interaction at a time.*

</div>
