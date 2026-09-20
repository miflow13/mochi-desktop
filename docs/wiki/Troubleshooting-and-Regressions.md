# Troubleshooting and Regressions

This page collects Mochi's highest-risk failure modes and the diagnostic patterns that have already proven useful.

The repository also contains `REGRESSION_WATCHLIST.md`. Keep that short checklist aligned with this deeper reference.

## 1. Context menu opens once, then Mochi stops accepting input

### Symptoms

- choose Walk/Sleep or another context-menu action
- Mochi moves or animates
- later right-click does not reopen the menu
- drag/click may also stop working
- Mochi appears alive visually but input is effectively frozen

### Historical cause

GTK popover dismissal is asynchronous.

Calling `Gtk.Popover.popdown()` starts closing the menu, but the popover may not yet have emitted `closed` or released its input grab. If Mochi moves the parent window immediately, an invisible/stale popover surface can continue intercepting input.

### Safe lifecycle

```text
select action
→ clear context/hover state
→ request popdown
→ wait for closed
→ defer one main-loop turn
→ start behavior
```

### Verify

- right-click works after Walk
- right-click works after Sleep/Wake
- drag works after any context action
- repeated context open/close works
- callback runs only after popover is hidden/unfocusable

## 2. Mochi looks idle but actions are rejected

### Symptoms

- idle sprite is visibly playing
- click/walk/drag requests seem ignored
- logs show a non-idle state such as `BLINKING`

### Historical cause

Animation completion resumed idle visuals without restoring behavioral state to `IDLE`.

### Fix principle

Visual state and behavioral state must transition together.

Every one-shot completion handler must explicitly end in a valid behavioral state.

### Verify

- blink → `IDLE`
- heart → `IDLE`
- typing → `IDLE`
- emote → `IDLE`
- put-down → `IDLE`
- wake → `IDLE`

## 3. New animation import suddenly shows old/noncanonical Mochi

### Symptoms

- idle or click design changes unexpectedly
- manifest frame counts change
- some new art appears while other states regress

### Historical cause

An external animation set was copied wholesale over `assets/mochi/`, overwriting canonical PixelLab idle/squish binaries and replacing manifest mappings.

### Prevention

- migrate only the named state being replaced
- checkpoint first
- compare hashes/counts before and after
- keep old working states until replacements exist
- audit manifest missing/unreferenced files
- inspect the wheel contents

Do not solve a code issue by restoring/replacing unrelated artwork.

## 4. Checkerboard background appears around an emote

### Symptoms

- gray checkerboard is visible behind heart, typing, transition, or generated art
- PNG reports RGBA but still looks opaque

### Cause

The checkerboard was baked into RGB pixels; simply having an alpha channel does not guarantee transparency.

### Diagnostic check

Inspect:

- alpha extrema
- corner pixel alpha
- colors connected to transparent boundaries

### Fix principle

Remove only confirmed background/matte pixels. Preserve legitimate dark outline, shading, and highlights.

## 5. Gray halo around dragged Mochi

### Symptoms

- thin gray edge becomes obvious under nearest-neighbor scaling
- idle looks clean but drag looks matted

### Cause

Opaque low-saturation gray pixels existed in the source sprite around the silhouette.

Nearest-neighbor rendering exposed the source artifact; it did not create it.

### Verify

- no opaque gray-matte class connected to transparent background
- dark green/black outline remains
- every drag frame passes

## 6. Eyes turn solid black during drag

### Symptoms

- idle eyes have small highlights
- drag/held frames lose highlights and look like black blocks

### Cause

Generated drag frames did not preserve canonical eye-highlight pixels.

### Fix principle

Apply precise pixel-level correction to the existing strip. Avoid broad image regeneration when only the eyes are wrong.

Check every frame.

## 7. Pickup/release leaves Mochi stuck

### Symptoms

- release happens before pickup finishes
- Mochi remains in pickup/held state
- re-grab stops working
- right-click/click may be rejected

### Design requirement

Every interruption path must resolve deterministically.

At minimum test:

```text
idle → pickup → immediate release
pickup → held → release
put_down → immediate re-grab
fast drag → release → right-click
```

Do not assume users wait for one-shot animations to finish before interacting again.

## 8. Single-click and double-click both fire

### Symptoms

- double-click plays heart but also triggers squish/bounce
- reaction order feels noisy

### Cause pattern

Single-click action is dispatched before the double-click window closes.

### Arbitration pattern

```text
first click
→ schedule pending single-click
second click in threshold
→ cancel pending single-click
→ double-click reaction
```

Ensure only one pending click source exists.

## 9. Ambient typing happens too often or fights input

### Symptoms

- typing triggers back-to-back
- typing begins while dragging/walking/emoting
- idle timers multiply over time

### Cause pattern

Multiple unmanaged GLib timers or rescheduling without cancelling the owned source.

### Rule

Use one cancellable ambient scheduler. It may schedule the next idle opportunity only when ownership is clear.

Direct interaction outranks ambient behavior.

## 10. Packaged Mochi uses different art than checkout

