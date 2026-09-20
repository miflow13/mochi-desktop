# Changelog

Notable user-facing changes to Mochi are tracked here.

Mochi is still in early public alpha, so behavior, configuration, and compatibility details may change between prereleases.

## Unreleased

### Added

- Added **Focus with Mochi** sessions with configurable focus/break rounds,
  optional rain ambience, bond XP, and dedicated menu/setup-thinking and
  writing animations.

### Changed

- Continued Linux desktop reliability work around workspace changes, placement, multi-monitor behavior, and contextual reactions.
- Documentation is being split into focused guides so the root README remains a concise project overview.
- Clarified alpha limitations, installation/update steps, and tester reporting guidance.
- Aligned the runtime version string with the existing package version, `0.2.0a0`.

### Known issues

- **Open alpha blocker:** entering GNOME Overview or switching workspaces during an emote can leave Mochi visually frozen on XWayland ([#45](https://github.com/miflow13/mochi-desktop/issues/45)). The latest reproduction report supersedes earlier unsuccessful reproduction attempts; no fix is claimed.
- Drag-left/right poses can lag after reversing pointer direction. Investigation remains open in [#68](https://github.com/miflow13/mochi-desktop/issues/68); no fix is claimed.
- Niri, fractional scaling, and non-GNOME environments receive less regression coverage than Fedora + GNOME + Wayland.
- GNOME awareness depends on the Shell helper; a first installation may need one logout/login before it becomes active.

### Release metadata note

Audit of GitHub metadata on 2026-09-15:

- Current package and runtime metadata use `0.2.0a0` (Python's spelling of `0.2.0-alpha`). This polish pass does not assign a new release version. Record the tested commit because installing `main` includes unreleased changes.
- The published [`v0.2.0-alpha`](https://github.com/miflow13/mochi-desktop/releases/tag/v0.2.0-alpha) release is marked non-prerelease, but its body says `v0.3.0-alpha` and describes care/comfort work. That conflicts with its tag and with the project's alpha status.
- The published [`v0.3.0-alpha`](https://github.com/miflow13/mochi-desktop/releases/tag/v0.3.0-alpha) prerelease advertises nameplates and comfort/care foundations, while its tagged package metadata still says `0.2.0a0`. Its body also repeats the "What's Changed" heading. These release descriptions are not a reliable current feature inventory.
- Existing releases and tags are unchanged. Release naming and descriptions need a separate maintainer decision before promotion; care/progression claims are not part of this pass.

[Issue #37](https://github.com/miflow13/mochi-desktop/issues/37) owns the current alpha QA gate. This documentation pass does not certify release readiness.

## 0.2.0-alpha — Feels Alive

Feature summary for the early alpha line; see the metadata note above for published-label discrepancies.

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
