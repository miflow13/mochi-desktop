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
- right-click works after Feed/Eating
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
- eating → heart → `IDLE` / ambient recovery
- put-down → `IDLE`
- wake → `IDLE`

## 3. New animation import suddenly shows old/noncanonical Mochi

### Symptoms

- idle or click design changes unexpectedly
- manifest frame counts change
- some new art appears while other states regress

### Historical cause

An external animation set was copied wholesale over `assets/mochi/`, overwriting canonical artwork and replacing manifest mappings.

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

Drag frames did not preserve canonical eye-highlight pixels.

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

The repository has historically shown different version values between README development status and `pyproject.toml` package metadata.

Before a release:

- choose the release version
- update package metadata
- update README/wiki release status
- build a fresh wheel
- verify filename/version

Treat this as release housekeeping, not a runtime behavior bug.

## 12. Drag pose lags behind a left/right reversal on XWayland

### Symptoms

- Mochi is dragged quickly in one direction, then reversed
- the window follows the pointer but the sprite briefly keeps leaning the old way
- one drag direction may look correct while the opposite direction feels delayed

### Historical cause

Reading the X11 window position back immediately after moving it adds compositor/server latency. The visual velocity sample can therefore describe an older position than the pointer-owned target that actually drove the drag.

### Fix principle

While XWayland drag owns the pointer, `WindowPlacement.position` is the authoritative target. Use that target directly for velocity and pose selection instead of waiting for X11 readback.

### Verify

- rapid left → right and right → left reversals change rendered pose immediately
- authored left/right drag sprites remain distinct
- pickup sway and put-down still work after reversals
- edge clamping remains solid
- visible dialogue follows Mochi during fast movement

## 13. Fedora Mode gets stuck, exits early, or loses its hat after interruption

### Symptoms

- intro finishes but the held loop does not begin
- toggling off during the intro skips the outro
- drag/pickup removes the Fedora art permanently
- sleep or another ambient state takes over while Fedora Mode is still active
- Fedora Mode appears finished visually while its active/exiting flags remain set

### Ownership rule

Fedora Mode is an explicitly user-held presentation mode:

```text
secret gesture
→ FEDORA + intro
→ held loop
→ secret gesture
→ outro
→ IDLE
→ resume eligible ambient context
```

Direct pointer interaction may temporarily own the state machine, but it must not silently cancel an active Fedora hold.

### Verify

- enter only from allowed states
- intro → loop
- toggle-off during intro → outro after intro finishes
- pickup/drag/drop → Fedora loop resumes while still active
- toggle-off after direct interaction → outro → `IDLE`
- sleep cannot silently override active/exiting Fedora Mode
- Feed is rejected while Fedora Mode owns presentation
- shutdown clears Fedora active/exiting flags

## 14. Feeding duplicates audio, awards stale completion, or leaves the menu grabbing input

### Symptoms

- Feed is selected and later right-click/drag stops working
- eating sound plays twice
- interrupted eating still triggers the heart/completion hook
- multiple Feed clicks stack reactions

### Ownership rule

Feed must use the same proven deferred context-menu lifecycle as other actions. `EATING` owns the one-shot while active, and completion only counts if the finished animation is still the current eating reaction.

The eating sound is frame-synchronized: it fires only when the active animation crosses authored frame 2. A held frame, stale callback, or interrupted feed must not replay it.

### Verify

```text
menu → Feed → menu fully closes → EATING
EATING frame 2 → one eat sound
EATING completes → heart → IDLE / ambient recovery
```

Also test:

- Feed while sleeping/waking/pickup/drag/drop/Fedora/eating is rejected
- Feed interrupts lower-priority walk/emote safely
- interrupted eating does not trigger stale heart/completion behavior
- repeated Feed actions do not stack audio or animations
- right-click and drag still work afterwards

## 15. Contextual app/media states replay or remain stale

### Symptoms

- terminal/VS Code animations restart repeatedly while focus never changed
- switching apps leaves the old coworking presentation active
- browser focus produces a false watching state
- paused/stopped media leaves Mochi watching or dancing
- helper restart produces duplicated transitions

### Rule

Detection and presentation should be edge-triggered. Repeated detection of the same already-active condition should not restart the presentation.

Raw helper/MPRIS state may change independently, but presentation should resolve through one coherent priority/state path.

### Verify

- terminal and VS Code enter once per real context change
- terminal ↔ VS Code transitions without waiting for an unrelated idle timer
- browser focus alone does not manufacture YouTube/watchable-video activity
- music and video classification remain distinct
- pause/stop/focus loss clears stale presentation
- direct interaction can interrupt contextual presentation cleanly
- helper loss clears helper-owned context without breaking independent MPRIS/Downloads activity
- helper re-enable delivers one transition and current state without restarting Mochi

## Regression checklist before merging interaction changes

- [ ] context menu releases input before dispatch
- [ ] right-click works after Walk
- [ ] right-click works after Sleep/Wake
- [ ] right-click works after Feed/Eating
- [ ] drag works after context menu
- [ ] blink returns behavioral state to `IDLE`
- [ ] every temporary state has an exit
- [ ] pickup/drag/put-down interruption paths recover
- [ ] rapid XWayland drag reversals update pose immediately
- [ ] Fedora intro/loop/outro and interruption recovery work
- [ ] feeding audio/completion fires exactly once on valid completion paths
- [ ] repeated contextual signals do not restart active presentation
- [ ] direct input interrupts lower-priority ambient behavior
- [ ] no legacy art appears
- [ ] no baked checkerboards
- [ ] no gray matte/halo
- [ ] eye highlights remain canonical
- [ ] ambient timers do not accumulate
- [ ] double-click cancels pending single-click
- [ ] full tests pass or pre-existing failures are explicitly reconciled
- [ ] `git diff --check` passes
- [ ] live Fedora GNOME/Wayland/XWayland test passes

## When to stop and checkpoint

If a fix restores a known-good interaction sequence, checkpoint it before attempting broader cleanup or polish.

A small stable commit is more valuable than a larger session containing three correct fixes and one unverified migration.
