# Mochi 🌱 Wiki

> **A tiny friend for your Linux desktop.**

Mochi is a small pixel-art Linux desktop companion built to feel like a quiet little creature living on the desktop rather than a dashboard, widget, or chatbot.

Mochi is in early alpha. The focus is interaction quality, input reliability,
and public-alpha readiness, tracked in [issue #37](https://github.com/miflow13/mochi-desktop/issues/37).
The [current known issues](../../README.md#known-issues) include unresolved
workspace/Overview freezing (#45) and drag-direction latency (#68).

## What Mochi is

Mochi is designed to be:

- cute, expressive, and unobtrusive
- lightweight enough to leave running
- responsive to clicks, dragging, sleep/wake actions, and contextual actions
- visually consistent pixel art with crisp nearest-neighbor rendering
- Linux-native, with Fedora + GNOME as the primary development environment

The project intentionally keeps the creature core small. Systems such as health, hunger, XP, shops, accessories, and deeper progression belong to later phases, not the current alpha foundation.

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

The interaction core is the immediate priority:

```text
IDLE
├── click → SQUISH → IDLE
├── double-click → HEART → IDLE
├── ambient → TYPING → IDLE
├── context menu → WALK / SLEEP / EMOTE / COMPUTER
└── PICKUP → HELD / DRAG → PUT_DOWN → IDLE
```

The most important rule underneath every interaction is simple:

> **Mochi must always recover and remain interactable.**

Every temporary animation state needs a deterministic exit path. Direct user input takes priority over ambient behavior. A feature is not complete if it looks correct but leaves Mochi unable to click, drag, right-click, wake, or return to idle.

## Canonical visual rules

Mochi's runtime art uses a fixed pixel-art presentation:

- 128×128 logical runtime canvas
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

Package/runtime metadata is `0.2.0a0`. Published release labels have
[documented discrepancies](../../CHANGELOG.md#release-metadata-note); use the
tested commit to identify a build. This wiki's dated handoffs and conceptual
roadmaps are not evidence that a feature shipped or a release gate passed.

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
