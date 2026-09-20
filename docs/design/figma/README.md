> **Historical scoped handoff:** This document describes a v0.2-era presentation task. Its "do not implement feeding/XP/progression" restrictions applied to that task only. v0.3 now intentionally ships non-punitive bond progression, feeding, level-up feedback, emote unlocks, and Focus with Mochi. Use the current README, roadmap, and project philosophy for present-day product scope.

# Mochi Figma → Copilot Handoff

This folder is a design handoff for the **Mochi v0.2-dev** nametag + contextual
status overlay task.

## Source of truth

Use the files in `reference/exports/` as the visual source of truth.
The files in `reference/inspection/` document measurements read directly from Figma.

Start with:

1. `COPILOT_HANDOFF.md`
2. `design-spec.md`
3. `implementation-notes.md`

## Scope

This handoff covers presentation only:

- Mochi name
- compact/contextual status UI
- health/status bar presentation
- overlay positioning and visibility

It does **not** authorize implementation of feeding, persistent health, XP,
leveling, or other v0.3 progression systems.
