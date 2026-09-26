# Mochi Lab Appearance System — Design

**Date:** 2026-09-26

**Target:** post-v0.3 / v0.4 supporting work

**Status:** approved conversational design, implementation not started

## Purpose

Turn Mochi Lab into a user-facing appearance creator where people can make their own Mochi by selecting premade body variants and mix-and-match pixel-art accessories while preserving Mochi's authored animation quality.

The system must let accessories remain equipped through normal movement, sleep, dragging, and emotes whenever reasonably possible without requiring every accessory to be redrawn for every animation frame.

The feature is an appearance system, not an unrestricted image editor. Mochi's silhouette, animation language, pixel-art rules, and authored visual identity remain intentional.

## Product principles

1. **Mochi stays Mochi.** Customization decorates or varies the character; it should not erase the recognizable Mochi silhouette and expressive face.
2. **Real pixel art only.** Production assets use crisp authored pixel sprites, hard alpha edges, and nearest-neighbor scaling. Runtime transforms must not blur or stretch accessories.
3. **Accessories stay equipped whenever possible.** Hiding an equipped item is a fallback for genuinely incompatible animations, not the normal behavior.
4. **Simple assets should remain simple.** A basic accessory must be valid with one default sprite. Animation-specific overrides are optional polish.
5. **Rendering must be deterministic.** Slots, anchors, draw order, override resolution, and fallback behavior are data-driven rather than guessed at runtime.
6. **Appearance must never brick Mochi.** Invalid manifests, missing files, missing overrides, or stale saved loadouts must degrade safely to fewer accessories or plain Mochi.
7. **The system should be portable.** Appearance composition should not be coupled to GTK so the same model can later feed Linux and macOS renderers.
8. **Do not solve effects in v1.** Time-based effects are a separate subsystem and should not block appearance customization.
9. **Community extensibility comes after the built-in path works.** First prove the engine with first-party assets; pack discovery is later work.

## Scope

### In scope for the first complete Mochi Lab appearance system

- base Mochi variants;
- wearable/accessory slots;
- deterministic layer composition;
- per-frame attachment points;
- optional animation overrides;
- per-animation hide rules;
- persisted appearance loadouts;
- live user-facing Mochi Lab preview;
- developer attachment authoring;
- developer stress-test preview;
- validation of accessory manifests and images;
- graceful handling of missing or invalid assets.

### Out of scope for v1

- particle systems;
- autonomous visual effects;
- arbitrary user image uploads;
- freeform scaling/rotation of accessories;
- user-painted sprites inside Mochi Lab;
- online marketplace/discovery;
- remote asset downloading;
- community pack installation UI;
- monetized cosmetic inventory;
- network accounts or cloud sync.

## Existing asset/runtime constraints

Mochi's current animation manifest already establishes useful invariants:

- logical animation cell: **256 × 256**;
- anchor: **bottom-center**;
- scaling: **nearest-neighbor**;
- some source animations originate at 64×64 or 128×128 and are normalized by the existing sprite pipeline.

The appearance system must build on these rules instead of replacing them.

Accessories therefore have their own authoring canvas and anchor metadata, but are resolved into Mochi's existing logical 256×256 composition space at render time.

## Architecture overview

The appearance system is a separate domain under:

```text
src/mochi/appearance/
    models.py
    catalogue.py
    loadout.py
    attachments.py
    compositor.py
    validation.py
```

Responsibilities:

```text
models.py
    typed accessory/base/loadout definitions

catalogue.py
    discover built-in appearance assets and definitions

loadout.py
    equip/unequip, slot replacement, persistence-facing normalization

attachments.py
    resolve current animation/frame attachment coordinates

compositor.py
    resolve assets, overrides, positions, and deterministic layer order

validation.py
    validate manifests, paths, anchors, image constraints, and compatibility
```

The existing buddy renderer asks the appearance system for render layers. It does not own wardrobe rules.

Conceptually:

```text
behavior/state
     ↓
current animation + frame
     ↓
AppearanceCompositor
     ├── base sprite
     ├── AttachmentMap
     ├── AppearanceLoadout
     └── AccessoryCatalogue
     ↓
ordered RenderLayer[]
     ↓
platform renderer
```

