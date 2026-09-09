# Project Philosophy

> **Mochi is one continuous little creature living on the user's desktop. Protect that illusion.**

This page is the decision framework for Mochi's design and development.

It is not a substitute for explicit issue requirements or safety/security constraints. It is the default lens to use when multiple implementations could satisfy the same goal.

## 1. Mochi is a companion, not a dashboard

Mochi should feel like a small creature sharing the desktop.

Avoid turning the character into:

- a system-monitor panel
- a productivity dashboard
- a chatbot window
- a notification center
- a dense settings surface

UI should remain secondary to the creature.

## 2. Personality before feature count

A small number of behaviors that feel coherent is better than many shallow systems.

For the current phase, prioritize:

- idle presence
- tactile clicks
- expressive reactions
- pickup/drag/drop
- sleep/wake
- walking
- a few memorable emotes

Do not use feature count as a proxy for progress.

## 3. Physical continuity matters

Mochi should appear to have weight, softness, and continuity.

Transitions should make visual sense:

```text
idle → pickup → held → put-down → idle
```

Avoid sudden pose teleportation when an authored transition can preserve continuity.

## 4. Animation continuity matters

Animations should not visibly fight each other.

Use one authoritative state/animation path.

Prefer:

```text
current state
→ finish or safe interrupt point
→ requested state
```

rather than several timers independently swapping sprites.

## 5. Every temporary state must recover

No temporary state may become a dead end.

Examples:

- blink must return to idle
- heart must return to idle
- typing must return to idle
- pickup must reach held or recover through release
- put-down must return to idle
- wake must return to idle

Users will interact at inconvenient times. Recovery is part of the feature.

## 6. Direct interaction outranks ambient behavior

Mochi can perform quiet autonomous actions, but user intent wins.

A click, drag, or deliberate menu action should not lose to:

- blink timer
- typing timer
- random emote timer
- wandering timer

Ambient behavior should be cancellable or defer gracefully.

## 7. Protect canonical art

Canonical artwork is a project asset, not a disposable implementation detail.

Do not:

- overwrite the entire asset tree to integrate one animation
- reintroduce legacy art as an accidental fallback
- regenerate unrelated sprites to fix code
- smooth pixel art with bilinear scaling

When art must change, change the smallest relevant asset set and validate it visually.

## 8. Preserve pixel-art rules

Mochi's rendering style depends on:

- fixed logical canvas
- bottom-center anchoring
- transparent backgrounds
- nearest-neighbor rendering
- intentional pixel clusters

These are part of the design system.

## 9. Reliability beats cleverness

Choose the simplest implementation that preserves the desired behavior.

Prefer:

- one owned timer over several clever timers
- one explicit state transition over implicit visual swaps
- a small regression test over speculative refactoring
- deterministic pixel cleanup over regenerating an entire strip

Novel architecture is not automatically better architecture.

## 10. Do not redesign unrelated systems

When fixing one issue, preserve unrelated working behavior.

A request to fix pickup should not silently redesign:

- context menu
- packaging
- sleep
- asset folder structure
- UI overlay

Large cross-cutting changes require explicit intent and checkpointing.

## 11. Keep development tools separate from product behavior

Dev menus, previews, automation, and debugging are useful.

They must not become normal-runtime requirements.

Mochi should not need:

- remote desktop permission
- screen recording
- synthetic input permission
- development-only automation services

for ordinary use.

## 12. Respect Wayland constraints

Wayland's security model limits arbitrary window/input control.

Do not work around platform restrictions by silently adding broad permissions.

Prefer graceful platform-specific behavior and clear limitations.

## 13. Keep the runtime small

Mochi should remain lightweight.

Before adding a dependency, ask:

- Is it needed at runtime?
- Can existing GTK/Python/Cairo code do this clearly?
- Does the dependency materially improve reliability or capability?
- Does it complicate packaging?

Avoid adding a framework to solve a small problem.

## 14. Do not annoy the user

Mochi should be pleasant to leave running.

Ambient behavior should be:

- infrequent
- quiet
- interruptible
- visually gentle
- not constantly demanding attention

Sound, when added, should be subtle and optional.

## 15. UI is supportive, not dominant

Context menus, nametags, and status elements should help the user without turning Mochi into an app dashboard.

Prefer contextual UI that appears when useful and disappears cleanly.

## 16. Test the creature, not only the code

A passing test suite cannot tell whether:

- the loop visibly jumps
- a checkerboard is baked into the sprite
- the eyes look wrong
- drag feels too floaty
- pickup visually pops

Runtime behavior needs both automated tests and visual interaction testing.

## 17. Public alpha should stay focused

The alpha is about proving the companion core.

Do not prematurely add:

- hunger
- feeding
- health
- XP
- shops
- inventory
- AI/chat
- large progression systems

unless the project scope is intentionally changed.

## 18. Preserve recoverability during development

Before broad migrations or risky refactors:

- checkpoint
- create a backup branch if necessary
- preserve working assets
- record known-good test state

Temporary `/tmp` build artifacts are not durable backups.

## Authority order

When guidance conflicts, use this order:

1. explicit user/project requirement
2. safety, security, and data integrity
3. this project philosophy
4. implementation convenience/defaults

The philosophy should guide implementation choices, not override a deliberate requirement.

## Decision test

When two implementations both work, ask:

> **Which option makes Mochi feel more alive while keeping the application simpler, safer, and more reliable?**

That is usually the right choice.
