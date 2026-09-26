# Mochi Update Service — Design

**Date:** 2026-09-26  
**Target:** post-v0.3 / v0.4 supporting work  
**Status:** approved design, implementation not started

## Purpose

Give installed Mochi users a simple, polished way to learn that a newer build exists and update without manually running Git commands.

The updater should feel like part of Mochi rather than a package manager: quiet by default, cute when it appears, explicit before installation, and safe if anything goes wrong.

For the current alpha, the update source is the latest commit on the repository's `main` branch. The design must leave room for a future stable channel backed by GitHub Releases without requiring a UI rewrite.

## Product principles

1. **User intent wins.** Mochi may check and notify automatically, but never installs an update without an explicit **Update & Restart** action.
2. **Do not nag.** Automatic checks are infrequent, failed checks are silent, and a dismissed target commit is not repeatedly announced.
3. **Keep the creature central.** Update notification begins as a Mochi speech bubble; the GTK updater window appears only when the user chooses to act.
4. **Protect the working installation.** A failed update must leave the previous Mochi runnable.
5. **Protect user state.** Bond progress, unlocks, future personality state, position, audio preferences, and Focus preferences are never replaced by application updates.
6. **Do not touch developer checkouts.** Updating an installed Mochi must not run `git pull`, switch branches, stash files, or otherwise mutate a user's source checkout.
7. **Fail quietly when offline.** Update discovery is optional and must never block Mochi startup.

## User experience

### Automatic discovery

On startup, Mochi checks the timestamp of the last successful or attempted automatic update check.

If fewer than 24 hours have elapsed, no network request is made.

If a check is due:

1. resolve the current `main` HEAD commit from the official repository;
2. compare it with the installed commit;
3. when different, fetch the update metadata associated with that exact target commit;
4. record the result locally.

Network failures, malformed metadata, GitHub outages, or timeouts do not surface an error to the user during ordinary startup.

### Notification

A newly discovered target commit may produce one speech bubble:

> psst... i learned some new things! 🌱

The right-click menu gains an **Update available** row/indicator.

The same target commit is not announced repeatedly after the user chooses **Later**. A newer target commit may become eligible for one new notification.

A normal **Check for updates** action remains available even when no update is known.

### Update window

Selecting **Update available** or **Check for updates** opens one compact GTK window. The same window changes state throughout the operation instead of spawning multiple dialogs.

The visual treatment follows Mochi's existing GTK language:

- roughly 420–480 px wide;
- rounded, compact surface;
- system light/dark theme support;
- Mochi green used as the accent;
- real project pixel art and authored Mochi animations;
- nearest-neighbor rendering;
- no illustrated replacement mascot;
- no terminal window required for the normal flow.

#### Available state

The window shows:

- installed version;
- available version/channel;
- short commit identifiers in a secondary/technical treatment;
- a compact **What's new** section with 2–3 curated highlights;
- **Later**;
- emphasized **Update & Restart**.

The full changelog may be linked separately rather than copied into the window.

#### Downloading state

The updater shows real byte progress when available.

Suggested copy:

> Getting the newest Mochi…

A safe **Cancel** action is available while cancellation cannot damage the current install.

#### Installing state

Installation uses honest stages rather than fabricated percentages:

- Downloaded update
- Verified files
- Installing Mochi
- Checking installation
- Restarting

Suggested copy:

> Setting things up…

Once the critical installation/swap phase begins, cancellation is no longer offered.

#### Success state

After the new installation starts successfully, the updater completes and the relaunched Mochi gives a one-time return acknowledgement such as:

> i'm back! 🌱

A Wave or similarly lightweight authored animation may accompany that acknowledgement.

#### Failure state

Friendly error copy:

> Hmm... something went wrong.  
> Your current Mochi is still safe.

Actions:

- **Try Again**
- **Close**
- **Show Details**

Technical details may include the failed stage, current version, and target commit for bug reporting. Raw Python tracebacks are not the default user experience.

## Architecture

The updater is divided into four responsibilities.

