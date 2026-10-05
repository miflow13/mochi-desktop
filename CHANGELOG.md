# Changelog

Notable user-facing changes to Mochi are tracked here.

Mochi is still in early public alpha, so behavior, configuration, and compatibility details may change between prereleases.

## 0.4.1 — Curious & Steady

Mochi notices where your attention goes, and stays animated and updatable
on GNOME.

### Added

- Mochi now notices when you switch windows or settle on a new browser tab.
  If he's standing around he takes a quick look through his magnifying glass;
  if he's busy he shows a tiny thought bubble instead, and he settles down
  during long browsing sessions. Both come from the GNOME helper, which tells
  Mochi that you switched, and at most a broad app type such as browser or
  terminal, never a title or address. They start working after you log out
  and back in once the update installs.

### Changed

- Terminal coworking has new artwork: Mochi takes out a little laptop, types
  sleepily, and puts it away again when you leave the terminal. The opening and
  closing frames match his idle pose, so the change in and out does not pop.
- Installed Mochi now updates from **published GitHub Releases** instead of
  every commit on `main`, so a change has to ship in a release before it
  reaches everyone. Alpha testers can keep following `main` with
  `mochi-update --channel main` (and return with `--channel release`).
  Switching channels never downgrades an installed build.

### Fixed

- Fixed the likely cause of Mochi's animation freezing on GNOME (#45). GTK paused his
  window after each frame until GNOME Shell confirmed it was drawn, with no
  timeout, so a single missed confirmation stopped his sprite while he kept
  moving and talking. Mochi now paces his own frames.
- Mochi's nameplate, speech bubble, and bond progress overlay are readable in
  light mode again. They used libadwaita-only theme colors that plain GTK does
  not define, so GTK dropped them and the nameplate showed white text with no
  background — invisible on light desktops.
- Mochi now follows the desktop's light/dark style, including switching live,
  through the XDG Settings portal. Previously plain GTK 4 (before 4.20) kept
  Mochi's menus and overlays in one style regardless of the system setting.

- **Update & Restart** now relaunches Mochi after installing. In 0.4.0-alpha.1
  the updater leaked its private `PYTHONPATH` into the relaunched Mochi, which
  then crashed on startup; the rollback restored the previous installation but
  crashed the same way, leaving Mochi closed. The updater now gives install,
  validation, and relaunch a clean environment, and the `mochi` command starts
  through a small launcher that also survives the older updater's environment,
  so installations still running 0.4.0-alpha.1 can update to this fix.
  If an earlier update left Mochi closed, open Mochi again and update again.
- The updater's candidate check now confirms the real Mochi package loads from
  the new runtime instead of only checking that a `mochi` package exists.
- Failed updates now say what went wrong: installer, integration-refresh,
  startup-check, and relaunch failures each report a reason, and installer
  output appears under **Show Details** instead of only an exit status.

## 0.4.0-alpha.1 — Pocket & Polish

v0.4 focuses on making Mochi more useful, easier to update, and easier for the
community to contribute to without losing the small, local desktop-companion
feel.

### Added

- Added **Mochi Pocket**, a local-first ten-item shelf for files, directories,
  text, HTTP(S) links, and dropped images. Supported drags now make Mochi loop
  an open-mouth preview with hover feedback before release, then close his mouth
  only after the item is safely persisted. Pocket contents can be opened, viewed,
  revealed in their containing folder, removed individually, or cleared together
  from the new `Pocket · N` context-menu window.
- Added the **Mochi Artist Kit**, including the canonical character reference,
  production sprites, canvas/dimension rules, animation conventions, and a
  contribution template for community-made Mochi animations.
- Added more autonomous companion behavior, including occasional naps that
  cooperate with Mochi's existing interaction and state lifecycle.
- Added a polished **Mochi Update Service** for installed alpha builds. Mochi can
  quietly detect newer `main` commits, announce an available update once, show
  a compact GTK **What's new** window using real Mochi pixel art, and update
  through the new `mochi-update` command or **Update & Restart** UI.
- Updates are pinned to the exact discovered commit, staged beside the current
  runtime, validated before swap, and rolled back if the replacement does not
  start successfully. User bond/progression/preferences remain separate from
  the replaceable runtime.
- Added **This Is Fine** as a rare Bond Level 3 catalogue emote with an animated hover preview and unlock reveal.
- Added **Wave**, **VS Code**, and **Mochi.exe** to the Bond-aware Emote Catalogue, replacing the three placeholder mystery cards with authored animated previews and new bond unlocks.
- Added **Coffee** as a completed Bond-aware catalogue emote with an animated hover preview.
- Added **Focus with Mochi** sessions with configurable focus/break rounds,
  optional rain ambience, bond XP, and dedicated menu/setup-thinking and
  writing animations.
- Added bond-phase relationship dialogue so triple-click responses grow from
  curious introductions into familiar, comfortable, and long-term companion lines.
- Added a dedicated breathing idle animation for Mochi's persistent sad mood.

### Fixed

- Source installs now generate the `mochi` launcher from the final virtual-environment path instead of a deleted temporary directory.

### Changed

- Broadened installer/runtime portability so GNOME-only integration is optional
  and non-GNOME Linux desktops can install without GNOME extension tooling.
- Enabling **Edge roam** now closes the context menu and immediately starts Mochi toward the nearest screen edge when he is free to walk.
- Slowed Mochi's default breathing loop from **3.9s to 4.95s** so his resting motion is gentler and less visually distracting in peripheral vision.
- Every unlocked Emote Catalogue animation now automatically participates in Mochi's autonomous idle emote pool. The overall emote chance stays fixed as the catalogue grows, so new emotes add variety without making Mochi increasingly noisy.
- Nameplate is now ephemeral: it appears while Mochi is hovered, remains briefly after speech, then fades away to reduce persistent desktop clutter. Temporary care/interaction feedback may still surface it when needed.
- Package/runtime version metadata is `0.4.0a1` (Python packaging form of
  `0.4.0-alpha.1`).

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
