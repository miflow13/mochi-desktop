known failure modes
## input / Context Menu

- [ ] Context menu does not leave an invisible GTK input grab
- [ ] Right-click works after Walk
- [ ] Right-click works after Sleep/Wake
- [ ] Drag still works after using the context menu

## State Machine

- [ ] Blink returns behavioral state to `IDLE`
- [ ] Temporary animation states always have an exit path
- [ ] Pickup / drag / put-down cannot leave Mochi stuck
- [ ] Direct user input correctly interrupts ambient behavior

## Animation / Assets

- [ ] Canonical PixelLab artwork remains active
- [ ] No legacy fallback artwork appears
- [ ] No baked checkerboards
- [ ] No gray matte / halo pixels
- [ ] Eye highlights remain consistent

## Timers

- [ ] Ambient timers do not accumulate
- [ ] Idle timers do not compete with direct interactions
- [ ] Double-click correctly cancels pending single-click behavior

## Before merging interaction changes

- [ ] Relevant unit tests pass
- [ ] Full test suite passes
- [ ] `git diff --check` passes
- [ ] Live GTK/XWayland test passes
