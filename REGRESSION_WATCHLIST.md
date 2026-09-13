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

## AmbiSense helper lifecycle (#58)

Automated coverage: `python -m pytest tests/test_helper_lifecycle.py`.
The helper now exports `GetState` (idle, file-browser focus, YouTube focus,
coarse app category). Update/reload the extension along with Mochi to enable
initial snapshots. Older extensions still deliver live signals but cannot
provide a snapshot. Adapter startup success means the name watch is installed;
the helper may still be absent. No helper discovery timer is used.

Fresh Fedora GNOME/Wayland/XWayland QA:

- [ ] Start Mochi with the extension disabled, then enable it while a file
      manager or terminal is focused; verify the current context appears.
- [ ] Start Mochi with the extension already enabled; verify initial context.
- [ ] Disable the extension while contextual behavior is active; verify stale
      file/app/video/presence state clears and typing fallback still works.
- [ ] Re-enable repeatedly; verify each transition is delivered once and current
      context returns without restarting Mochi.
- [ ] During a helper outage, verify MPRIS playback and Downloads activity remain
      functional; stop Mochi and verify no later helper events affect it.