### 1. UpdateChecker

The runtime-side checker is read-only with respect to installation.

Responsibilities:

- enforce the automatic-check cooldown;
- resolve the latest `main` commit from the official repository;
- compare target and installed commits;
- fetch update metadata for the exact target commit;
- return a small typed result such as:
  - `UP_TO_DATE`
  - `UPDATE_AVAILABLE`
  - `CHECK_FAILED`

It must not download the application archive or modify the installation.

### 2. UpdateState

Small persistent metadata using Mochi's existing local configuration approach.

Conceptual preference/check fields:

```text
update_checks_enabled = true
update_channel = "main"
last_update_check = ...
dismissed_commit = ...
```

Installed build identity is stored separately under the application home because it describes the installed runtime, not a user preference.

No account, telemetry identifier, device identifier, analytics payload, or cloud state is introduced.

### 3. Update presentation

GTK presentation owns:

- speech-bubble notification;
- context-menu update row/state;
- update window;
- progress/stage rendering;
- friendly error presentation.

Presentation never performs installation work itself.

### 4. External `mochi-update` executable

The installer installs a third user-facing command alongside the existing commands:

```text
mochi
mochi-update
mochi-uninstall
```

`mochi-update` owns download, verification, installation, rollback coordination, and relaunch.

The Mochi process must exit cleanly before its active runtime environment is replaced.

## Updater execution independence

The critical updater process must not depend on the runtime environment it is about to replace.

The installed `mochi-update` command may begin as a lightweight launcher, but before the venv swap it must bootstrap the updater runner into a stable temporary/application-owned location and use an interpreter/resources that remain available while `venv` is renamed.

Acceptable implementation shapes include:

- a small shell launcher that starts a system-Python updater runner copied outside the active venv; or
- a bootstrap step that copies the required updater module/UI assets to the update workspace before entering the critical phase.

The updater must not rely on late imports or asset reads from the old venv after that venv has been moved to `venv.backup`.

This requirement prevents the updater from deleting or renaming the code it still needs to finish rollback, report progress, or relaunch Mochi.

## Update source and race avoidance

The alpha update channel is:

```text
https://github.com/miflow13/mochi-desktop
branch: main
```

Update discovery first resolves the exact `main` commit SHA.

All metadata and source used for that update are then fetched from that exact commit. The updater must not resolve `main` once for the notification and later download a potentially newer branch snapshot.

Conceptually:

```text
resolve main -> TARGET_SHA
fetch metadata at TARGET_SHA
user approves
download archive for TARGET_SHA
install TARGET_SHA
record TARGET_SHA
```

This makes one update attempt deterministic even while new commits continue landing on `main`.

## Update metadata

A small repository file, for example `update.json`, provides human-facing update information.

It does **not** need to contain its own commit SHA; the SHA comes from update discovery.

Example:

```json
{
  "version": "0.3.1-alpha",
  "channel": "main",
  "highlights": [
    "Mochi notices more desktop context.",
    "Edge Roam is more reliable.",
    "New personality behaviors have arrived."
  ]
}
```

Requirements:

- 2–3 short curated highlights;
- no automatic parsing of `CHANGELOG.md`;
- malformed or missing metadata must not prevent update detection;
- the updater may fall back to version/commit-only presentation.

## Installed metadata

The installer records the build that is actually installed in application-owned data, conceptually:

```text
~/.local/share/mochi-desktop/install.json
```

This record is separate from relationship/preferences configuration and may be replaced whenever the application runtime is replaced.

Conceptual record:

```json
{
  "version": "0.3.0a1",
  "commit": "97b770344aad...",
  "channel": "main",
  "installed_at": "2026-09-26T..."
}
```

When installation occurs from a Git checkout, the installer may discover the commit locally.

When installation occurs from an updater-downloaded archive, `mochi-update` passes the already-resolved target commit to the installer and records it after successful installation.

A source install with no discoverable commit remains valid; automatic comparison may fall back to version information or report that the installed commit is unknown.

## Download and validation

