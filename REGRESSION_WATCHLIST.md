# Mochi Regression Watchlist

Use this after changes that touch interaction, state, input, windowing, presence,
animation, audio, or lifecycle behavior. Not every checkbox applies to every PR,
but the core interaction checks plus the relevant feature section should be
verified before merge.

## Core input / Context Menu

- [ ] Context menu does not leave an invisible GTK input grab
- [ ] Repeated open / close cycles still accept input
- [ ] Right-click works after Walk
- [ ] Right-click works after Sleep / Wake
- [ ] Right-click works after Feed / Eating
- [ ] Drag still works after using the context menu
- [ ] Context-menu actions begin only after the menu has released input

## State Machine / Interruption

- [ ] Blink returns behavioral state to `IDLE`
- [ ] Temporary animation states always have an exit path
- [ ] Pickup / drag / put-down cannot leave Mochi stuck
- [ ] Direct user input correctly interrupts lower-priority ambient behavior
- [ ] Repeated detection of an already-active contextual state does not restart it
- [ ] Leaving a contextual state restores the correct idle / ambient behavior
- [ ] Switching directly between contextual states does not require an idle timeout

## Pickup / Drag / XWayland

- [ ] Idle → pickup → immediate release recovers cleanly
- [ ] Pickup → held → release reaches put-down / idle correctly
- [ ] Put-down → immediate re-grab works
- [ ] Rapid left / right reversals update the drag pose immediately
- [ ] Left and right drag poses remain visually distinct
- [ ] Fast drag → release → right-click still works
- [ ] Desktop-edge clamping remains solid without spring-back or drift
- [ ] Visible speech bubbles stay attached to Mochi during fast XWayland dragging

## Fedora Mode

- [ ] Secret gesture enters Fedora Mode only from an allowed state
- [ ] `fedora_intro` completes into the held `fedora_loop`
- [ ] Toggling off during the intro still completes through `fedora_outro`
- [ ] Pickup / drag may temporarily interrupt the art, then resume the loop while active
- [ ] Ending Fedora Mode after a direct interaction still reaches the outro and `IDLE`
- [ ] Sleep does not silently override active / exiting Fedora Mode
- [ ] Feed is rejected while Fedora Mode owns presentation
- [ ] Fedora Mode shutdown clears active / exiting flags without orphaned behavior

## Feeding / Eating

- [ ] Feed closes the context menu before starting `EATING`
- [ ] Feeding is rejected in sleeping, waking, pickup, dragged, dropping, Fedora, and eating states
- [ ] Starting Feed cancels lower-priority walk / emote behavior without getting stuck
- [ ] Eat sound fires exactly once when frame 2 is crossed
- [ ] Interrupted or stale eating callbacks do not fire completion behavior
- [ ] Completed eating chains into the heart reaction exactly once
- [ ] Feed → heart → idle / ambient recovery completes cleanly
- [ ] Repeated Feed actions cannot stack duplicate animations or sounds

## Contextual Presence / Media

- [ ] Terminal / VS Code context enters once and does not replay on duplicate signals
- [ ] Switching terminal ↔ VS Code updates presentation without stale coworking state
- [ ] Browser focus alone does not manufacture a false YouTube / watching state
- [ ] Music and watchable-video detection remain distinct
- [ ] Pause / stop / focus loss clears stale watching or dancing presentation
- [ ] Direct interaction can interrupt contextual presentation and ambient recovery is deterministic
- [ ] Helper loss clears stale file / app / video / presence state while independent MPRIS and Downloads activity keep working

## Speech / Nameplate / Overlay Surfaces

- [ ] Speech / nameplate surfaces never steal Mochi's click, right-click, or drag input
- [ ] No invisible overlay remains mapped after dismissal
- [ ] Existing dialogue is preserved rather than duplicated when a drag starts
- [ ] Bubble / nameplate timers do not outlive shutdown or recreate dismissed UI

## Animation / Assets / Audio

- [ ] Canonical handcrafted runtime artwork remains active
- [ ] `assets/mochi/manifest.json` still matches runtime files and frame order
- [ ] No legacy fallback artwork appears
- [ ] No baked checkerboards
- [ ] No gray matte / halo pixels
- [ ] Eye highlights remain consistent
- [ ] Nearest-neighbor scaling remains crisp at supported sizes
- [ ] Missing optional audio assets fail safely without breaking interaction

## Timers / Scheduling

- [ ] Ambient timers do not accumulate
- [ ] Idle timers do not compete with direct interactions
- [ ] Double-click correctly cancels pending single-click behavior
- [ ] Feature-specific follow / cooldown timers have one clear owner and cancel path
- [ ] Shutdown removes timers, helper watches, and late callbacks cleanly

## Before merging interaction changes

- [ ] Relevant targeted tests pass
- [ ] `python -m pytest tests/test_feeding.py tests/test_fedora_mode.py` passes when those systems changed
- [ ] `python -m pytest tests/test_drag_motion.py tests/test_drag_visuals.py` passes when drag changed
- [ ] Full test suite passes, or any pre-existing failures are explicitly reconciled
- [ ] `git diff --check` passes
- [ ] Live Fedora GNOME / Wayland / XWayland test passes
- [ ] Mika verifies the changed behavior on real Fedora / Wayland hardware before merge

## AmbiSense helper lifecycle (#58)

Automated coverage: `python -m pytest tests/test_helper_lifecycle.py`.
With GJS installed and session-bus access, run the real D-Bus integration check:
`MOCHI_RUN_DBUS_TESTS=1 python -m pytest tests/test_helper_dbus_integration.py`.
It uses a private test name and covers all helper-backed adapters, late startup,
already-running startup, same-process extension restarts, and process restarts.
It does not enable, disable, or replace the installed GNOME extension.
The helper exports `GetState` (idle, file-browser focus, YouTube focus,
coarse app category). Update / reload the extension along with Mochi to enable
initial snapshots. Older extensions still deliver live signals but cannot
provide a snapshot. Adapter startup success means the name watch is installed;
the helper may still be absent. No helper discovery timer is used.

Fresh Fedora GNOME / Wayland / XWayland QA:

- [ ] Start Mochi with the extension disabled, then enable it while a file
      manager or terminal is focused; verify the current context appears
- [ ] Start Mochi with the extension already enabled; verify initial context
- [ ] Disable the extension while contextual behavior is active; verify stale
      file / app / video / presence state clears and typing fallback still works
- [ ] Re-enable repeatedly; verify each transition is delivered once and current
      context returns without restarting Mochi
- [ ] During a helper outage, verify MPRIS playback and Downloads activity remain
      functional; stop Mochi and verify no later helper events affect it