This boundary is intentionally platform-neutral.

## Appearance model

### Base variant

A base variant describes which Mochi body/animation set is active.

Example:

```json
{
  "id": "classic",
  "display_name": "Classic Mochi",
  "animation_manifest": "assets/mochi/classic/manifest.json",
  "attachments": "assets/mochi/classic/attachments.json",
  "preview": "assets/mochi/classic/preview.png"
}
```

The initial implementation may treat today's Mochi asset set as the implicit `classic` variant before alternate bodies ship.

Each future base variant owns its own attachment map because different silhouettes may place head, face, neck, and hand points differently.

### Accessory

An accessory is a reusable appearance item.

Required conceptual fields:

```json
{
  "id": "green_beanie",
  "display_name": "Green Beanie",
  "slot": "head",
  "layer": "head",
  "source_cell_size": [64, 64],
  "anchor": [32, 16],
  "offset": [0, 0],
  "assets": {
    "default": "default.png"
  },
  "hide_during": []
}
```

`anchor` and `offset` are authored in the accessory's source-grid coordinates. The accessory loader normalizes both the image and these coordinates into Mochi's 256×256 runtime space before composition.

Optional fields may include:

- animation overrides;
- frame-specific overrides in a future format revision;
- tags;
- author/pack metadata;
- preview asset;
- compatibility metadata.

### Appearance loadout

The user's chosen appearance is stored as a small declarative loadout rather than a baked sprite sheet.

Example:

```json
{
  "base": "classic",
  "equipped": {
    "head": "green_beanie",
    "face": "round_glasses",
    "neck": "pink_scarf",
    "held": null
  }
}
```

Unknown or unavailable IDs are ignored during normalization.

## Initial slot system

The first public slot set is intentionally small:

```text
base
head
face
neck
back
held
```

Only one accessory may occupy a slot at a time.

Selecting a new accessory for an occupied slot replaces the prior item.

Sub-slots such as `headwear` + `head_detail` are intentionally deferred until real user demand proves they are necessary.

## Draw order

Layering is deterministic.

Initial order:

```text
1. back
2. base/body
3. neck
4. held-behind   (reserved, not required in first milestone)
5. face
6. head
7. held-front
8. foreground effect layer (reserved for future effect work)
```

The initial held slot may map to a single front layer until an actual asset requires behind/front separation.

## Attachment-point model

Accessories follow Mochi through animation by attaching to authored points on each animation frame.

Initial named attachment points:

```text
head
face
neck
back
held
```

Hand-specific points such as `left_hand` and `right_hand` may be added when held-item art proves that distinction necessary.

Attachment data should live separately from the current animation manifest in:

```text
assets/mochi/<variant>/attachments.json
```

For the initial classic variant, the existing asset root may be used while preserving this logical separation.

Conceptual format:

```json
{
  "format": "mochi-attachments-v1",
  "animations": {
    "idle": [
      {
        "head": [128, 54],
        "face": [128, 102],
        "neck": [128, 142],
        "back": [92, 126],
        "held": [164, 138]
      }
    ]
  }
}
```

The array length for an animation must match its effective frame count.

Attachment coordinates are expressed in Mochi's normalized **256×256 logical frame space**, regardless of the original source cell size of that animation.

## Accessory normalization and anchor placement

A 64×64 accessory canvas represents the same full logical frame as Mochi's 256×256 runtime cell. It is **not** a tight-cropped image that is drawn at 1:1 runtime pixels.

The accessory loader mirrors the existing animation loader:

```text
64×64 source image
→ nearest-neighbor ×4
→ 256×256 runtime surface
```

Source-grid anchor and offset coordinates are normalized by the same scale factor.

For example, if a beanie manifest defines:

```text
source anchor: (32, 16)
source offset: (0, 0)
```

the compositor receives:

```text
runtime anchor: (128, 64)
runtime offset: (0, 0)
```

If Mochi's current normalized `head` point is:

```text
(128, 54)
```

the accessory layer origin is:

