# Changelog

Notable user-facing changes to Mochi are tracked here.

Mochi is still in early public alpha, so behavior, configuration, and compatibility details may change between prereleases.

## Unreleased

### Added

- Added **This Is Fine** as a rare Bond Level 3 catalogue emote with an animated hover preview and unlock reveal.
- Added **Wave**, **VS Code**, and **Mochi.exe** to the Bond-aware Emote Catalogue, replacing the three placeholder mystery cards with authored animated previews and new bond unlocks.
- Added **Coffee** as a completed Bond-aware catalogue emote with an animated hover preview.
- Added **Focus with Mochi** sessions with configurable focus/break rounds,
  optional rain ambience, bond XP, and dedicated menu/setup-thinking and
  writing animations.
- Added a dedicated breathing idle animation for Mochi's persistent sad mood.

### Fixed

- Source installs now generate the `mochi` launcher from the final virtual-environment path instead of a deleted temporary directory.

### Changed

- Enabling **Edge roam** now closes the context menu and immediately starts Mochi toward the nearest screen edge when he is free to walk.
- Slowed Mochi's default breathing loop from **3.9s to 4.95s** so his resting motion is gentler and less visually distracting in peripheral vision.
- Every unlocked Emote Catalogue animation now automatically participates in Mochi's autonomous idle emote pool. The overall emote chance stays fixed as the catalogue grows, so new emotes add variety without making Mochi increasingly noisy.
- Nameplate is now ephemeral: it appears while Mochi is hovered, remains briefly after speech, then fades away to reduce persistent desktop clutter. Temporary care/interaction feedback may still surface it when needed.

## 0.3.0-alpha.1 — Growing Together

v0.3 expands Mochi from a reactive desktop buddy into a more persistent companion while keeping care intentionally non-punitive.

### Added

- Persistent, non-decaying **Bond Level** and bond XP progression.
- Bond XP from shared activities including typing, feeding, and Focus with Mochi.
- **Feed Mochi** interaction with authored eating animation, sound, post-feed heart, and bond integration.
- Bond-aware **Emote Catalogue** with locked/unlocked states, rarity tiers, coming-soon entries, and animated hover previews.
- Bond-gated idle moods, including newly learned emotes becoming available to ambient behavior.
- Dedicated bond **level-up feedback** with authored animation, sound, visual presentation, unlock cards, and newly learned emote demonstrations.
- **Focus with Mochi** sessions with configurable focus/break durations and rounds.
- Focus-session bond XP: one XP per completed focus minute and a one-time completion bonus for finishing the configured session.
- Optional local **Rain** soundscape for Focus with independent volume control.
- Global Emote Catalogue shortcut through the GNOME helper: `Ctrl + Alt + E`.
- Expanded Mochi Lab controls for bond, unlock, and level-up QA.

### Changed

- Promoted the completed v0.3 development line to `main`.
- Strengthened lifecycle handling around Focus pause/stop/sleep/shutdown and final-minute XP settlement.
- Direct interaction continues to take priority over ambient and long-running presentation states.
- Bond and Focus systems are explicitly designed without streaks, decay, missed-session penalties, or punishment for closing Mochi.
- Rebalanced repeat feeding so completed feeds award **30 XP**, then **10 XP**, then **0 XP** until Mochi has gone 10 minutes without another completed feed; feeding itself always remains available.
- Documentation, release guidance, and regression coverage now reflect the shipped v0.3 interaction surface.
- Package/runtime version metadata is `0.3.0a1` (Python packaging form of `0.3.0-alpha.1`).

### Compatibility

- Fedora + GNOME + Wayland remains the primary tested environment.
- Mochi uses XWayland for the buddy window where GNOME Wayland positioning restrictions require it.
- Niri remains experimental.
- Other Linux environments may work with reduced desktop-awareness integration.

### Known issues

- **GNOME Overview/workspace freeze — [#45](https://github.com/miflow13/mochi-desktop/issues/45):** entering Overview or switching workspaces during an emote can leave Mochi visually frozen on XWayland.
- **Drag direction responsiveness — [#68](https://github.com/miflow13/mochi-desktop/issues/68):** drag-left/right poses can lag briefly after rapidly reversing direction.
- Fractional scaling, multi-monitor arrangements, and non-GNOME compositors receive less regression coverage than the primary Fedora/GNOME environment.
- First-time GNOME helper installation may still require one logout/login before helper-backed awareness and global shortcuts become active.

### Release metadata

The earlier `v0.3.0-alpha` tag is an older development snapshot and is not the final v0.3 feature inventory. `v0.3.0-alpha.1` is the release-prep line that matches the completed v0.3 feature set and `0.3.0a1` package/runtime metadata.

[Issue #37](https://github.com/miflow13/mochi-desktop/issues/37) remains the public-alpha QA tracker.

## 0.2.0-alpha — Feels Alive

Feature summary for the earlier alpha line.

### Added

- Idle breathing and natural blink behavior.
- Walking with persistent **Stay put** control.
- Pickup, velocity-aware dragging, and drop behavior.
- Bounce, squish, heart, click-chirp, and triple-click reactions.
- Sleep / wake behavior.
- Typing and media companion states.
- **AmbiSense**, a local rule-based ambient-awareness system built around privacy-reduced desktop signals.
- GNOME Shell helper integration for richer desktop-awareness events.
- Developer-facing Mochi Lab controls for animation and AmbiSense tuning.
- Automated regression coverage for animation, behavior, configuration, menus, dragging, edge roaming, D-Bus integration, and related state behavior.

### Changed

- Continued state and interaction hardening so repeated contextual detections do not unnecessarily restart active behavior.
- Improved multi-monitor and XWayland positioning reliability.
- Expanded installation and troubleshooting guidance for Fedora + GNOME + Wayland.

### Compatibility

- Fedora + GNOME + Wayland is the primary tested environment.
- Niri support is experimental.
- Other Linux environments may run Mochi with reduced desktop-awareness behavior.

## 0.1 — Exists

Initial desktop-companion foundation: core windowing, sprite animation, movement, interactions, and the first persistent character behaviors.