`mochi-update` downloads a clean archive for the exact target SHA into a temporary directory.

Before executing installation code, it validates the expected Mochi source structure, including at least:

```text
pyproject.toml
install.sh
src/mochi/
assets/mochi/
```

The normal UI does not support arbitrary update URLs. The source is fixed to the official Mochi repository.

The temporary source is removed after success or failure.

## Installation safety and rollback

The existing working environment remains recoverable until the replacement has passed installation checks and the new Mochi reports successful startup.

Conceptual runtime layout during an update:

```text
~/.local/share/mochi-desktop/
├── venv             # current/final runtime
├── venv.update      # candidate runtime while being prepared
└── venv.backup      # previous runtime during final handoff
```

The exact filenames may change during implementation, but the ownership model must remain transactional.

### Required sequence

1. Download the exact target source.
2. Validate source structure.
3. Build/install the candidate runtime without destroying the active runtime.
4. Verify the candidate:
   - Python environment exists;
   - `mochi` executable exists;
   - package metadata/version is readable;
   - core imports succeed;
   - required runtime assets are present.
5. Quit the running Mochi cleanly.
6. Move the old runtime to a backup location.
7. Promote the candidate runtime to the final location using same-filesystem renames where possible.
8. Relaunch Mochi with a one-time startup handshake.
9. After the new process reports successful initialization, delete the backup and record the installed metadata.
10. If startup fails or times out, stop the failed candidate if necessary, restore the previous runtime, and report a safe failure.

The implementation should reuse installer logic rather than maintain two independent definitions of how a Mochi runtime is built.

## Startup handshake

Installation success alone is not enough to discard the backup.

The relaunched Mochi receives a one-time updater handshake token/path through an internal command-line argument or environment variable.

After core application initialization succeeds, Mochi signals readiness to the external updater.

The handshake is:

- local only;
- ephemeral;
- not a permanent daemon or IPC service;
- unused during normal launches.

A timeout or immediate process failure causes rollback.

## User data boundary

Updater work must not overwrite persistent relationship or preference data.

Application/runtime replacement is separate from user state.

Protected state includes, at minimum:

- bond XP and level;
- unlocked emotes;
- future v0.4 personality tendencies;
- future cosmetic choices;
- position and sizing;
- audio preferences;
- Focus preferences;
- ordinary Mochi configuration.

Any future data migration must be backward-safe or separately designed. The updater itself does not reset user data as a recovery strategy.

## GNOME helper behavior

The existing installer may update Mochi's optional GNOME helper.

For updater v1:

- helper installation remains idempotent;
- Mochi must continue to degrade safely when the helper is absent or an older compatible helper is active;
- if GNOME requires logout/login to load changed extension JavaScript, the success UI explains that without forcing logout;
- helper updates must not be required for the updater UI itself to function.

Strict app/helper lockstep versioning is out of scope for updater v1. If a future helper change cannot remain backward-compatible during rollback, helper rollback/version negotiation needs its own design.

## Manual CLI flow

The normal GUI flow is primary, but users can run:

```bash
mochi-update
```

The CLI uses the same checker, target resolution, validation, staged installation, and rollback behavior as the GUI.

It should present concise human-readable stages and return a non-zero exit code on failure.

No separate updater implementation should exist solely for the GUI.

## Network behavior

Automatic checks:

- at most once every 24 hours by default;
- short timeout;
- no startup blocking;
- no retry loop during the same session;
- failures remain silent.

Manual checks:

- always allowed;
- may display a friendly network/check error.

Only update metadata is fetched during a check. The full source archive is downloaded only after explicit user approval.

## Security and integrity boundaries

Updater v1 is intentionally narrow:

- fixed official GitHub repository;
- exact target commit resolved before download;
- exact-commit archive used for installation;
- expected source-tree validation before executing the installer;
- no arbitrary mirrors or user-supplied update URLs in normal UI;
- no privilege escalation beyond what the existing installer already requires for missing Fedora packages.

