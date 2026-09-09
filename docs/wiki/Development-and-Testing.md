# Development and Testing

Mochi's development process should optimize for reliable iteration rather than maximum change volume.

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

This is especially important for animation, input, context-menu, and state-machine changes because several past regressions only appeared after one feature interrupted another.

## Development environment

Primary environment:

- Fedora Linux
- GNOME
- Wayland desktop session
- XWayland where required
- Python 3.11+
- GTK4 / PyGObject
- Cairo

Common setup from the repository:

```bash
sudo dnf install python3 python3-gobject gtk4 gtk4-layer-shell
python3 -m pip install -e .
```

Launch:

```bash
mochi
```

Useful development commands:

```bash
mochi --debug
mochi --reset-position
mochi --preview-animations
python3 -m unittest discover -s tests -v
```

## Test layers

Mochi needs more than one kind of validation.

### 1. Focused unit/regression tests

Run the smallest relevant test first when diagnosing a bug.

Examples:

- animation definition tests
- state-transition tests
- drag motion tests
- click/double-click arbitration tests
- context-menu lifecycle tests
- asset alpha/dimension tests

A good bug fix starts with a reproducible failure whenever practical.

### 2. Full unit suite

Before declaring a behavior change complete:

```bash
python3 -m unittest discover -s tests -v
```

A focused test passing is not enough if another interaction regressed.

### 3. Python compilation

Run:

```bash
python3 -m compileall -q src tests
```

This catches syntax/import errors across files that a narrow test might not import.

### 4. Diff validation

Run:

```bash
git diff --check
```

This catches whitespace/errors that should not reach a checkpoint.

### 5. Package build

Build a fresh wheel:

```bash
python3 -m pip wheel . --no-deps --no-build-isolation -w /tmp/mochi-wheel
```

Then inspect the wheel contents when assets changed.

Verify:

- manifest is included
- expected PNG/spritesheets are included
- no obsolete art is packaged unintentionally
- package metadata is correct

### 6. Live GTK/XWayland validation

Some bugs cannot be proven away with pure unit tests.

Live tests are required for:

- context-menu input grabs
- drag responsiveness
- re-grabbing
- right-click after movement
- animation continuity
- transparency/visual artifacts
- compositor/window behavior

## Interaction torture test

After changes to input/state code, deliberately try to break Mochi.

Suggested sequence:

```text
idle
→ click
→ click
→ double-click
→ drag
→ drop
→ drag again
→ drop
→ right-click → Computer
→ right-click → Emote
→ right-click → Walk
→ interrupt/continue interactions
→ Sleep
→ Wake
→ drag
→ heart
→ drag
```

Also test messy input:

- rapid click/double-click
- repeated right-click open/close
- immediate release after pickup
- re-grab during or immediately after put-down
- drag after context menu closes
- direct input during ambient typing

Pass conditions:

- no freeze
- no invisible input interception
- no Python exception
- no persistent GTK warning
- no stuck behavioral state
- no duplicate ambient timers
- no legacy sprite popping
- no checkerboards/gray halo
- right-click and drag still work afterward

## Soak testing

Before alpha checkpoints, leave Mochi running and interact with him repeatedly for an extended period.

Watch for:

- rising CPU use
- rising memory use
- timer accumulation
- repeated warnings
- state drift
- one-shot animations that fail to return
- context menu eventually becoming unresponsive

A short smoke test proves launch stability. A soak test helps expose lifecycle leaks.

## Debugging workflow

When a regression appears:

1. reproduce the exact interaction sequence
2. record the observed state/action order
3. rank likely causes
4. add a focused regression test when possible
5. make the smallest fix that addresses the confirmed cause
6. run focused tests
7. run the full suite
8. test the real GTK interaction
9. checkpoint

Do not begin with a repository-wide cleanup or architectural rewrite unless evidence shows the architecture itself is the root cause.

## Git checkpoint discipline

Checkpoint before:

- replacing a canonical animation set
- changing context-menu lifecycle
- changing drag architecture
- modifying state priority
- broad file cleanup
- packaging changes

After a successful feature:

```bash
git status
git diff --check
python3 -m unittest discover -s tests -v
git add -A
git commit -m "Describe the completed change"
```

Avoid allowing several unrelated changes to accumulate uncommitted.

## Development permissions

Automated GUI testing may trigger GNOME/Wayland remote-desktop or synthetic-input permissions.

These permissions belong to the development/test environment only.

Mochi's normal runtime must not request:

- remote desktop
- screen sharing
- screen recording
- synthetic input control

If a runtime code change introduces one of these dependencies, treat it as a design regression unless explicitly justified.

## Definition of a completed runtime change

A behavior change is complete when:

- [ ] implementation is scoped
- [ ] relevant focused tests pass
- [ ] full test suite passes
- [ ] Python compilation passes
- [ ] `git diff --check` passes
- [ ] package builds when packaging is affected
- [ ] asset package audit passes when assets are affected
- [ ] live interaction behaves correctly
- [ ] no unrelated behavior changed
- [ ] clean Git checkpoint exists

This process may feel slower than stacking many features in one session, but it makes development much faster over time because working states remain recoverable.
