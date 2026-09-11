# Interaction Core

The **interaction core** is the minimum set of behaviors that makes Mochi feel like a responsive creature rather than a collection of disconnected animations.

For the public alpha, the interaction core matters more than progression systems or feature breadth.

## Core interaction graph

```text
IDLE
├── single click → SQUISH → IDLE
├── double click → HEART → IDLE
├── ambient idle → TYPING → IDLE
├── context menu → WALK / SLEEP / EMOTE / COMPUTER
└── PICKUP → DRAG → existing release-settle → IDLE
```

The guiding requirement is:

> **Mochi must always recover and remain interactable.**

A feature is not complete if its animation plays correctly but leaves Mochi unable to accept later input.

## Idle

Idle is the safe/default behavior state.

Expected behavior:

- gentle breathing/idle loop
- occasional low-frequency ambient actions
- accepts clicks, double-clicks, drag, and context-menu input
- serves as the return state for most one-shot reactions

Ambient behavior must never compete with direct input.

## Single click

A normal click should trigger a tactile reaction such as squish/bounce, then return to idle.

Requirements:

- one-shot playback
- no duplicate reaction timers
- clean return to `IDLE`
- no interference with a pending double-click

Because single- and double-clicks compete for the same initial input, single-click dispatch may need a short delay so the double-click path can cancel it.

## Double-click heart

Double-click should play the heart reaction without also firing the single-click reaction.

Required arbitration:

```text
first click
→ pending single-click reaction
→ second click arrives inside double-click window
→ cancel pending single-click
→ play HEART once
→ IDLE
```

The heart animation must be transparent and return through the normal animation-completion path.

## Ambient typing / Computer

The typing/computer animation has two entry paths:

1. ambient low-frequency idle behavior
2. explicit **Computer** action from the context menu

Ambient rules:

- only begin from genuine idle
- use one owned, cancellable timer
- randomized delay should not accumulate duplicate sources
- direct interaction preempts the ambient reaction
- one-shot playback returns to idle

The explicit context-menu action should use the same animation/state path rather than introducing a special duplicate implementation.

## Pickup → drag → release-settle

This is the most important continuous physical interaction.

Desired flow:

```text
IDLE
→ PICKUP
→ DRAG
→ existing release-settle
→ IDLE
```

### Pickup

Pickup is a non-looping transition from the exact idle pose to the existing drag pose.

Requirements:

- begins at the current/canonical idle endpoint
- ends by entering the existing drag visual/state
- no visual pop at the boundary
- interruption by a quick release must have a safe recovery path

### Drag

While dragging:

- drag animation may play once and hold a final frame, or use a clean loop depending on the authored asset
- dragging remains responsive
- subtle visual inertia may trail the cursor
- actual window/drop coordinates remain accurate
- eye highlights, transparency, and canonical silhouette remain consistent

### Release-settle

Release uses the established drag-settle behavior to recover to idle; it is not a
separate new animation pipeline.

Requirements:

- release triggers it once
- a release during pickup cancels the pickup and uses this same recovery path
- re-grabbing during or immediately after the transition must not leave Mochi stuck

### Required interruption cases

Test all of these:

```text
idle → pickup → immediate release
idle → pickup → long drag → release
idle → pickup → fast drag → release
release-settle → immediate re-grab
heart → idle → drag
computer → idle → drag
context menu → close → drag
```

Every path must resolve to a valid state.

## Hover

Hover currently has no visible behavior. The retired nametag/status overlay must
not be recreated as an incidental side effect of pointer handling.

If a future hover feature is added, attach its `enter`/`leave` signals to a
separate `Gtk.EventControllerMotion` in `Buddy`. Keep it independent of the
primary-click, primary-drag, and secondary-click context-menu controllers, so
hover UI cannot consume or alter drag and right-click input.

## Context menu

The right-click menu is called the **context menu**.

Current/expected actions may include:

- Walk
- Sleep / Wake
- Emote
- Computer
- size/position reset or other utility actions
- Quit

Important lifecycle rule:

The menu must finish closing and release GTK input/focus grabs **before** behavior that moves the window begins.

Safe sequence:

```text
action selected
→ context state cleared
→ popdown requested
→ wait for GTK closed signal
→ defer one main-loop turn
→ dispatch behavior
```

This prevents invisible popovers from intercepting later clicks, right-clicks, or drags.

## Walk

Walking should visually match physical movement.

Requirements:

- animation or bounce only while moving
- movement and animation remain synchronized
- stop safely before returning to idle
- context-menu initiated walk must not retain a popover grab
- later drag/right-click input still works

## Sleep / wake

Sleep is a transition, not an endlessly looping fall-asleep sequence.

Expected behavior:

```text
IDLE
→ sleep transition
→ sleeping hold/loop
→ WAKE
→ IDLE
```

Requirements:

- sleep transition plays once
- sleeping state persists intentionally
- wake plays once
- wake returns to idle
- input can wake Mochi through a defined path
- sleep/wake cannot permanently block click/right-click/drag

## Emote

The context-menu `Emote` action should select from existing compatible reaction animations.

Rules:

- start only when allowed by state priority
- do not interrupt non-interruptible transitions
- play once
- return cleanly
- reuse existing assets and state machinery

## Priority rules

General priority from highest to lowest:

1. direct user interaction
2. pickup/drop and wake/sleep transitions
3. deliberate movement
4. explicit one-shot emotes
5. ambient idle behavior
6. idle

The exact implementation can evolve, but timers must never independently fight for control of the animation state.

## Interaction completion criteria

A new interaction is only considered complete when:

- expected animation plays
- visual state and behavioral state agree
- interruption paths are defined
- no input surface remains mapped invisibly
- no duplicate timer is left running
- next click/right-click/drag works
- relevant unit/regression tests exist
- full suite passes
- live GTK/XWayland interaction is verified

That final recovery requirement is part of the feature, not optional polish.