```text
x = 128 - 128 + 0 = 0
y = 54  - 64  + 0 = -10
```

The full normalized accessory layer is then clipped/composited into the same 256×256 frame space as the base sprite.

This allows an accessory to be authored on a coarse, real pixel-art grid while still following small per-frame attachment-point changes after normalization.

The normalization and placement calculations are pure and independently testable.

No runtime auto-fit, arbitrary scaling, or rotation is performed to make an accessory fit a pose.

## Animation override resolution

Accessories should remain visible by default.

Resolution priority:

```text
future frame-specific override
        ↓
animation override
        ↓
default asset
        ↓
hide only when the accessory explicitly declares the animation incompatible
```

A v1 accessory may therefore define:

```json
{
  "assets": {
    "default": "default.png",
    "sleeping": "sleeping.png",
    "dragged": "dragged.png"
  },
  "hide_during": ["table_flip"]
}
```

The default asset remains valid for all animations not listed in `hide_during`, even when no override exists.

### Policy

- **Default:** keep equipped.
- **Preferred:** use a hand-authored override for poses where the default clearly fails.
- **Last resort:** temporarily hide during a declared incompatible animation.

This directly implements the product requirement that the user's chosen identity should remain visible whenever reasonably possible.

## Pixel-art authoring standard

### Canonical accessory source canvas

The standard first-party accessory source canvas is **64×64** transparent PNG.

That 64×64 canvas represents the **entire Mochi frame**, not a tight crop around the hat/glasses/item. At load time it is normalized to a 256×256 runtime surface with nearest-neighbor scaling, matching the existing sprite-loader model.

```text
authoring grid: 64×64
runtime grid:   256×256
scale:          exactly 4×
```

Accessory anchors and offsets are stored in 64×64 source-grid coordinates and normalized by the same factor.

This preserves authentic coarse pixel geometry while giving the compositor one coordinate system for base frames, attachment points, and accessory layers.

Accessories that genuinely require a different source cell may be supported in a future manifest revision, but v1 keeps one canonical 64×64 source grid.

### Rendering rules

Production accessory assets must:

- use PNG transparency;
- preserve hard pixel edges;
- use nearest-neighbor scaling;
- avoid anti-aliased contour pixels;
- avoid runtime arbitrary rotation;
- avoid runtime non-integer squash/stretch;
- remain legible at Mochi's normal small desktop sizes.

### Recommended slot footprints

These are authoring guidance and validator warnings, not hard clipping regions.

#### Head

```text
canvas: 64×64
recommended art bounds:
x: 8–56
y: 4–48
```

#### Face

```text
x: 12–52
y: 16–44
```

#### Neck

```text
x: 10–54
y: 26–58
```

#### Back

```text
x: 4–48
y: 12–56
```

#### Held

```text
x: 8–56
y: 18–60
```

### Visual style guidance

Accessories should decorate Mochi rather than visually replace the character.

Guidelines:

- preserve a readable Mochi silhouette;
- avoid covering the entire face for ordinary items;
- prefer simple, chunky forms over dense detail;
- use consistent dark outlines when appropriate;
- use a restrained number of shades per material;
- prioritize silhouette and readability before internal detail;
- avoid smooth vector-like shapes that do not match the sprite language.

### Palette guidance

Mochi's body palette remains controlled by its base variant.

Accessories may use broader colors, but first-party items should normally stay compact, roughly **3–8 colors plus transparency**.

Color-count limits are a style warning, not a runtime validity requirement.

## Accessory asset structure

Each accessory owns one self-contained directory:

```text
assets/accessories/
    green_beanie/
        manifest.json
        default.png
        sleeping.png
        dragged.png
        preview.png
```

Example manifest:

```json
{
  "format": "mochi-accessory-v1",
  "id": "green_beanie",
  "display_name": "Green Beanie",
  "slot": "head",
  "layer": "head",
  "source_cell_size": [64, 64],
  "anchor": [32, 16],
  "offset": [0, 0],
  "assets": {
    "default": "default.png",
    "sleeping": "sleeping.png",
    "dragged": "dragged.png"
  },
  "hide_during": [],
  "tags": ["cozy", "winter", "hat"]
}
```

