# Roadmap and Public Alpha

Mochi's roadmap is intentionally staged. The public alpha should prove that the creature core is dependable before adding deeper care/progression systems.

## Current phase

**Phase 2 — Make Mochi Feel Alive**

Current priorities:

- interaction continuity
- animation polish
- reliable click/double-click behavior
- pickup/drag/drop
- context-menu stability
- walk polish
- sleep/wake reliability
- a small set of expressive emotes
- visual consistency
- packaging and desktop reliability

## Public alpha goal

The public alpha does **not** need every future Mochi feature.

It needs a small, polished, dependable companion that users can install, interact with, and leave running without obvious breakage.

### Public-alpha creature core

```text
IDLE
├── click → reaction → IDLE
├── double-click → HEART → IDLE
├── ambient → TYPING → IDLE
├── context menu → WALK / SLEEP / EMOTE / COMPUTER
└── PICKUP → HELD / DRAG → PUT_DOWN → IDLE
```

## Alpha blockers

Do not call the build public-alpha ready while any of these are reproducible:

- crash during ordinary interaction
- permanent input freeze
- context menu cannot reopen
- drag cannot recover after another action
- pickup/put-down can leave Mochi stuck
- one-shot animation leaves behavioral state invalid
- ambient timers multiply or fight direct input
- legacy/noncanonical art appears unexpectedly
- baked checkerboard/obvious gray matte appears in runtime art
- package installs with wrong/missing runtime assets
- normal runtime requests remote-desktop/screen-control permissions

## Alpha definition of done

### Startup

- [ ] clean launch on target Fedora/GNOME environment
- [ ] canonical Mochi appears immediately
- [ ] transparent undecorated presentation works
- [ ] no unexpected permission prompts
- [ ] no immediate GTK/Python errors

### Idle

- [ ] idle/breathing loop is stable
- [ ] blink returns to true `IDLE`
- [ ] ambient behavior is low-frequency and interruptible
- [ ] no duplicate idle timers

### Clicks

- [ ] single click produces tactile reaction
- [ ] single-click reaction returns to idle
- [ ] double-click produces heart reaction
- [ ] double-click cancels pending single-click reaction
- [ ] input remains responsive afterward

### Drag

- [ ] pickup transition is seamless
- [ ] held/drag state remains responsive
- [ ] visual inertia is subtle
- [ ] drop position remains accurate
- [ ] put-down transition is seamless
- [ ] quick release recovers safely
- [ ] immediate re-grab works

### Context menu

- [ ] opens repeatedly
- [ ] closes before behavior dispatch
- [ ] Walk works
- [ ] Sleep/Wake works
- [ ] Emote works
- [ ] Computer works
- [ ] later click/right-click/drag still works

### Visual integrity

- [ ] crisp nearest-neighbor rendering
- [ ] no legacy Mochi art
- [ ] no checkerboards
- [ ] no gray halo/matte
- [ ] canonical eye highlights
- [ ] bottom-center anchoring
- [ ] transition endpoints do not pop

### Reliability

- [ ] full test suite passes
- [ ] Python compilation passes
- [ ] `git diff --check` passes
- [ ] fresh wheel builds
- [ ] packaged assets audited
- [ ] extended live soak passes
- [ ] no stuck states observed
- [ ] no timer/input lock observed

### Documentation

- [ ] installation instructions match actual package
- [ ] version metadata reconciled
- [ ] issue template exists
- [ ] regression watchlist current
- [ ] wiki current
- [ ] known limitations documented

## Version roadmap

The repository's existing conceptual roadmap is:

### v0.1 — Exists

Core desktop buddy functionality.

### v0.2 — Feels alive

Animation polish, reactions, sleep/wake behavior, status/UI work, and desktop reliability.

### v0.3 — Needs care

Potential future systems:

- health
- fullness
- feeding
- XP
- leveling

Do not pull these into the public-alpha interaction-core sprint prematurely.

### v0.4 — Develops personality

Potential future systems:

- unlockable behaviors
- expressions
- traits
- cosmetic progression

### v0.5 — Lives on your desktop

Potential deeper environment interaction:

- windows
- cursor behavior
- screen edges
- richer desktop-environment awareness

These later versions are direction, not a promise of exact implementation.

## Near-term work order

Recommended order from the current development state:

1. finish/validate pickup and put-down
2. verify all new transition art
3. verify typing/computer transparency
4. run full interaction torture tests
5. build/audit package
6. create a known-good checkpoint
7. add/maintain philosophy and alpha-checklist documentation
8. only then return to optional art/animation polish

## What not to add before alpha stability

Unless the scope changes intentionally, avoid using the alpha sprint for:

- hunger/feeding
- health systems
- XP/leveling
- inventory/shop
- AI/chat features
- large UI/dashboard systems
- repository-wide architecture rewrites
- unnecessary platform integrations

Feature restraint is part of the alpha strategy.

## After public alpha

Use real user feedback to decide what matters next.

Useful questions:

- Which interactions do users naturally discover?
- Does Mochi stay running for long sessions without annoyance?
- Which animations feel delightful versus repetitive?
- Does the context menu expose the right controls?
- Are resource use and Wayland behavior acceptable across machines?
- Do users want deeper care systems, more personality, or more environment interaction first?

Do not assume the later roadmap is correct until users validate the creature core.
