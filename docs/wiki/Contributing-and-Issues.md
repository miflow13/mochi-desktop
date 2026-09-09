# Contributing and Issues

Mochi is still in active development, so contributions should prioritize stability, clarity, and small reviewable changes.

## Before contributing

Read:

- the repository README
- [[Project Philosophy]]
- [[Interaction Core]]
- [[Development and Testing]]
- `REGRESSION_WATCHLIST.md`

If your change affects input, animation state, dragging, context-menu behavior, or asset loading, assume it can create regressions outside the exact feature being edited.

## Good contribution scope

Good pull requests are usually narrow:

- fix one reproducible bug
- replace one animation state
- improve one interaction path
- add one regression test
- improve one small piece of documentation
- improve packaging validation

Avoid combining unrelated work such as:

```text
new drag system
+ repository cleanup
+ UI redesign
+ asset migration
+ state-machine rewrite
```

Even individually reasonable changes become difficult to validate when bundled together.

## Issue categories

Useful issue labels/categories include:

- `bug`
- `enhancement`
- `animation`
- `input`
- `state-machine`
- `rendering`
- `ui`
- `alpha-blocker`
- `polish`
- `docs`

The exact label set may evolve, but issues should clearly distinguish release-blocking reliability problems from optional polish.

## Priority guidance

### Alpha blocker

Use for problems that prevent normal public-alpha use, including:

- crash
- input freeze
- context menu permanently intercepting input
- Mochi stuck in an invalid state
- pickup/drop fundamentally broken
- package fails to launch/install
- serious unexpected permission requirement

### High

A major interaction is broken, but Mochi remains generally usable.

### Medium

Noticeable regression or behavior inconsistency that should be fixed but does not block basic use.

### Low / polish

Visual feel, timing, minor animation quality, or optional UX improvements.

## Recommended bug format

```md
## 🌱 Summary

Briefly describe the issue.

## 🧩 Area

- [ ] Animation
- [ ] Input / mouse interaction
- [ ] Drag / pickup / put-down
- [ ] State machine
- [ ] Context menu
- [ ] Sleep / wake
- [ ] Walking
- [ ] Emotes
- [ ] Rendering / transparency
- [ ] Audio
- [ ] UI / overlay
- [ ] Packaging / installation
- [ ] Performance
- [ ] Other

## 🚨 Priority

- [ ] Alpha blocker
- [ ] High
- [ ] Medium
- [ ] Low / polish

## 🔁 Steps to reproduce

1.
2.
3.

## ✅ Expected behavior

What should Mochi do?

## ❌ Actual behavior

What happens instead?

## 🧠 State / interaction sequence

```text
IDLE
→ ...
→ FAILURE
```

## 💻 Environment

OS / distro:
Desktop environment:
Wayland / X11 / XWayland:
Mochi version / commit:
Python version:

## 🎯 Acceptance criteria

- [ ] root cause understood
- [ ] expected behavior works consistently
- [ ] Mochi remains interactable
- [ ] regression test added/updated
- [ ] full test suite passes
- [ ] live test passes when applicable
```

## Why interaction sequences matter

Mochi bugs are often lifecycle bugs rather than isolated visual bugs.

This:

```text
IDLE → RIGHT CLICK → WALK → DRAG → INPUT FREEZE
```

is usually more diagnostic than:

> Drag sometimes does not work.

Include the sequence whenever possible.

## Screenshots and recordings

Attach visual evidence for:

- checkerboard backgrounds
- matte/halo artifacts
- eye inconsistencies
- loop restart pops
- window placement problems
- context menu stuck on screen

For freeze/state bugs, include debug logs if available.

## Pull request expectations

A runtime PR should explain:

1. what was broken or missing
2. the confirmed cause or design need
3. the smallest implementation used
4. tests added/updated
5. manual/live scenarios tested
6. any remaining uncertainty

Do not describe a change as fully verified if compositor-level interaction was not actually tested.

## Required regression thinking

For interaction-related changes, verify that the fix does not break:

- single-click squish
- double-click heart
- pickup → drag → put-down
- context menu
- Walk
- Sleep/Wake
- Emote
- Computer/typing
- idle recovery

For art changes, verify:

- transparency
- no gray matte
- canonical eyes
- bottom-center alignment
- nearest-neighbor rendering
- no legacy art

## Asset contributions

Do not overwrite the entire Mochi asset tree to add one animation.

Preferred flow:

1. identify the exact state being replaced
2. preserve current working art for other states
3. add/replace only relevant files
4. update the manifest
5. run asset integrity tests
6. build/audit package
7. preview visually

## AI-assisted contributions

AI-assisted code or art is acceptable as part of the development process, but generated output should be treated like any other contribution:

- inspect it
- understand the change
- test it
- document relevant limitations
- do not merge generated assets without production QA

AI output does not reduce the acceptance standard.

## Project-management split

Mochi uses different tools for different layers of work:

- **GitHub Issues** — concrete bugs, regressions, and implementation tasks
- **Trello** — sprint planning and prioritization
- **Git commits / PRs** — actual implementation history
- **Wiki/docs** — durable knowledge and architecture guidance

Avoid duplicating entire issue descriptions in planning tools. Link between them instead.

## Contribution philosophy

The best contribution is not necessarily the biggest one.

A small fix that keeps Mochi responsive across every interaction is more valuable than a large feature that destabilizes the creature core.
