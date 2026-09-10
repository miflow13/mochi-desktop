<div align="center">

# Mochi 🌱

### Your new Deskling Companion

<img width="800" height="475" alt="Mochi on the Linux desktop" src="https://github.com/user-attachments/assets/d64b6900-3120-4174-9ec6-a40688fe921a" />

**A tiny pixel-art companion quietly living on your Linux desktop.**

</div>

Mochi is a lightweight Linux desktop companion that idles, reacts, wanders, sleeps, and generally tries to make the desktop feel a little more alive without becoming another thing demanding your attention.

> [!IMPORTANT]
> Mochi is currently in **alpha development**. The first public alpha is planned for **September 21, 2026**. If you'd like to follow development, **star or watch this repository** for updates.

---

<h2><img width="48" height="48" alt="Mochi being picked up" src="https://github.com/user-attachments/assets/dee6a7c8-2f70-475a-ae3b-74f1b959dbc6" /> Current Status</h2>

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — *Make Mochi Feel Alive*

| Working now | In progress |
| --- | --- |
| ✅ Core desktop buddy MVP | 🚧 Walking polish |
| ✅ Idle / breathing behavior | 🚧 Sleep / wake polish |
| ✅ Natural blink behavior | ✅ Pickup + drag animation refresh |
| ✅ Bounce / squish reactions | ⏳ New hover interaction UI |
| ✅ Manifest-driven pixel-art assets | ⏳ Desktop reliability testing |
| ✅ Two-dimensional wandering | |

<p align="center">
  <img width="738" height="592" alt="Mochi desktop demo" src="https://github.com/user-attachments/assets/79e7eb9b-8c14-4c22-86eb-fc7ea9878451" />
</p>

---

## Why Mochi?

Desktop pets already exist. Mochi is an experiment in making one feel **quietly useful, expressive, and native to the Linux desktop** rather than like a video playing on top of it.

The project is intentionally focused on small interaction details: animation timing, state transitions, cursor reactions, movement, persistence, and knowing when *not* to interrupt the user.

The long-term goal is a companion that develops personality and useful desktop behaviors while staying lightweight and unobtrusive.

---

## Handcrafted With Love

<div align="center">

<img width="800" alt="Mochi animation being handcrafted in Pixelorama" src="https://github.com/user-attachments/assets/8c3492d7-7be7-4d9a-9a0d-9028dd75154b" />

*Every pixel. Every frame. A little bit of personality.*

</div>

Mochi's sprites and animations are **handcrafted with love**, built and refined frame by frame with careful attention to silhouette, timing, squash and stretch, and the tiny expressions that make Mochi feel alive.

The goal isn't simply to make Mochi move — it's to make every movement feel unmistakably **Mochi**.

---

## Engineering Highlights

Mochi is also a hands-on software-engineering project. Current work includes:

- **State-driven behavior** for idle, movement, reactions, sleep, and interaction transitions
- **Manifest-driven sprite assets** so artwork can change without coupling animation files to behavior code
- **Per-frame animation timing** with cached Cairo surfaces and nearest-neighbor rendering
- **Persistent configuration** for desktop placement and user settings
- **GTK4 desktop integration** with transparent, undecorated windows
- **Wayland/XWayland compatibility work** around Linux desktop window-management constraints
- **Automated tests and asset validation** to keep behavior and animation changes from silently breaking existing states

Mochi's visual design is simple on purpose; much of the engineering challenge is making that small character feel responsive and consistent.

---

## Design Goal

Phase 2 is focused on making Mochi feel less like a widget and more like a tiny creature peacefully sharing your desktop.

Mochi should stay:

**quiet · cozy · playful · lightweight · expressive · unobtrusive**

A right-click developer menu is currently retained for testing while the future user-facing interaction UI is redesigned.

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

## Tech Stack

The primary target is **Fedora Linux with GNOME and Wayland**.

Mochi is built with:

- Python
- GTK4 / PyGObject
- Cairo
- XWayland where GNOME's native Wayland restrictions require it

---

## Development Notes

<details>
<summary><strong>Project Structure</strong></summary>

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
<summary><strong>Animation Architecture</strong></summary>

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

## Contributing & Feedback

Mochi is early-stage software, so bug reports, Linux desktop compatibility notes, design feedback, and ideas are welcome through [GitHub Issues](https://github.com/miflow13/mochi-desktop/issues).

If you're interested in the project, **star or watch the repository** to follow Mochi's progress toward the September 21 alpha.

Licensed under the **MIT License**.

---

<div align="center">

### 🌱 Mochi is growing.

*Built one tiny interaction at a time.*

</div>