Manifest paths are relative to the accessory directory and must not escape it.

## Accessory behavior categories

These categories are authoring guidance rather than runtime subclasses.

### Static wearable

Examples:

- glasses;
- scarf;
- bow;
- beanie.

Usually valid with one default sprite plus optional difficult-pose overrides.

### Held/prop item

Examples:

- coffee;
- book;
- flower;
- tiny laptop.

More likely to need overrides because pose and body overlap can change substantially.

### Expressive/special wearable

Examples:

- wizard hat;
- oversized crown;
- frog hat;
- cape.

May require explicit overrides or hide rules during exaggerated emotes.

## Validation

### Hard manifest validation

Reject/skip an accessory when:

- format identifier is unsupported;
- ID is missing or invalid;
- slot is unsupported;
- layer is unsupported;
- anchor is missing or outside the source canvas;
- required default asset is missing;
- referenced override file is missing;
- asset path escapes the accessory directory;
- manifest JSON is malformed.

### Hard image validation

For built-in v1 assets:

- PNG;
- declared source cell size is 64×64 for v1;
- image dimensions match the declared 64×64 source cell;
- readable image data;
- transparent-capable image mode;
- no malformed file.

Whether to reject all partial-alpha pixels should be decided by the actual PNG tooling used during implementation. The required visual outcome is hard-edged pixel art; the validator may begin by warning on partial alpha rather than rejecting assets if strict rejection would produce false positives.

### Style warnings

Warnings may flag:

- unusually high color count;
- artwork outside recommended slot bounds;
- mostly empty canvas;
- suspicious partial-alpha edge pixels;
- unusually large visual footprint;
- missing overrides for known difficult animations.

Warnings do not prevent first-party development builds from loading the item.

## Persistence and recovery

Appearance is saved through the existing configuration system.

Conceptual persisted state:

```json
{
  "appearance": {
    "base": "classic",
    "equipped": {
      "head": "green_beanie",
      "face": "round_glasses",
      "neck": "pink_scarf"
    }
  }
}
```

On startup:

```text
load raw appearance
→ validate base ID
→ validate each accessory ID
→ discard unavailable/invalid entries
→ return normalized loadout
→ render
```

Failure behavior:

- missing accessory → omit that slot;
- invalid manifest → item never enters catalogue;
- missing override → default asset;
- missing default → skip accessory;
- corrupt appearance state → safe classic/plain loadout;
- missing alternate base → classic base.

Appearance failures must not abort Mochi startup.

## Mochi Lab user experience

Mochi Lab is launched from a user-facing customization action, expected initially from Mochi's context menu:

```text
Customize Mochi
```

The Lab is a character creator rather than a file browser.

Primary layout:

```text
┌────────────────────────────────────────────┐
│                  Mochi Lab                 │
├───────────────────────┬────────────────────┤
│                       │                    │
│      LIVE PREVIEW     │   Base             │
│                       │   ○ Classic        │
│         Mochi         │   ○ Spotted        │
│                       │                    │
│    animated preview   │   Head             │
│                       │   [sprout] [hat]   │
│                       │                    │
│                       │   Face             │
│                       │   [glasses] [none] │
│                       │                    │
│                       │   Neck             │
│                       │   [scarf] [none]   │
├───────────────────────┴────────────────────┤
│ Randomize        Reset          Save & Wear│
└────────────────────────────────────────────┘
```

### Preview behavior

The preview must animate rather than showing only a static idle image.

Initial preview controls:

```text
Idle
Walk
Sleep
Drag
Bounce
Random
```

Changing an appearance item updates the preview immediately.

**Save & Wear** persists the normalized loadout and applies it to the running desktop Mochi without requiring a restart.

### Randomize

Randomize chooses one valid item or no item for each supported slot and a valid base variant.

It is intentionally local and deterministic only to the extent necessary for valid combinations; no sharing code or seed format is required for v1.

## Developer attachment editor

Attachment coordinates should not be maintained primarily by hand-editing JSON.

A developer-facing authoring tool should allow:

