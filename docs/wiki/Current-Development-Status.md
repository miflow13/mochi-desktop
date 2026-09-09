# Current Development Status

> Snapshot date: **2026-09-08**
>
> This page is a development handoff snapshot, not a permanent release contract. Update it after the next known-good checkpoint.

## Project phase

**Phase 2 — Make Mochi Feel Alive**

The immediate goal is to finish and stabilize the interaction core before adding more systems.

## Last fully validated development baseline

Before pickup/put-down transition work began, the development tree had a known-good checkpoint with:

- Computer action in the context menu
- transparent heart animation
- corrected drag eye highlights
- corrected drag transparency/gray matte
- subtle visual drag inertia
- double-click heart arbitration
- ambient typing behavior
- 60 passing tests
- clean `git diff --check`
- successful wheel build
- successful XWayland launch smoke test

Treat later pickup/put-down changes as work-in-progress until the full validation gate is rerun.

## Current interrupted work

The current transition work adds:

```text
IDLE
→ PICKUP
→ HELD / DRAG
→ PUT_DOWN
→ IDLE
```

New transition assets were created for:

```text
assets/mochi/pickup/spritesheet.png
assets/mochi/put_down/spritesheet.png
```

Each transition was designed as a six-frame non-looping strip with locked endpoints:

- pickup begins from the exact idle pose
- pickup ends at the held pose
- put-down begins at the held pose
- put-down ends at the exact idle pose

The transition integration was edited into runtime/manifest/tests but had not yet received the full post-change validation pass at the time of this snapshot.

## First task at next development session

Do **not** begin with a new feature.

First:

1. inspect the current pickup/put-down implementation
2. finish the state/lifecycle integration if incomplete
3. validate quick release and re-grab paths
4. audit transition alpha/eyes/alignment/endpoints
5. verify typing/computer transparency
6. run full interaction torture test
7. run compilation, full tests, `git diff --check`, wheel build, and live XWayland test
8. create a clean checkpoint commit

## Required transition scenarios

```text
idle → pickup → held → put_down → idle
idle → pickup → immediate release
idle → pickup → fast drag → release
put_down → immediate re-grab
heart → idle → drag
computer → idle → drag
context menu → action → drag
```

Mochi must remain interactable after each sequence.

## Recovery history

A safety branch was created during the 2026-09-08 restoration work:

```text
backup-before-migration-restore-20260908
```

Backup commit:

```text
7aaec47
```

The restored development line was reconstructed from base commit:

```text
9b837a4
```

The backup preserves later experimental work for reference/recovery. Do not develop directly from it unless intentionally salvaging a specific change.

## Tonight / next checkpoint definition of done

- [ ] pickup/put-down flow finished and recoverable
- [ ] transition art passes transparency/eye/alignment checks
- [ ] typing spritesheet transparency verified/fixed
- [ ] full interaction torture test passes
- [ ] full unit suite passes
- [ ] Python compilation passes
- [ ] `git diff --check` passes
- [ ] fresh wheel builds and contains intended assets
- [ ] live XWayland smoke/soak passes
- [ ] clean Git checkpoint created

## What should wait

Until this checkpoint exists, avoid:

- large refactors
- repository-wide cleanup
- new progression systems
- more broad asset migrations
- major UI redesign
- adding multiple new emotes at once

The priority is to turn the current interaction core into a dependable baseline.
