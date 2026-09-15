# Changelog

Notable user-facing changes to Mochi are tracked here.

Mochi is still in early public alpha, so behavior, configuration, and compatibility details may change between prereleases.

## Unreleased

### Added

- Ongoing v0.3 care/progression work, including feeding and future progression hooks.

### Changed

- Continued Linux desktop reliability work around workspace changes, placement, multi-monitor behavior, and contextual reactions.
- Documentation is being split into focused guides so the root README remains a concise project overview.

### Known issues

- Workspace-switch / XWayland reliability remains under investigation in [issue #45](https://github.com/miflow13/mochi-desktop/issues/45).
- Niri, fractional scaling, and non-GNOME environments receive less regression coverage than Fedora + GNOME + Wayland.

## 0.2.0-alpha — Feels Alive

Current public-alpha development line.

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