```text
select base
→ select animation
→ select frame
→ select attachment point
→ click desired location
→ save integer coordinate
```

Useful authoring actions:

- previous/next frame;
- copy previous frame's point;
- apply one point to all frames;
- clear/reset a point;
- preview accessory at that point.

Interpolation is optional and should be added only if manual authoring proves painful enough to justify it.

## Developer accessory stress test

A developer-only viewer should cycle one accessory through every animation.

Example status concepts:

```text
✓ default asset used
✓ animation override used
⚠ hidden by compatibility rule
⚠ validation warning
```

The tool is both QA and an artist workflow.

It should make it easy to answer:

- does the default asset remain aligned?
- which animations need overrides?
- does any pose require hiding?
- does scaling remain crisp?
- does the accessory clip or obscure important expression?

Automated image analysis is not required for v1; visual inspection plus manifest/geometry validation is sufficient.

## Rendering integration

The existing Buddy drawing path should remain responsible for platform drawing while appearance composition determines what to draw.

Conceptual integration:

```python
layers = appearance_compositor.layers_for(
    animation=current_animation,
    frame_index=current_frame_index,
    loadout=current_loadout,
)

for layer in layers:
    draw_layer(layer)
```

The compositor returns pure render metadata such as:

- image/sprite reference;
- logical x/y;
- layer order;
- visibility.

It must not know about GTK gestures, menus, behavior transitions, X11 movement, or Wayland layer shell.

## Base variants

Alternate bodies are intentionally added after the accessory engine works against classic Mochi.

Each base variant supplies:

- animation set;
- attachment map;
- preview metadata;
- stable variant ID.

The accessory manifest format remains unchanged across variants.

The compatibility contract is therefore:

```text
Accessory.slot
        +
BaseVariant attachment point with same name
        =
portable placement
```

If a base variant does not expose a required attachment point, the relevant accessory is omitted for that frame/animation rather than crashing.

## Community asset packs

Community packs are a later phase after first-party catalogue behavior is stable.

Conceptual structure:

```text
cozy-pack/
    pack.json
    green_beanie/
        manifest.json
        default.png
    scarf/
        manifest.json
        default.png
```

Conceptual pack metadata:

```json
{
  "format": "mochi-accessory-pack-v1",
  "id": "cozy-pack",
  "name": "Cozy Pack",
  "author": "Mika",
  "version": "1.0.0"
}
```

Later local discovery may scan an application data directory such as:

```text
~/.local/share/mochi/accessories/
```

Exact community installation UX, trust model, moderation, and remote distribution are separate future designs.

## Effects are a separate subsystem

Effects such as:

- sparkles;
- hearts;
- sleep Zs;
- music notes;
- rain clouds;
- glow/aura;

are time-based visual behaviors rather than persistent wearables.

They may require:

- spawn/despawn lifecycle;
- independent animation;
- duration;
- looping;
- state triggers;
- independent motion.

Therefore v1 Mochi Lab does **not** model effects as ordinary accessories.

A future effects subsystem may reuse attachment points and render-layer infrastructure, but it should have its own controller/model.

## First-party launch catalogue

The first public catalogue should remain intentionally small.

### Initial base

- Classic Mochi.

Alternate base variants follow after the engine proves stable.

### Head candidates

- Sprout;
- beanie;
- bow;
- frog hat;
- flower clip.

### Face candidates

- round glasses;
- square glasses;
- star glasses;
- heart glasses.

### Neck candidates

- scarf;
- bow collar.

### Held candidates

- coffee;
- book;
- tiny laptop;
- flower.

The first engineering milestone does not require the whole launch catalogue.

## Initial proof milestone

**Mochi Lab Milestone 0:**

Classic Mochi can wear:

- round glasses;
- green beanie;
- scarf;

through:

- idle;
- blink;
- walk;
- sleeping;
- dragged;

without losing crisp pixel alignment, breaking normal animation, or requiring the accessory to disappear.

This milestone proves the attachment/composition model before the public Lab UI is built.

## Implementation phases

### Phase 1 — Developer-only appearance engine

Build:

