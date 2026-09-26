# Regression Watchlist

Use this checklist for interaction/state changes and before release checkpoints. Automated tests are necessary but do not replace live Fedora/GNOME/Wayland/XWayland verification.

## Input / Context Menu

- [ ] Context menu does not leave an invisible GTK input grab
- [ ] Context menu opens/closes repeatedly
- [ ] Right-click works after Walk
- [ ] Right-click works after Sleep/Wake
- [ ] Right-click works during and after Focus
- [ ] Drag still works after using the context menu
- [ ] Feed and Focus actions close the menu before taking presentation ownership
- [ ] Opening/closing the menu while Mochi is sleeping does not wake him unexpectedly

## State / Recovery

- [ ] Blink returns behavioral state to `IDLE`
- [ ] Temporary animation states always have an exit path
- [ ] Pickup / drag / put-down cannot leave Mochi stuck
- [ ] Direct user input correctly interrupts lower-priority ambient behavior
- [ ] Feed returns through heart/recovery without leaving `EATING` active
- [ ] Focus visual interruptions recover to the writing loop while the timer remains valid
- [ ] Level-up/unlock presentation returns to the appropriate behavior state
- [ ] Shutdown clears long-running sources and does not leave persisted state stale

## Animation / Assets

- [ ] Canonical artwork remains active
- [ ] No legacy fallback artwork appears
- [ ] No baked checkerboards
- [ ] No gray matte / halo pixels
- [ ] Eye highlights remain consistent
- [ ] New one-shot animations play exactly once unless explicitly authored to loop
- [ ] Level-up and emote-unlock sequencing does not visibly fight normal behavior

## Nameplate / Speech Surface

- [ ] Nameplate stays hidden during ordinary idle when Mochi is not hovered
- [ ] Hover shows the nameplate immediately at full opacity
- [ ] Leaving hover fades the nameplate out rather than leaving it persistent
- [ ] Speech bubble always takes priority over the nameplate
- [ ] After speech ends, the nameplate lingers briefly and then fades away
- [ ] Hover during a fade restores full opacity cleanly
- [ ] Temporary care/interaction feedback can still surface the nameplate
- [ ] Bond progress and Focus bond hints still outrank the nameplate
- [ ] Nameplate remains non-targetable and does not interfere with click/drag/right-click
- [ ] Repeated hover/speech cycles do not leave the nameplate stuck visible or transparent

## Timers / Long-running Sources

- [ ] Ambient timers do not accumulate
- [ ] Idle timers do not compete with direct interactions
- [ ] Double-click correctly cancels pending single-click behavior
- [ ] Focus start → stop → start creates only one active timer
- [ ] Pause freezes Focus time and reward accumulation
- [ ] Rain audio does not create duplicate playback channels
- [ ] Focus/rain sources are removed on stop and shutdown

## Bond Progression

- [ ] Bond state restores after restart
- [ ] Typing awards bond XP without duplicate tick sources
- [ ] Feed awards bond progress only after a completed feed
- [ ] Repeated/spam feeding does not create unbounded orb backlog
- [ ] XP progress UI matches persisted bond state
- [ ] Crossing a level threshold advances exactly once
- [ ] Repeated updates at the same level do not replay the level-up celebration

## Feed

- [ ] Feed is rejected safely during sleeping/waking/pickup/drag/Fedora/eating states
- [ ] Feed can interrupt only allowed lower-priority behavior
- [ ] Eating sound fires once at the authored frame
- [ ] Completed feed chains into heart once
- [ ] Interrupted/stale feed completion does not award progress or fire completion behavior
- [ ] Feed → heart → idle leaves click/right-click/drag usable

## Emote Catalogue

- [ ] Catalogue opens from the normal UI path
- [ ] `Ctrl + Alt + E` opens the catalogue when the GNOME helper is available
- [ ] Locked, unlocked, and coming-soon states match the current bond level
- [ ] Implemented emotes animate on hover without restarting uncontrollably
- [ ] Placeholder/mystery entries remain non-interactive where intended
- [ ] Closing/reopening the catalogue does not leak windows/timers
- [ ] Newly unlocked idle emotes become eligible only at the correct bond level

## Level-up / Unlock Presentation