### Symptoms

- source preview looks correct
- installed/packaged version shows stale art

### Cause

Working-tree assets and packaged data files differ, or an installed prefix contains an older asset set.

### Verify

- runtime manifest lookup path
- wheel file list
- packaged asset hashes or byte comparison
- stale `/usr/share` or environment-prefix assets when relevant

Do not assume a successful wheel build means it contains the intended files.

## 11. Version strings disagree

The current repository has historically shown different version values between README development status and `pyproject.toml` package metadata.

Before a release:

- choose the release version
- update package metadata
- update README/wiki release status
- build a fresh wheel
- verify filename/version

Treat this as release housekeeping, not a runtime behavior bug.

## 12. Feed finishes visually but bond/reaction state is wrong

### Symptoms

- eating animation completes but no heart follows
- bond progress is awarded after an interrupted feed
- repeated feeding creates an ever-growing visual orb backlog
- Mochi remains in `EATING`

### Rule

Only the currently owned, successfully completed `eat` animation may trigger feed completion behavior.

Interrupted/stale callbacks must not award progress, play completion feedback, or trigger the post-feed heart.

### Verify

- feed once → eating cue → heart → recover
- interrupt feed where allowed → no stale reward
- spam Feed → bounded visual backlog
- right-click/drag still works afterward

## 13. Bond level-up repeats or becomes stuck

### Symptoms

- celebration replays when the same level is restored/refreshed
- unlock card and emote demo overlap incorrectly
- presentation never returns to normal
- restart replays an already-seen level-up

### Rule

Level-up is triggered by a real level transition, not by repeatedly observing the same saved state.

The authoritative presentation sequence is:

```text
level changes
→ level-up animation/sound
→ level card
→ optional unlock card
→ learned-emote demo
→ recover
```

Test real threshold crossings from typing, Feed, and Focus reward paths.

## 14. Emote Catalogue leaks or shows the wrong lock state

### Symptoms

- catalogue cards do not update after bond changes
- hover previews keep running after close
- repeated open/close creates multiple windows/timers
- locked emotes appear available

### Verify

- lock state matches Bond Level
- newly unlocked entries refresh after level-up
- hover animation stops/cleans up on close
- `Ctrl + Alt + E` and normal UI open the same catalogue lifecycle
- repeated open/close remains responsive

## 15. Focus time, XP, or presentation drifts

### Symptoms

- final completed minute does not award XP
- pause/stop loses already-earned whole minutes
- break time earns XP
- start → stop → start creates duplicate ticking
- drag/menu/feed permanently replaces the writing presentation
- manual Sleep leaves Focus running visually or rewards incorrectly

### Rule

The Focus clock and reward accounting are separate from temporary presentation ownership.

Settle elapsed time before pause, stop, manual Sleep, and shutdown. Direct interactions may temporarily interrupt the visual while the session clock remains authoritative.

### Verify

- pause/resume
- stop near a minute boundary
- start → stop → start
- hide/reopen timer
- drag/feed/right-click during Focus
- manual Sleep during Focus
- full completion bonus exactly once
- level-up during Focus
- shutdown with pending earned XP

## 16. Rain audio duplicates or survives the session

### Symptoms

- two rain loops play at once
- volume changes restart the sound unexpectedly
- rain continues after stop/shutdown
- missing backend causes an exception

### Rule

Focus ambience is a long-running audio channel separate from short interaction sounds. It must have one owner and fail safely.

### Verify

- toggle Rain on/off
- change volume repeatedly
- pause/resume/stop
- start a second session
- shutdown during playback
- test unavailable/missing audio backend where practical

## Regression checklist before merging interaction changes

- [ ] context menu releases input before dispatch
- [ ] right-click works after Walk and Sleep/Wake
- [ ] drag works after context-menu actions
- [ ] menu open/close does not wake sleeping Mochi
- [ ] blink and every temporary state recover
- [ ] pickup/drag/release interruption paths recover
- [ ] Feed → heart → recovery works and stale Feed callbacks do not reward
- [ ] bond state persists across restart
- [ ] real level-up/unlock presentation plays once and recovers
- [ ] catalogue lock state/hover lifecycle is correct
- [ ] Focus pause/resume/stop/start reward boundaries are correct
- [ ] direct input during Focus resumes the correct presentation afterward
- [ ] Rain has one playback owner and stops on teardown
- [ ] direct input interrupts lower-priority ambient behavior
- [ ] no legacy art/checkerboards/gray matte appears
- [ ] ambient/Focus/audio timers do not accumulate
- [ ] double-click cancels pending single-click
- [ ] full pytest suite passes
- [ ] Python compilation passes
- [ ] `git diff --check` passes
- [ ] wheel/package asset audit passes
- [ ] package/runtime versions agree
- [ ] live Fedora/GNOME/Wayland/XWayland test passes

## When to stop and checkpoint

If a fix restores a known-good interaction sequence, checkpoint it before attempting broader cleanup or polish.

A small stable commit is more valuable than a larger session containing three correct fixes and one unverified migration.
