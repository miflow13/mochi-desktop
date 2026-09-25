# Pull Request

> ### New to Mochi? Start with the codebase manual 🌱
>
> If this is your first contribution—or your change touches runtime behavior—please read the
> **[Mochi Codebase Manual](https://github.com/miflow13/mochi-desktop/blob/main/docs/CODEBASE_MANUAL.md)**
> before you begin.
>
> The manual explains Mochi's shared behavior-state path, animation/state ownership,
> interruption and recovery rules, timers/callback lifecycles, contextual detection,
> GTK/XWayland behavior, repository structure, debugging, and common change patterns.
>
> Also see [CONTRIBUTING.md](https://github.com/miflow13/mochi-desktop/blob/main/CONTRIBUTING.md)
> and [REGRESSION_WATCHLIST.md](https://github.com/miflow13/mochi-desktop/blob/main/REGRESSION_WATCHLIST.md).
> Mochi is an early public alpha, so `main` remains the source of truth if documentation
> and implementation disagree.

## Summary

<!-- What changed and why? Describe the behavior/result, not only the files edited. -->

## Scope

<!-- What is intentionally not part of this PR? Keep one focused concern per PR when possible. -->

## Verification

- [ ] Relevant sections of the Codebase Manual were reviewed when runtime behavior changed
- [ ] Relevant tests added or updated
- [ ] `python3 -m pytest -q` passes
- [ ] `git diff --check` passes
- [ ] Documentation updated when public behavior, setup, or architecture changed
- [ ] `CHANGELOG.md` updated for notable user-facing changes when appropriate
- [ ] `REGRESSION_WATCHLIST.md` reviewed when interaction/state/input/animation/windowing code changed
- [ ] Live GTK/XWayland verification completed when runtime behavior changed

## Runtime / lifecycle notes

<!--
For behavior changes, briefly explain anything reviewers should know about:
- state ownership and transitions
- start / active / end / interruption / recovery behavior
- timers, callbacks, monitors, windows, or other long-lived resources
- repeated detection/events and whether they can retrigger the state
- nearby interactions that could regress (dragging, context menu, sleep/wake, idle recovery)

Delete this section if it is not applicable.
-->

## Environment tested

<!-- Example: Fedora 44 / GNOME / Wayland + XWayland -->

- OS:
- Desktop / compositor:
- Display path:

## Notes

<!-- Known limitations, follow-ups, screenshots, recordings, or reproduction details. -->
