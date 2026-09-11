# Development Checkpoint — 2026-09-09

This document captures the current Mochi development state before work pauses due to Codex weekly-credit limits.

## Branch

`feat/pickup-idle-hover-cleanup`

Current feature commit before this checkpoint:

`8789502` — `feat: polish Mochi interactions and animation assets`

## Source-of-truth decisions

- Preserve the current interaction behavior rather than reintroducing the unstable context-menu experiments from earlier builds.
- The manually replaced drag assets are intentional and should be treated as the current visual baseline.
- Stability takes priority over architectural cleanup or reworking interactions that already feel good.
- Future changes should be small, isolated, and verified against the working right-click/context-menu behavior.

## Changes captured in the latest feature commit

### Pickup interaction

- Added a new six-frame pickup animation under `assets/mochi/pickup/`.
- Updated the animation manifest so the pickup sequence is available to the runtime.
- Updated Mochi behavior/state handling to support the pickup interaction.

### Interaction cleanup

- Simplified interaction handling in `buddy.py` and removed obsolete status-overlay integration from the active interaction path.
- Removed the old `status.py` and `status_overlay.py` implementation from this branch.
- Updated `Interaction-Core.md` to reflect the current interaction model.

### Project/runtime updates

- Updated `app.py`, `behavior.py`, `state.py`, and related sprite-loading behavior to match the current interaction flow.
- Updated `pyproject.toml` for the current runtime/development requirements.

### Tests

- Expanded buddy interaction coverage.
- Updated behavior, sprite-loader, and sprite tests for the current implementation.
- Removed tests that only covered the retired status-overlay implementation.

## Animation state

The current asset set includes the newer hand-replaced Mochi artwork and interaction animations. In particular, the drag behavior/assets are in a state worth preserving.

Do not automatically regenerate, normalize, or replace animation PNGs just because they differ from an older asset set. Visual replacements may be deliberate.

## Context-menu rule

The context menu previously became unreliable after several rounds of interaction/window changes. The project was returned to a stable baseline before continuing.

When resuming work:

1. Verify right-click works at multiple positions on Mochi before changing interaction code.
2. Make one interaction change at a time.
3. Re-test right-click immediately after each change.
4. Avoid broad rewrites of event-controller, hitbox, popover, window, or input-region logic unless a reproducible bug requires them.
5. Preserve a known-good commit before attempting risky fixes.

## Branch relationship to `main`

At this checkpoint the feature branch has diverged from `main`: it contains feature work not on `main`, while `main` also contains newer commits made after the branch point.

Do not force-update either branch. Before merging, review the divergence and deliberately rebase, merge, or cherry-pick as appropriate. README/documentation changes on `main` should not be accidentally overwritten by the older copies on this branch.

## Resume checklist

When development credits are available again:

- Confirm Mochi launches cleanly from this branch.
- Verify idle → pickup/drag → release → idle.
- Verify right-click/context menu without dragging first.
- Verify repeated drag interactions on the same monitor.
- Check pickup animation timing and transition into the held/dragged state.
- Check that random idle behavior still resumes correctly after interaction.
- Run the full test suite before merging.
- Review branch divergence from `main` before opening or updating a PR.

## Next development priority

Continue polishing pickup/drag/idle transitions without destabilizing the interaction core. Treat the current working interaction system and manually replaced drag visuals as the baseline, not as temporary placeholders.
