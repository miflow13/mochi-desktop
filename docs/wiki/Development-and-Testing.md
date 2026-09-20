# Development and Testing

Mochi's development process optimizes for reliable iteration rather than maximum change volume.

## Core workflow

Use this loop for runtime changes:

```text
one meaningful change
→ focused test
→ full suite
→ live visual/input test
→ clean Git checkpoint
→ next change
```

This is especially important for animation, input, context-menu, bond, Focus, and state-machine changes because lifecycle regressions often appear only when one system interrupts another.

## Development environment

Primary environment:

- Fedora Linux
- GNOME
- Wayland desktop session
- XWayland where required
- Python 3.11+
- GTK4 / PyGObject
- Cairo

Complete the [Fedora runtime/helper setup](../../README.md#install), then create an editable environment:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m pip install pytest
```

Launch:

```bash
mochi
```

Useful modes:

```bash
mochi --debug
mochi --reset-position
mochi --preview-animations
```

## Test layers

### 1. Focused regression tests

Run the smallest relevant test first.

Examples include:

- animation/state transition tests
- context-menu lifecycle tests
- drag/pickup tests
- bond/persistence tests
- feeding tests
- emote catalogue/shortcut tests
- level-up presentation tests
- Focus/reward/audio tests
- helper lifecycle tests

A good bug fix starts with a reproducible failure whenever practical.

### 2. Full pytest suite

Before declaring a behavior change complete:

```bash
python -m pytest -q
```

Some D-Bus/GJS integration coverage is opt-in because it requires session-bus access:

```bash
MOCHI_RUN_DBUS_TESTS=1 python -m pytest tests/test_helper_dbus_integration.py
```

Report environmental skips accurately rather than treating them as passes.

### 3. Python compilation

```bash
python -m compileall -q src tests
```

### 4. Diff validation

```bash
git diff --check
```

### 5. Package build

```bash
python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mochi-wheel
```

When packaging or assets changed, inspect the wheel and verify:

- package/runtime version
- manifest
- expected PNG assets
- level-up/feed/focus/emote assets
- short interaction audio
- Focus soundscape audio
- no obsolete art

### 6. Live GTK/XWayland validation

Unit tests cannot prove away compositor/input issues.

Live tests are required for:

- context-menu input grabs
- drag responsiveness and re-grab
- right-click after movement/reactions
- catalogue window lifecycle
- Focus timer/setup window behavior
- Rain audio lifecycle
- level-up/unlock presentation
- transparency/visual artifacts
- workspace/Overview behavior
- multi-monitor/scaling behavior

## v0.3 interaction torture test

Deliberately try to break Mochi:

```text
idle
→ click
→ double-click
→ triple-click
→ drag/drop
→ drag again
→ right-click → Feed
→ heart/recover
→ open Emote Catalogue → hover several entries → close/reopen
→ right-click → Focus
→ start → pause → resume
→ drag during Focus
→ right-click during Focus
→ Feed during Focus
→ Stop
→ Start again
→ manual Sleep during Focus
→ wake
→ complete a short Focus session
→ trigger/cross a bond level if practical
→ right-click
→ drag
```

Also test messy input:

- rapid click/double-click
- repeated right-click open/close
- immediate release after pickup
- re-grab during release settle
- menu while sleeping
- feed spam
- catalogue open/close loops
- Focus start/stop/start loops
- hide/reopen Focus timer
- Rain volume changes
- direct input while Focus writing is active
- shutdown during active Focus
- shutdown while bond XP is pending

Pass conditions:

- no freeze
- no invisible input interception
- no Python exception
- no stuck behavioral/presentation state
- no duplicate ambient/focus/audio timers
- correct bond persistence
- correct reward boundaries
- no repeated level-up from stale state
- no legacy sprite popping
- no checkerboards/gray halo
- right-click and drag still work afterward

## Soak testing

Before alpha checkpoints, leave Mochi running for an extended period and use normal desktop activity.

Watch for:

- rising CPU/memory
- timer accumulation
- audio sources that never stop
- repeated warnings
- state drift
- repeated level-up/unlock presentation
- Focus reward drift
- catalogue/window leaks
- context menu eventually becoming unresponsive

A short smoke test proves launch stability. A soak test helps expose lifecycle leaks.

## Debugging workflow

When a regression appears:

1. reproduce the exact interaction sequence
2. record observed state/action order
3. identify the owning subsystem
4. add a focused regression test when practical
5. make the smallest fix addressing the confirmed cause
6. run focused tests
7. run the full suite
8. test the real GTK interaction
9. checkpoint

Fix the source of a bad event/state rather than merely hiding its visible animation.

## Git checkpoint discipline

Checkpoint before:

- replacing canonical animation assets
- changing context-menu lifecycle
- changing drag architecture
- changing state priority
- changing bond persistence/progression
- changing Focus timer/reward lifecycle
- changing long-running audio ownership
- broad file cleanup
- packaging/version changes

Typical verification:

```bash
git status
git diff --check
python -m pytest -q
python -m compileall -q src tests
```

Avoid accumulating unrelated changes in one branch.

## Development permissions

Development automation may use desktop-control permissions.

Mochi's normal runtime must not require:

- remote desktop
- screen sharing
- screen recording
- synthetic input control

If runtime code introduces one of these dependencies, treat it as a design regression unless explicitly justified.

## Definition of a completed runtime change

- [ ] implementation is scoped
- [ ] relevant focused tests pass
- [ ] full pytest suite passes
- [ ] Python compilation passes
- [ ] `git diff --check` passes
- [ ] package builds when relevant
- [ ] packaged assets are audited when relevant
- [ ] live interaction behaves correctly
- [ ] persistence/reward behavior is verified when relevant
- [ ] no unrelated behavior changed
- [ ] documentation/regression list updated when public behavior changed
- [ ] clean Git checkpoint exists
