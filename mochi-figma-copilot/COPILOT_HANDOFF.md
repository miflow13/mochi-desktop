# Copilot Task — Mochi Nametag + Contextual Status Overlay

Continue development of **Mochi v0.2-dev — Make Mochi Feel Alive**.

## First: inspect the handoff

Before editing code, read:

- `design-spec.md`
- `implementation-notes.md`
- all relevant PNGs under `reference/exports/`

Treat the exported Figma files as the **visual source of truth**.

Also inspect the existing Mochi repository architecture before implementing.
Preserve the animation transition-policy work already completed.

## Task

Implement:

**Nametag + contextual status overlay — Mochi name + small health/status bar**

The overlay should reproduce the supplied Figma design as closely as practical
within GTK.

## Product goal

The UI should make Mochi feel like a living desktop companion without creating a
permanent HUD.

It should support:

- name: `Mochi`
- compact visual health/status bar
- optional contextual state/status presentation
- contextual show/hide behavior

## Figma requirements

Known measured design values are in `design-spec.md`.

Key values include:

- full wrapper: 220 × 72 px
- panel: 220 × 64 px
- panel padding: 12 px horizontal / 8 px vertical
- panel gap: 4 px
- panel radius: 14 px
- panel fill: #FFF8F0
- panel stroke: #3D2B3A at 2 px
- name font: Rubik ExtraBold, 14 px
- name color: #4D384A
- compact variant: 180 × 44 px
- minimal variant: 144 × ~52.36 px
- standalone status modules: 80 × 48 px

Do not invent undocumented visual details when the exported references can answer
the question.

## Contextual behavior

Prefer the overlay to be hidden during ordinary idle desktop use.

Show it contextually, for example:

- after click/pet interaction
- while dragging
- after meaningful state changes
- for sleeping/waking states where appropriate
- when status/health changes in the future

Then hide it again after a short delay.

A small fade is acceptable if it does not create timer/state conflicts.

## Architecture constraints

- Prefer `Gtk.Overlay` or the closest structure that fits the existing GTK code.
- Create a dedicated presentation component such as `MochiStatusOverlay`.
- Do not draw the entire overlay directly in `Buddy._draw()`.
- The overlay observes existing behavior; it does not own behavior.
- Do not create a parallel state machine.
- Do not disturb the transition-priority rules already implemented.
- Do not add unnecessary dependencies.
- Preserve Wayland and X11 behavior.

## Input safety

The overlay must not steal focus or pointer behavior from Mochi.

Verify that it does not break:

- bounce/squish click reactions
- walking
- dragging
- right-click context menu
- sleep/wake
- animation completion / interruption rules

## Health bar scope

Implement the **visual presentation API only**.

Use a normalized value:

```text
0.0 → 1.0
```

Clamp values.

Do NOT implement:

- feeding
- persistent health
- fullness
- XP
- level progression
- vitals persistence

Those belong to a later phase.

## Friendly state presentation

If state text is shown, use a small testable mapping from `MochiState` to friendly
labels rather than displaying enum names directly.

## Tests

Add unit coverage for non-GTK logic where practical:

- state → friendly display label
- normalized bar clamping
- contextual visibility policy
- show/hide trigger decisions

Do not unnecessarily force GTK initialization into the standard-library tests.

Run:

```bash
python3 -m unittest discover -s tests -v
```

All existing tests must remain green.

## Acceptance criteria

1. `Mochi` is displayed according to the Figma visual hierarchy.
2. The status bar resembles the supplied Figma design.
3. The overlay is contextual rather than permanently intrusive.
4. It remains visually attached to Mochi while Mochi moves.
5. Showing/hiding does not move Mochi's desktop anchor.
6. It does not interfere with clicking, dragging, context menus, or animation states.
7. It uses presentation-only normalized status data.
8. No v0.3 care/progression mechanics are introduced.
9. Existing animation transition rules remain intact.
10. The full test suite passes.

## Before editing

Report:

1. current files/components you will reuse
2. exact files you expect to modify/add
3. proposed GTK composition
4. proposed contextual visibility policy
5. any expected Figma → GTK compromises

Then implement the smallest clean version.

## After implementation

Report:

- files changed
- design measurements followed
- Figma → GTK compromises
- visibility behavior
- future vitals integration seam
- tests added/changed
- full test results
- manual playtest checklist
