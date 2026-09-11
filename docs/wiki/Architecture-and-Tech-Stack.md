# Architecture and Tech Stack

This page describes Mochi's runtime architecture and the boundaries that should remain stable as the project grows.

## Runtime stack

Mochi is a Linux desktop application built with:

- **Python 3.11+**
- **GTK4**
- **PyGObject** for GTK/GNOME bindings
- **Cairo** for sprite drawing/compositing
- **Fedora + GNOME** as the primary development target
- **Wayland-first** behavior, with **XWayland** used where GNOME's native Wayland restrictions require it

The application is intentionally small and does not use Electron, React, Qt, Unity, Godot, or a web backend.

## Architectural goals

The runtime should remain:

- easy to reason about
- event-driven rather than polling-heavy
- lightweight enough to leave running
- explicit about behavior state
- resilient to interrupted animations and unexpected input order
- visually deterministic
- free of unnecessary platform permissions

Mochi should never require remote-desktop, screen-sharing, screen-recording, or synthetic-input privileges during normal use. Development automation may use separate test tooling, but those permissions are not runtime dependencies.

## Key modules

The repository README currently identifies these primary runtime modules:

### `app.py`

GTK application and window setup.

Responsibilities should include:

- creating the application
- creating/presenting the Mochi window
- command-line launch integration
- application lifecycle

It should not become the main behavior engine.

### `buddy.py`

The high-level interaction coordinator.

Typical responsibilities:

- mouse input
- click/double-click arbitration
- drag lifecycle
- movement
- idle timers
- context-menu actions
- handing animation completion back to the state system

Because this module touches many systems, changes here deserve focused regression testing.

### `state.py`

Named behavioral states and state transitions.

The state machine is a core reliability boundary. Visual playback and behavioral state must agree; an animation that *looks* idle while the state remains `BLINKING`, `TYPING`, or another temporary state can make later input appear frozen.

### `animation.py`

Time-based animation playback.

Responsibilities:

- current frame tracking
- per-frame durations
- looping vs one-shot behavior
- animation completion
- safe interruption points where applicable

### `sprite_loader.py`

Loads and validates animation assets from the manifest.

The loader should:

1. read `assets/mochi/manifest.json`
2. resolve frame or spritesheet metadata
3. validate expected assets
4. load/slice images once
5. cache runtime surfaces

Runtime code should request animation names, not assemble PNG paths in behavior code.

### `sprites.py`

Runtime sprite definitions and cached surfaces.

This layer translates manifest data into rendering-ready animation definitions while preserving:

- fixed canvas geometry
- bottom-center anchoring
- nearest-neighbor scaling
- authored frame timing

### `behavior.py`

Behavior selection and higher-level reaction choices.

Ambient behavior should stay subordinate to direct interaction. It should not own duplicate timers or create a second animation controller.

### `config.py`

Persistent user configuration.

Keep persistence separate from animation and input state so a config failure cannot easily lock the creature state machine.

## Rendering model

Mochi is pixel art. The rendering rules are intentional architecture, not just aesthetics.

### Fixed logical canvas

Runtime artwork uses a **256×256 asset frame** and scales to the configured
window size (128 px by default).

Fixed frame dimensions prevent visual jitter when Mochi changes silhouette between breathing, squishing, dragging, or other reactions.

### Anchoring

Frames are **bottom-center anchored**.

This makes the character's apparent contact point with the desktop remain stable even when the upper silhouette changes.

### Scaling

Use **nearest-neighbor interpolation only**.

Do not use bilinear filtering for sprite art. Prefer integer scale factors.

### Caching

Decode and prepare textures/surfaces once. Do not create new textures every animation tick.

## Animation/state ownership

There should be one authoritative interaction/state path.

Avoid:

- a second animation controller for one new feature
- separate unmanaged GLib timers for each emote
- visual state changes that bypass behavioral state
- input handlers that directly swap sprites without a defined state transition

The desired priority model is generally:

1. direct user interaction
2. pickup/drop and sleep/wake transitions
3. deliberate movement such as walking
4. one-shot idle reactions
5. ambient idle behavior

## Context menu lifecycle

The right-click menu is referred to as the **context menu**.

GTK popover teardown matters because `popdown()` is asynchronous. A behavior that moves the parent window before the popover has emitted `closed` can leave a stale input grab.

The safe sequence is:

```text
select action
→ clear context state
→ request popdown
→ wait for closed
→ defer one main-loop turn
→ begin behavior
```

Any future context-menu implementation should preserve that sequencing.

## Drag architecture

Dragging has two separate concepts:

1. **actual window/drop position**
2. **visual character inertia**

Visual inertia may make Mochi trail the cursor slightly, but it must not change the final release coordinates or make dragging difficult to control.

Keep motion feel separate from correctness of window positioning.

## Packaging

Mochi uses `pyproject.toml` with setuptools.

The package exposes:

```text
mochi = mochi.main:main
```

Runtime data files include the Mochi asset manifest, sprite art, and audio assets.

Before release, audit the built wheel rather than assuming working-tree assets were packaged correctly.

## Architecture rules of thumb

When deciding where new code belongs:

- **asset discovery/loading** → loader layer
- **frame timing/playback** → animation layer
- **behavior state** → state layer
- **reaction choice** → behavior layer
- **mouse/timer/window coordination** → buddy layer
- **GTK application/window creation** → app layer
- **persistent settings** → config layer

If a feature seems to require duplicating several of these responsibilities, reconsider the design before adding it.