- [ ] Real level-up plays the authored level-up animation once
- [ ] Level-up sound plays once for a real level-up
- [ ] Level-up card reflects the new bond level
- [ ] Unlock card appears only for newly unlocked emotes
- [ ] Newly learned emote demo plays once after its anticipation delay
- [ ] Focus/typing/feed XP crossing a threshold uses the same authoritative level-up flow
- [ ] Direct interaction and shutdown cannot leave level-up presentation stuck

## Focus with Mochi

- [ ] Setup accepts 5–120 minute focus blocks, 1–30 minute breaks, and 1–8 rounds
- [ ] Menu/setup thinking animation enters and exits cleanly
- [ ] Start transitions into the writing loop
- [ ] Pause → resume preserves elapsed/reward accounting
- [ ] Stop keeps earned whole-minute XP and gives no completion bonus
- [ ] Break time gives no XP
- [ ] Full configured completion grants the completion bonus exactly once
- [ ] Final-minute XP is retained at reward boundaries
- [ ] Start → stop → start works without duplicate timers/audio
- [ ] Hidden/reopened timer window reflects the same live session
- [ ] Held primary click, drag, feed, and right-click can temporarily interrupt presentation without stopping the clock
- [ ] Manual Sleep settles earned XP and pauses the Focus session
- [ ] Focus crossing a bond level produces coherent level-up feedback
- [ ] Application shutdown settles/persists pending earned XP

## Focus Rain Audio

- [ ] Rain starts only when enabled
- [ ] Rain volume changes do not restart playback unnecessarily
- [ ] Pause/stop/session transitions leave audio in the intended state
- [ ] Missing/unavailable audio backend fails safely
- [ ] Shutdown stops the long-running soundscape channel

## AmbiSense Helper Lifecycle (#58)

Automated coverage: `python -m pytest tests/test_helper_lifecycle.py`.

With GJS installed and session-bus access, run the real D-Bus integration check:

`MOCHI_RUN_DBUS_TESTS=1 python -m pytest tests/test_helper_dbus_integration.py`

It uses a private test name and covers helper-backed adapters, late startup,
already-running startup, same-process extension restarts, and process restarts.
It does not enable, disable, or replace the installed GNOME extension.

Fresh Fedora GNOME/Wayland/XWayland QA:

- [ ] Start Mochi with the extension disabled, then enable it while a file manager or terminal is focused; verify the current context appears
- [ ] Start Mochi with the extension already enabled; verify initial context
- [ ] Disable the extension while contextual behavior is active; verify stale file/app/video/presence state clears and typing fallback still works
- [ ] Re-enable repeatedly; verify each transition is delivered once and current context returns without restarting Mochi
- [ ] During a helper outage, verify MPRIS playback and Downloads activity remain functional
- [ ] Stop Mochi and verify no later helper events affect it

## Update Service / Install Lifecycle

- [ ] Automatic update check stays quiet when offline and never blocks startup
- [ ] One newly discovered target produces at most one update speech bubble
- [ ] **Later** suppresses repeat announcements for the same target commit
- [ ] **Check for updates** works repeatedly from the context menu
- [ ] Opening/closing the updater leaves the context menu usable
- [ ] Drag still works after opening/closing the updater
- [ ] Background update discovery does not interrupt Sleep, Focus, pickup/drag, or ambient ownership
- [ ] **Update & Restart** downloads/stages the exact commit that was approved
- [ ] Cancel before runtime swap leaves the current installation untouched
- [ ] Cancel/close is unavailable once the critical swap/restart phase begins
- [ ] Successful update preserves Bond XP, unlocks, position, audio, Focus, and ordinary config
- [ ] Candidate-install failure leaves the current runtime untouched
- [ ] Integration-refresh or startup-handshake failure restores the prior runtime
- [ ] Update bootstrap/temp workspaces are cleaned after success, failure, or cancellation
- [ ] GNOME helper refresh notice remains informative and non-blocking
- [ ] Updated Mochi relaunches from the updater and from the GNOME app grid
- [ ] `mochi-update` and in-app updating use the same exact-target transaction path

## Release Gate

- [ ] Relevant focused tests pass
- [ ] Full `python -m pytest -q` suite passes
- [ ] Python compilation passes
- [ ] `git diff --check` passes
- [ ] Fresh wheel builds
- [ ] Wheel contains expected sprite/audio assets
- [ ] Package/runtime version strings agree
- [ ] README, changelog, wiki, and regression docs match shipped behavior
- [ ] Live Fedora/GNOME/Wayland/XWayland smoke/torture test passes
- [ ] Known issues are documented rather than silently claimed fixed