Future release artifacts may add cryptographic checksums/signatures. That is not required to ship the first main-channel updater, but the design should not prevent it.

## Future stable channel

The first implementation exposes only the current alpha behavior:

```text
main -> latest main commit
```

Internally, source/channel selection should not be hardwired into presentation code.

A future release may support:

```text
Stable       -> newest GitHub Release artifact
Development  -> newest main commit
```

Ordinary users should eventually default to Stable. The UI designed here should continue to work without meaningful redesign.

## Non-goals

Updater v1 does not add:

- background auto-installation;
- forced restarts;
- telemetry;
- accounts;
- delta/binary patching;
- peer-to-peer distribution;
- arbitrary package repositories;
- arbitrary update URLs;
- a general plugin/package manager;
- rollback history beyond the immediately previous working runtime;
- strict GNOME-helper version negotiation;
- automatic user-data schema migration beyond migrations explicitly supported by Mochi.

## Expected code boundaries

Exact filenames may change during implementation, but responsibility should remain separated.

Likely additions/changes:

```text
src/mochi/update/
    checker.py        # remote/current-version comparison
    model.py          # result/state types
    window.py         # GTK updater presentation

src/mochi/update_cli.py or equivalent
    # external updater entry point

install.sh
    # reusable/staged install support + installed metadata

pyproject.toml
    # mochi-update console entry point

update.json
    # curated user-facing update metadata

tests/
    # checker, metadata, staging/rollback, CLI, UI-state regressions
```

Updater lifecycle must not become another owner of Mochi's animation state machine. Runtime notification/presentation should use existing dialogue/menu presentation paths and yield to direct interaction.

## Testing requirements

### Pure/unit coverage

- installed == target -> up to date;
- installed != target -> update available;
- unknown installed commit degrades safely;
- cooldown prevents repeated automatic checks;
- manual checks bypass automatic cooldown;
- dismissed target is not re-announced;
- newer target becomes eligible;
- malformed metadata falls back safely;
- network failure returns `CHECK_FAILED` without raising into startup.

### Installer/updater coverage

- exact target SHA is used throughout one update;
- invalid archive is rejected before install;
- candidate install failure leaves current runtime untouched;
- candidate validation failure leaves current runtime untouched;
- successful candidate swaps into place;
- startup handshake success removes backup;
- startup handshake failure restores backup;
- temporary source/candidate directories are cleaned up;
- installed metadata records the actually installed target.

### Regression coverage

- existing `mochi` launcher still works;
- `mochi-uninstall` still works;
- clean `./install.sh` path still works;
- reinstall/update does not duplicate desktop launchers/helpers;
- updater does not mutate a source checkout;
- update notification does not interfere with context menu, dragging, Focus, Sleep, or ambient behavior.

### Live Fedora/GNOME QA

Mika's local Fedora/Wayland test remains required for:

- speech bubble presentation;
- update-menu row;
- light/dark GTK styling;
- real Mochi pixel-art rendering;
- quit/update/restart flow;
- failure/rollback presentation;
- GNOME helper update notice;
- app-grid launch after update.

## Acceptance criteria

The first updater is complete when:

- Mochi can detect a newer `main` commit without blocking startup;
- one unobtrusive notification appears for a new target;
- the user can manually check for updates;
- the polished GTK updater shows concise release highlights;
- **Update & Restart** downloads and installs the exact approved target;
- no developer checkout is modified;
- an install/startup failure restores the previous runnable Mochi;
- persistent user relationship/config data survives unchanged;
- successful update relaunches Mochi automatically;
- `mochi-update` provides the same update path from the terminal;
- full automated verification passes;
- live Fedora/GNOME QA passes before merge.

## Later roadmap relationship

This update system is supporting infrastructure, not one of v0.4's personality pillars.

v0.4 remains focused on **Develops Personality**:

1. learned behaviors;
2. emergent local personality tendencies;
3. restrained cosmetic personalization;
4. deeper non-punitive relationship milestones.

The updater simply gives users a friendly, reliable path to receive those improvements as Mochi evolves.
