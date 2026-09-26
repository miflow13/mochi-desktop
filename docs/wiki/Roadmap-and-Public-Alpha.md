# Roadmap and Public Alpha

Mochi's roadmap is staged around one requirement: new personality and progression features must preserve the dependable creature core underneath them.

> **Current release line:** v0.3 — Growing Together
>
> **Current QA tracker:** [issue #37](https://github.com/miflow13/mochi-desktop/issues/37)
>
> GNOME Overview/workspace freezing ([#45](https://github.com/miflow13/mochi-desktop/issues/45)) remains a known alpha issue, and drag-direction latency ([#68](https://github.com/miflow13/mochi-desktop/issues/68)) remains under investigation.

## Current phase

**v0.3 — Growing Together / release stabilization**

The v0.3 feature work is now on `main`. Current priorities are:

- regression testing and long-session reliability
- bond/feed/focus lifecycle hardening
- context-menu and drag reliability
- packaging/version consistency
- Fedora/GNOME/Wayland/XWayland QA
- tester feedback from different monitor/compositor setups
- documentation and release polish
- supporting update infrastructure so alpha testers can safely move to newer `main` builds without managing Git

This phase is no longer about adding another major system before the release checkpoint.

## What v0.3 adds

### Relationship without punishment

Mochi now has persistent, non-decaying bond progression.

The design intentionally avoids:

- daily streaks
- relationship decay
- missed-day penalties
- punishment for closing Mochi
- failure states for not interacting

Bond grows through ordinary shared activity such as typing, feeding, and Focus with Mochi.

### Feeding

Feed is a positive direct interaction with authored animation/audio, bond progress, and post-feed heart feedback.

It is **not** a hunger/fullness survival system. Mochi does not become sick or unhappy because the user was away.

### Emote progression

The Emote Catalogue exposes bond-gated expressions, rarity, lock state, hover previews, and newly learned idle moods.

### Level-up feedback

Bond level changes use one coherent presentation path: authored level-up animation, sound, level card, optional unlock card, and newly learned emote demonstration.

### Focus with Mochi

Focus sessions add configurable focus/break rounds, a dedicated coworking presentation, optional Rain ambience, and bond XP for completed focus time.

Focus remains intentionally non-punitive: pauses and early stops do not create penalties.

## Public-alpha goal

The public alpha should be a small, dependable companion that users can install, leave running, interact with, and test across real Linux desktops.

v0.3 expands the surface that must remain reliable:

```text
IDLE
├── click / double-click / dialogue → reaction → IDLE
├── ambient context → temporary presentation → IDLE
├── context menu → WALK / SLEEP / FEED / FOCUS / controls
├── PICKUP → DRAG → release-settle → IDLE
├── bond XP → optional LEVEL-UP / UNLOCK presentation → prior behavior
└── FOCUS clock → writing/break presentation while direct interaction may interrupt visually
```

## Alpha blockers

Do not call the build release-ready while any of these are reproducible:

- crash during ordinary interaction
- permanent input freeze
- context menu cannot reopen
- drag cannot recover after another action
- pickup/put-down can leave Mochi stuck
- one-shot animation leaves behavioral state invalid
- Focus creates duplicate clocks/audio or loses earned XP
- level-up/unlock presentation becomes stuck or repeats from stale state
- bond persistence corrupts or resets unexpectedly
- ambient timers multiply or fight direct input
- legacy/noncanonical art appears unexpectedly
- baked checkerboard/obvious gray matte appears in runtime art
- package installs with wrong/missing runtime assets
- package/runtime version strings disagree
- normal runtime requests remote-desktop/screen-control permissions

## Alpha definition of done

### Startup

- [ ] clean launch on target Fedora/GNOME environment
- [ ] canonical Mochi appears immediately
- [ ] transparent undecorated presentation works
- [ ] no unexpected permission prompts
- [ ] no immediate GTK/Python errors

### Core interaction

- [ ] idle/blink/walk remain stable
- [ ] click and double-click arbitration remains correct
- [ ] pickup/drag/drop always recovers
- [ ] context menu opens/closes repeatedly
- [ ] Sleep/Wake remains reliable
- [ ] direct interaction outranks ambient behavior

### v0.3 systems

- [ ] bond state persists across restart
- [ ] feeding completes once and recovers
- [ ] catalogue lock/unlock/hover behavior remains correct
- [ ] real level-up feedback plays once
- [ ] newly unlocked emote demonstration plays once
- [ ] Focus start/pause/resume/stop/start remains stable
- [ ] Focus reward boundaries are correct
- [ ] Rain audio starts/stops cleanly
- [ ] shutdown persists pending bond/Focus progress

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
- [ ] no timer/input/audio-source leak observed

### Documentation / release

- [ ] installation instructions match actual package
- [ ] package and runtime metadata agree
- [ ] changelog matches shipped features
- [ ] regression watchlist is current
- [ ] wiki reflects the current release line
- [ ] known limitations are documented

## Version roadmap

These labels describe direction, not promises that every listed idea will ship.

### v0.1 — Exists

Core desktop buddy functionality.

### v0.2 — Feels Alive

Animation polish, reactions, sleep/wake behavior, contextual awareness, and desktop reliability.

### v0.3 — Growing Together

Shipped direction:

- persistent bond progression
- feeding as a positive interaction
- bond-gated emotes
- level-up/unlock feedback
- Focus with Mochi
- continued contextual personality and reliability work

### Supporting infrastructure between v0.3 and v0.4

The update service is release/distribution infrastructure rather than a new
personality pillar. It provides quiet update discovery, a user-approved
**Update & Restart** flow, an exact-commit staged install, startup verification,
and rollback while preserving local relationship/configuration data.

During the public alpha, the updater follows `main`. A later stable channel may
move ordinary users to signed/versioned GitHub Release artifacts without
changing the in-app experience.

### v0.4 — Develops Personality

Potential future direction:

- broader unlockable behavior sets
- richer phrase/personality variation
- cosmetic personalization
- deeper non-punitive relationship rewards

### v0.5 — Lives on Your Desktop

Potential future direction:

- broader desktop-environment integration
- more environment-aware reactions
- compositor/platform coverage
- richer spatial behavior

## What not to add during v0.3 release stabilization

Until the release checkpoint is stable, avoid expanding into:

- punitive hunger/fullness decay
- health/failure systems
- shops/inventory/economies
- daily streaks or obligation mechanics
- AI/chat systems
- large dashboard UI
- repository-wide architecture rewrites
- unrelated platform integrations

Feature restraint still matters; v0.3 should stabilize before another major feature wave.

## After the v0.3 alpha

Use tester feedback to decide what matters next:

- Which bond interactions feel meaningful versus noisy?
- Do unlocked emotes make Mochi feel more expressive?
- Is Focus pleasant to leave running for real work sessions?
- Does Mochi remain reliable across monitors, scaling, and compositor differences?
- Which lifecycle bugs appear only after hours of use?
- Which future personality/care features can add delight without obligation?

Do not let roadmap ideas outrun what real users validate.
