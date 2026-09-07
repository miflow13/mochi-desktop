# GTK Implementation Notes

## Architectural intent

The status overlay is presentation. It must observe Mochi's state rather than own
or mutate behavior.

Preferred conceptual flow:

```text
MochiState / presentation data
            ↓
MochiStatusOverlay
            ↓
GTK widgets / styling
```

Avoid:

```text
overlay
  ↓
behavior state machine
```

## Preferred structure

Use a dedicated component around the existing Buddy presentation, for example:

```text
Gtk.Overlay
├── Buddy / existing sprite widget
└── MochiStatusOverlay
```

Exact GTK composition should follow the existing project architecture rather than
forcing a new framework.

## Pointer/input behavior

The overlay must not interfere with:

- primary click reactions
- dragging
- right-click/context menu
- walking
- sleep/wake
- transition-priority rules

Prefer making presentation layers non-focusable and non-interactive unless a
future task explicitly adds interaction.

## Contextual visibility

The overlay should be contextual rather than permanently intrusive.

Recommended first-pass policy:

- idle with no recent interaction → hidden
- click/reaction → show briefly
- drag → show while dragging
- important state change → show briefly
- future health/status change → show briefly
- sleep may use the Sleeping variant
- optional hover behavior only if it is reliable and does not complicate input

After a short delay, hide the overlay.

A subtle fade is welcome only if it can be implemented without creating a second
animation/timer subsystem that fights Mochi's state timers.

## Health/status value

For v0.2, implement only a presentation API.

Recommended contract:

```python
set_status_value(value: float)  # normalized 0.0 ... 1.0
```

Clamp presentation values safely.

Do not add:

- persistent health
- feeding
- fullness simulation
- XP
- levels/progression logic

A temporary demonstration value is acceptable if clearly marked as presentation
data.

## State labels

If state text is used, map internal states to user-facing labels in a testable
non-GTK function.

Examples:

```text
SLEEPING   → Sleeping
WAKING     → Waking up
WALKING    → Walking
BOUNCING   → Happy
SQUISHING  → Happy
DRAGGED    → (optional / no text)
```

Do not expose raw enum strings in the UI.

## Important layout warning

Showing/hiding the overlay must not change the character's desktop anchor or make
the window jump.

The overlay should remain visually attached while Mochi moves and while display
scale changes.