- data models;
- catalogue;
- loadout;
- attachment map reader;
- compositor;
- basic validation.

Use three first-party test accessories.

No public Mochi Lab window yet.

### Phase 2 — Attachment authoring tool

Build the frame/point editor needed to create and maintain attachment maps efficiently.

### Phase 3 — Accessory stress-test viewer

Provide full animation cycling and clear indication of default, override, hidden, and warning states.

### Phase 4 — Persistence and live switching

Save loadouts through ConfigStore and apply changes to the running Mochi without restart.

### Phase 5 — Public Mochi Lab

Add the user-facing customization window, live preview, Randomize, Reset, and Save & Wear.

### Phase 6 — Alternate base variants

Introduce additional Mochi bodies using the same accessory contract.

### Phase 7 — Community packs

Add local third-party pack discovery only after the first-party format and validation behavior are stable.

### Phase 8 — Effects

Design effects independently after appearance customization is proven.

## Testing strategy

### Pure unit tests

Test without GTK:

- valid manifest parsing;
- malformed manifest rejection;
- invalid slot rejection;
- path traversal rejection;
- missing default asset handling;
- override resolution;
- hide-rule resolution;
- one-item-per-slot replacement;
- unknown saved IDs dropped safely;
- loadout normalization;
- deterministic layer order;
- anchor coordinate calculation;
- base-variant fallback;
- missing attachment-point fallback.

Example geometry test:

```text
Source cell:             64×64
Runtime cell:            256×256
Source accessory anchor: (32, 16)
Normalized anchor:       (128, 64)
Mochi attachment point:  (128, 54)
Normalized offset:       (0, 0)

Expected layer origin:   (0, -10)
```

### Asset validation tests

Built-in accessory assets should be checked in CI for:

- valid manifests;
- expected dimensions;
- referenced files present;
- valid anchors;
- no duplicate accessory IDs.

### Integration tests

With the real sprite pipeline:

- current animation/frame resolves correct attachment record;
- base plus accessory layers resolve in stable order;
- alternate source-cell-size animations still use normalized 256×256 attachment coordinates;
- appearance persistence round-trips through ConfigStore.

### Live visual QA

Manual regression coverage should include:

- nearest-neighbor crispness at supported Mochi sizes;
- idle;
- walking both directions where relevant;
- drag/pickup/drop;
- sleep/wake;
- bounce/squish;
- context-menu interactions;
- complex catalogue emotes;
- accessory changes while Mochi is already running.

## Error and logging policy

Appearance errors are non-fatal.

User-facing behavior defaults to graceful fallback rather than modal errors.

Developer logs should identify:

- accessory ID;
- manifest path;
- invalid field/path;
- requested animation/frame;
- fallback selected.

The plain/classic Mochi render path remains the final safe fallback.

## Generated art workflow

Generated imagery may accelerate exploration and first-pass sprite candidates, but generated output is not automatically production-ready.

Recommended workflow:

```text
generate candidate
→ inspect visually
→ refine in Pixelorama or equivalent pixel editor
→ normalize palette/edges
→ add manifest and anchor
→ run validator
→ run animation stress test
→ approve into first-party catalogue
```

This preserves authored pixel-art quality while making asset creation faster.

## Success criteria

The appearance system is ready for the first public Mochi Lab when:

1. classic Mochi can wear multiple first-party accessories through common animations;
2. accessories remain equipped by default and only hide through explicit rules;
3. all built-in accessory definitions pass validation;
4. appearance persists across restart;
5. changing appearance does not require restarting Mochi;
6. invalid/missing assets cannot prevent Mochi from launching;
7. live preview accurately reflects the desktop render behavior;
8. attachment points can be maintained without hand-editing large JSON files;
9. appearance composition remains independent of GTK-specific behavior;
10. the first public UI feels like a character creator rather than an asset browser.

## Main architectural decision

Mochi Lab uses **manifest-driven layered composition with authored per-frame attachment points and optional animation overrides**.

It does not pre-bake every outfit combination, and it does not rely on crude fixed-position overlays.

That gives Mochi a scalable customization system while preserving the hand-authored pixel-art character of the project.
