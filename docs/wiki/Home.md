# Mochi 🌱 Wiki

> **A tiny friend for your Linux desktop.**

Mochi is a small pixel-art Linux desktop companion built to feel like a quiet little creature living on the desktop rather than a dashboard, widget, or chatbot.

Mochi is in early public alpha. The current v0.3 line adds persistent bond progression, feeding, bond-gated emotes, level-up feedback, and Focus with Mochi on top of the existing interaction core.

Release QA is tracked in [issue #37](https://github.com/miflow13/mochi-desktop/issues/37).
The [current known issues](../../README.md#known-issues) include unresolved
workspace/Overview freezing (#45) and drag-direction latency (#68).

## What Mochi is

Mochi is designed to be:

- cute, expressive, and unobtrusive
- lightweight enough to leave running
- responsive to clicks, dragging, sleep/wake actions, and contextual actions
- visually consistent pixel art with crisp nearest-neighbor rendering
- Linux-native, with Fedora + GNOME as the primary development environment

The project intentionally keeps care lightweight. v0.3 ships bond XP and positive feeding/focus rewards, but it still avoids punitive hunger/health decay, streaks, shops, and obligation-heavy progression.

## Wiki map

- [Getting Started](Getting-Started.md) — alpha installation guidance, editable development setup, and Wayland expectations
- [Development snapshot (2026-09-08)](Current-Development-Status.md) — historical WIP and checkpoint history
- [Architecture and Tech Stack](Architecture-and-Tech-Stack.md) — runtime, modules, rendering, packaging, and platform assumptions
- [Interaction Core](Interaction-Core.md) — the behaviors that define the public-alpha creature experience
- [Animation and Art Pipeline](Animation-and-Art-Pipeline.md) — assets, manifests, spritesheets, timing, and PixelLab/Pixelorama workflow
- [Development and Testing](Development-and-Testing.md) — development loop, validation gates, debugging, and release discipline
- [Troubleshooting and Regressions](Troubleshooting-and-Regressions.md) — known failure modes and what to check when Mochi becomes stuck
- [Contributing and Issues](Contributing-and-Issues.md) — issue-writing guidance, contribution scope, and acceptance criteria
- [Roadmap and Public Alpha](Roadmap-and-Public-Alpha.md) — current priorities, alpha definition of done, and later roadmap
- [Project Philosophy](Project-Philosophy.md) — the design rules that protect Mochi's identity and reliability

## Current development focus

v0.3 feature development is complete on `main`; the current focus is release stabilization and real-world tester feedback.

The interaction core now has to remain dependable while longer-lived v0.3 systems run around it:

```text
IDLE
├── click / heart / dialogue → reaction → IDLE
├── context menu → WALK / SLEEP / FEED / FOCUS / controls
├── PICKUP → DRAG → release-settle → IDLE
├── bond XP → LEVEL-UP / UNLOCK presentation → recover
└── FOCUS clock → writing/break presentation while direct input may interrupt visually
```

The most important rule underneath every interaction remains:

> **Mochi must always recover and remain interactable.**

Direct user input takes priority over ambient presentation. Bond, Focus, catalogue, and level-up features are not complete if they look correct but leave Mochi unable to click, drag, right-click, sleep/wake, or return to normal behavior.

## Canonical visual rules

Mochi's runtime art uses a fixed pixel-art presentation:

- 256×256 asset frames scaled to the configured runtime window
- bottom-center anchoring
- transparent RGBA artwork
- nearest-neighbor scaling only
- integer scale factors where possible
- cached frames rather than decoding PNGs every animation tick
- one canonical visual design; legacy artwork must not reappear through fallback paths

## Primary development environment

- Fedora Linux
- GNOME
- Wayland-first desktop environment
- XWayland where GNOME/Wayland restrictions require it
- Python 3
- GTK4 / PyGObject
- Cairo rendering

## Repository status note

Mochi is under active development, and local development work may temporarily be ahead of the default branch. Treat the current branch, issue tracker, test results, and explicit checkpoint commits as the authoritative source when debugging an in-progress feature.

Package/runtime metadata for the v0.3 release-prep line is `0.3.0a1` (the Python packaging form of `0.3.0-alpha.1`).

The earlier `v0.3.0-alpha` GitHub tag is an older development snapshot. Use the current README/changelog and the tested commit when identifying a build. This wiki's dated handoffs remain historical unless explicitly marked current.

## Development discipline

For runtime work, use this loop:

```text
one meaningful change
→ focused tests
→ full test suite
→ live visual/input test
→ clean Git checkpoint
→ next change
```

Avoid stacking unrelated refactors, art migrations, and interaction changes in one dirty working tree.

## Quick links

- Main repository: https://github.com/miflow13/mochi-desktop
- Issues: https://github.com/miflow13/mochi-desktop/issues
- Regression watchlist: ../../REGRESSION_WATCHLIST.md

---

Mochi's goal is not to do everything. The goal is to feel alive, dependable, and pleasant to share a desktop with. 🌱
