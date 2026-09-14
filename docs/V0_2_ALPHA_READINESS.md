# v0.2 alpha readiness audit — 2026-09-14

Baseline: `origin/main` at `0bb3c49`; branch `chore/v0.2-alpha-hardening`.
Read GitHub issues #37, #18, #45, #7, #8 and #54, including comments.
No experimental branch was modified or merged. Existing features on main were
preserved; no care/progression work or Buddy decomposition was undertaken.

## Findings and disposition

| Severity | Finding | Disposition |
| --- | --- | --- |
| High | Unreadable config and infinite numeric values could prevent launch. A failed position save could abort `_advance_walk` before IDLE recovery and terminate its GLib tick. | Fixed: safe defaults, finite volume, bounded coordinates, caught write errors, atomic replacement preserved, warning rate limited. |
| High | Core tick, ambient timers and typing/presence/media/file/shortcut monitors were not explicitly released by application shutdown. Menu and speech surfaces lacked terminal disposal. | Fixed: idempotent core shutdown called by application, cancel timers, stop monitors/player, dispose surfaces, reject queued menu actions. This is not a fix claim for #45. |
| High / publication blocker | Existing GitHub `v0.2.0-alpha` release body starts with v0.3 and advertises care/comfort; it is marked non-prerelease. | Recorded only; published metadata requires a separate release-maintenance action. Draft accurate alpha.1 wording is in `V0_2_ALPHA_RELEASE_NOTES.md`. |
| Medium | Package version `0.2.0a0`, runtime version `0.1.0`, README generic alpha disagreed. | All branch metadata now targets `0.2.0a1` / `v0.2.0-alpha.1`. |
| Medium / QA gate | Workspace freeze #45 is intermittent; stock Fedora VM, workspace/monitor stress and soak gates in #37 remain incomplete. | Keep open. No speculative workspace or coordinate changes. |
| Low | README placed size/audio in the regular menu and described squish as a click reaction. | Corrected README and Quick Start: size/audio live in Mochi Lab; clicks use bounce. |
| Low | GTK emitted GtkImage baseline warnings during both smoke launches. | No demonstrated input/layout failure; not changed without diagnosis. |
| Low | #37 expects `pet.wav`, which was intentionally deleted in `8749e83`. | Treat that QA item as stale; do not restore legacy audio or alter art. |

No remaining reproducible crash was found in the checks performed. This is a
bounded release audit, not proof that every desktop sequence is safe.

## Review coverage

- **Startup/restart:** backend selection, application activation, manifest loading,
  temporary config, source and wheel launches. Existing app ID handles normal
  single-instance activation. Runtime test used a separate application ID.
- **Shutdown/ownership:** inspected app, Buddy, presence mixin chain, nameplate,
  Quick Start, speech and both menus. Nameplate/Quick Start already disposed their
  windows. Added missing core/child cleanup; existing optional-presence cleanup
  remains responsible for its own resources.
