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

## Regression checklist before merging interaction changes

- [ ] context menu releases input before dispatch
- [ ] right-click works after Walk
- [ ] right-click works after Sleep/Wake
- [ ] drag works after context menu
- [ ] blink returns behavioral state to `IDLE`
- [ ] every temporary state has an exit
- [ ] pickup/drag/put-down interruption paths recover
- [ ] direct input interrupts ambient behavior
- [ ] no legacy art appears
- [ ] no baked checkerboards
- [ ] no gray matte/halo
- [ ] eye highlights remain canonical
- [ ] ambient timers do not accumulate
- [ ] double-click cancels pending single-click
- [ ] full tests pass
- [ ] `git diff --check` passes
- [ ] live GTK/XWayland test passes

## When to stop and checkpoint

If a fix restores a known-good interaction sequence, checkpoint it before attempting broader cleanup or polish.

A small stable commit is more valuable than a larger session containing three correct fixes and one unverified migration.
