# mochi 🌱

[![tests](https://github.com/miflow13/mochi-desktop/actions/workflows/tests.yml/badge.svg)](https://github.com/miflow13/mochi-desktop/actions/workflows/tests.yml)

<img width="800" height="475" alt="Mochi desktop companion" src="https://github.com/user-attachments/assets/f2030934-4153-4c03-9b84-350505b9f75e" />

*A tiny Deskling companion for Linux.*

[website](https://miflow13.github.io/mochi-desktop/) · [documentation](docs/README.md) · [issues](https://github.com/miflow13/mochi-desktop/issues) · [changelog](CHANGELOG.md) · [animation guide](assets/mochi/README.md)

> [!WARNING]
> **First install on GNOME Wayland:** log out and back in once after installing Mochi. This activates the GNOME Shell helper used for typing, app, file, and focused-media reactions.

## What is Mochi?

Mochi is a small Linux desktop companion built to feel expressive, contextual, and pleasant to leave running.

He wanders, reacts to clicks and dragging, sleeps, notices broad desktop activity through **AmbiSense**, and occasionally has something to say. Most of the work is in the details: animation timing, movement, persistence, speech pacing, state transitions, input behavior, and knowing when not to interrupt.

Mochi is intentionally **not** a productivity score, streak system, nagging assistant, or requirement to interact. You can ignore him completely and let him do his little thing.

Mochi is currently an **early public alpha**. Fedora + GNOME + Wayland is the primary tested environment.

## Install

### Fedora + GNOME

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

The installer creates Mochi's private Python environment, installs the GNOME helper, adds Mochi to the application grid, and installs `mochi` / `mochi-uninstall` launchers under `~/.local/bin`.

After the first install on GNOME Wayland, log out and back in once, then launch Mochi normally.

### Fedora + Niri

Niri support is experimental. The installer includes Fedora's `gtk4-layer-shell` package. After updating an existing installation, run `./install.sh` again and start Mochi once with:

```bash
mochi --reset-position
```

### Update

```bash
git pull
./install.sh
```

### Uninstall

```bash
~/.local/bin/mochi-uninstall
```

Remove saved settings too:

```bash
~/.local/bin/mochi-uninstall --purge
```

For installation and troubleshooting details, see the [Getting Started](docs/wiki/Getting-Started.md) and [Troubleshooting](docs/wiki/Troubleshooting-and-Regressions.md) guides.

## Current status

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — *Make Mochi Feel Alive*

Working now:

- idle / breathing + natural blink
- walking + persistent **Stay put**
- pickup, velocity-aware drag + drop
- bounce / squish / heart reactions
- click chirps + triple-click dialogue
- sleep / wake behavior
- typing + media companion states
- AmbiSense ambient dialogue
- multi-monitor / XWayland reliability work

Still growing:

- more ambient idle emotes
- animation-library polish
- broader Linux compatibility
- installation testing outside the primary development machines
- more AmbiSense contexts

See the [changelog](CHANGELOG.md) for release-facing changes and the [development status](docs/wiki/Current-Development-Status.md) for deeper project notes.

## Interactions

- **Left-click** — tactile bounce / squish + chirp
- **Three quick clicks** — occasional tiny dialogue
- **Double-click** — heart emote
- **Drag** — pick Mochi up and move him around
- **Right-click** — size, audio, sleep/wake, **Stay put**, and Quit
- **Stay put** — disables autonomous wandering without freezing other behavior
- **Mochi Lab** — developer controls for animations and AmbiSense tuning

## AmbiSense

**AmbiSense** is Mochi's lightweight, local ambient-awareness system. It turns privacy-reduced desktop signals into small behavior decisions without reading the content of what you type.

Depending on the desktop environment and available helpers, Mochi can react to broad signals such as typing activity, active/idle presence, coarse app categories, media playback, battery changes, network transitions, and file-browsing activity.

AmbiSense is a **local rule-based behavior engine**, not an LLM or cloud AI service.

Typing awareness is content-blind: Mochi does not store characters, inspect typed text, reconstruct words, log key values, or persist typing history.

Read the [AmbiSense documentation](docs/ambisense.md) for the event flow, privacy model, and implementation boundary.

## Art and animation

All Mochi pixel art, animations, and audio are created by the maintainer.

Sprites are handcrafted frame by frame in [Pixelorama](https://github.com/orama-interactive/pixelorama), with attention to silhouette, timing, squash and stretch, and small expressions that keep the character readable at desktop scale.

Runtime artwork lives under `assets/mochi/` and is defined by `assets/mochi/manifest.json`.

See the [animation and asset guide](assets/mochi/README.md) for frame, naming, looping, export, and validation rules.

## Engineering

Mochi is also a hands-on Linux software-engineering project. Current work includes:

- state-driven behavior for idle, movement, reactions, sleep, media, typing, and interaction transitions
- privacy-first event and context handling through AmbiSense
- manifest-driven sprite assets with runtime inventory validation
- per-frame animation timing with cached Cairo surfaces and nearest-neighbor rendering
- persistent configuration for placement and preferences
- GTK4 transparent desktop integration
- GNOME Wayland + XWayland compatibility work around positioning, input, menus, workspaces, and multiple monitors
- D-Bus / event-driven system awareness where appropriate
- automated regression tests around interaction and animation behavior

**Stack:** Python 3 · GTK4 / PyGObject · Cairo · GNOME Shell helper · XWayland

For the deeper architecture, see [Architecture and Tech Stack](docs/wiki/Architecture-and-Tech-Stack.md), [Interaction Core](docs/wiki/Interaction-Core.md), and [Development and Testing](docs/wiki/Development-and-Testing.md).

## Support boundary and known limitations

The current alpha intentionally has a narrow support boundary while the interaction and state systems are stabilized.

- **Fedora + GNOME + Wayland is the primary tested target.** Other Linux distributions may work, but automatic dependency installation currently supports Fedora only.
- **GNOME gets the fullest AmbiSense experience.** Other desktops may have reduced desktop-awareness features.
- **A one-time GNOME logout/login may be required after first install** so the newly installed Shell helper becomes active.
- **Mochi uses XWayland for parts of desktop positioning and interaction on GNOME Wayland.** Monitor layout, scaling, compositor, and workspace behavior can expose edge cases.
- **Workspace-switch reliability is still being watched.** See [issue #45](https://github.com/miflow13/mochi-desktop/issues/45).
- **Niri support is experimental** and receives less regression testing than GNOME.
- **Multi-monitor and fractional-scaling combinations are not exhaustively tested.**
- **There is no stable compatibility promise yet.** Alpha configuration, behavior, or installation details may change between prereleases.

If something fails quietly rather than crashing, it is still worth reporting. Ambient-awareness failures are designed to degrade gracefully, so a missing reaction can be useful debugging information.

## Roadmap

| version | focus |
| --- | --- |
| **v0.1 — Exists** | core desktop buddy functionality |
| **v0.2 — Feels alive** | animation polish, AmbiSense, reactions, contextual behavior, reliability, public alpha |
| **v0.3 — Needs care** | lightweight care / progression without turning Mochi into a chore |
| **v0.4 — Develops personality** | more behaviors, expressions, traits, and cosmetic personality |
| **v0.5 — Lives on your desktop** | deeper Linux desktop interactions and broader environment support |

## Development process

Mochi is developed in focused branches with regression tests and live Linux desktop verification before changes are considered complete. Runtime behavior involving GTK, Wayland/XWayland, state transitions, input, or animation is treated as requiring real-environment QA in addition to automated tests.

AI coding tools may assist with investigation, debugging, refactoring, review, and test generation. Architecture, product direction, original artwork/audio, review, and final implementation decisions remain maintainer-directed. Contributors are expected to understand and verify any code they submit.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [REGRESSION_WATCHLIST.md](REGRESSION_WATCHLIST.md) for the project workflow and verification expectations.

## Contributing

Bug reports, focused pull requests, and testing notes are welcome—especially reports that include the desktop environment, compositor, monitor/scaling setup, and clear reproduction steps.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