- **Workspace/XWayland (#45):** inspected mapped-window restore/keep-above,
  X11 pointer placement, monitor selection/clamping, menu popup generations,
  following and focus dismissal, speech/nameplate anchor and visibility checks.
  Shutdown omissions were objectively testable; no workspace-specific causal
  defect was established. Map/unmap and coordinate behavior remain unchanged.
- **Scaling (#7):** fixed 256px sprite canvas is scaled to drawing-area allocation;
  resizing updates drawing area and window size. The input controller area follows
  the widget, rather than an old fixed-size rectangle. Menus convert anchors and
  bounds into X11 device pixels; speech/nameplate use visible sprite bounds.
  All runtime frames fit and render at 64/128/192/256 in Cairo tests; GTK smoke
  checked configured widget/window dimensions at each size. Existing tests cover
  scaled bounds, negative/secondary monitors and right-edge menu positioning.
  The original slicing complaint appears stale at the code/rendering level;
  real pointer hit testing and mixed/fractional-scale display QA remain necessary.
- **Interaction (#8):** reviewed click queue, double-click heart entry, blink idle
  playhead, walking completion, pickup/drag/release recovery, sleep/wake and
  direct interruption. Active-animation identity guards stale completion;
  critical drag/drop states gate ambient entry. Existing tests exercise those
  paths plus typing stop, media stop, terminal/editor focus loss and Edge Roam.
  No broad state rewrite was justified. Rendering and behavioral state remain
  coordinated through existing Buddy/player/mixin methods, not a new controller.
- **AmbiSense:** inspected helper owner generations/subscription cleanup,
  state snapshots, typing fallback/reset, media/music start edges and grace,
  file activity expiry, contextual focus and priority guards. Existing regression
  tests cover browser false positives, video priority, typing feedback and helper
  loss/reconnect. A real private D-Bus/GJS lifecycle test passed. No typed content
  was inspected or recorded. Real media playback, unavailable system services
  and long-duration error/CPU behavior were not exhaustively simulated.
- **Persistence:** size, position, volume/mute, Stay Put and Edge Roam round trips;
  missing/empty/invalid/non-object/non-UTF8 config, wrong types, partial settings,
  non-finite/huge coordinates, read/write failures and retry. Invalid fields
  preserve independent valid fields. Read/write warnings occur at most once per
  operation per ConfigStore; failed persistence is not promised to survive restart.
- **Audio/assets:** all 239 unique manifest frames are packaged and load from the
  installed wheel. All four current audio files are packaged. `pet.wav`, pickup,
  drop and level-up cues are absent optional hooks; missing cues safely skip.
  No artwork changed. Runtime smoke was muted; actual sound output unverified.
- **Install/update/uninstall:** reviewed dependency list, system-site-packages
  venv, wheel install, icon/desktop entry, launcher replacement, helper zip/schema
  compilation, one-time login enable and uninstall/purge paths. Added actual
  shell coverage for replacing a dangling launcher while preserving arguments.
  Shell syntax passes. Full dnf install/logout/login/uninstall was not run against
  the user's live installation. Reinstall deletes the old venv before building
  the new one; interrupted updates still require rerunning the installer.
- **Docs/site:** install/update/uninstall/debug/privacy/support wording compared
  to code and helper scripts. Pages source inspected read-only at
  `origin/gh-pages:index.html`: install/logout and Fedora/Niri limitations agree
  with README; no site deployment needed. Existing screenshots/GIFs were not
  visually revalidated frame-by-frame. #54 decomposition intentionally deferred.

## Version and release naming

Python package and `mochi.__version__`: **0.2.0a1** (PEP 440).
Intended new tag: **v0.2.0-alpha.1**. Intended release title:
**Mochi v0.2.0-alpha.1**, marked **prerelease** when explicitly authorized.
The old `v0.2.0-alpha` already exists; do not move or replace it. A separate
`v0.3.0-alpha` prerelease also exists and was left untouched. No tag, release,
release edit or merge is part of this branch.

## Verification evidence

- Baseline: 366 passed, 1 optional test skipped.
- Final suite: 397 passed, 1 optional test skipped, 1 GI deprecation warning.
- Opt-in real helper test: 1 passed on a private D-Bus session, with GI/asyncio
  deprecation and isolated-bus GVfs environment warnings.
- `python -m compileall -q src`, `git diff --check`, shell syntax: passed.
- Wheel build/install in `/tmp/mochi-alpha-verify-venv`: passed. Inventory checked
  all 239 frames plus all existing audio; installed manifest resolved under venv
  `share/mochi`, independently of the checkout.
- Source and installed GTK/XWayland runtime smoke: passed. Used temporary muted
  settings and a separate application ID; launched, changed all four sizes,
  opened menu/speech, quit, asserted timers/monitors/player stopped and menu hidden.
  These were programmatic checks on the available desktop, not visual/manual QA.
- Added 31 test cases: 21 config recovery, 4 shutdown/queued-action/surface cleanup,
  4 supported-size rendering, 1 version agreement, 1 installer launcher test.

## Focused Fedora GNOME Wayland QA before release

1. Quit with speech visible and a menu open; relaunch several times. Confirm no
   leftover window, lost input or new traceback. Repeat after dragging and sleep/wake.
2. In Mochi Lab, try 64/128/192/256; click/drag/right-click at each size. Repeat
   near a secondary monitor's edges; verify menu, nameplate and speech attachment.
3. Save size, volume/mute, Stay Put and Edge Roam; drag to a new location; restart
   and check all preferences. With Mochi closed and config backed up, try an empty
   or invalid JSON file, confirm launch, then restore the backup.
4. Switch workspaces repeatedly while idle, reacting, after dragging, and with
   menu/speech visible. Record exact steps and logs if #45 reappears. Include both
   monitors if available.
5. On the clean Fedora test setup, install/reinstall and logout/login once;
   confirm helper context, actual click/lifecycle audio, pause/stop recovery and
   clean uninstall. Continue the normal-use soak required by #37.

The branch is suitable for release-candidate testing. Final publication remains
blocked on target-desktop QA signoff and accurate public release metadata; this
pass does not certify the intermittent workspace issue fixed.
