# Animation and Art Pipeline

Mochi's visual identity depends on consistent pixel-art handling from source generation through runtime rendering.

## Canonical presentation

Runtime expectations:

- fixed **128×128 logical frame**
- transparent RGBA artwork
- bottom-center anchoring
- nearest-neighbor scaling only
- integer scaling where practical
- no dynamic cropping per frame
- no bilinear filtering
- no new texture/surface allocation every animation tick

These rules reduce visual jitter and preserve intentional pixel clusters.

## Source tools

### Pixelorama

Primary manual pixel-art editor.

Use it for:

- cleanup
- pixel-by-pixel corrections
- palette control
- frame timing experiments
- manual emote edits
- checking loop continuity

### PixelLab / PixelEngine

Used for AI-assisted sprite and animation generation.

Generated output is a draft, not automatically production-ready. Every generated strip must be audited for:

- dimensions
- alpha transparency
- checkerboard/matte contamination
- outline consistency
- canonical eyes/highlights
- silhouette consistency
- bottom alignment
- loop seams

### Figma

Used for UI/UX work such as nametags, overlays, status presentation, spacing, and handoff specs.

Figma should not become a runtime dependency.

### ImageMagick

Useful for deterministic production transforms:

- nearest-neighbor resize
- strip splitting/joining
- alpha cleanup
- canvas normalization
- endpoint substitution
- sprite-sheet inspection

Automated transforms should be narrow and auditable. Avoid broad color or alpha operations that can erase legitimate outline/detail pixels.

## Palette and visual identity

Mochi is a soft green sprout/blob character with a simple, squat silhouette.

Canonical art should preserve:

- recognizable rounded body
- small limbs
- sprout placement
- dark outline
- simple face
- eye highlights
- compact proportions
- clean pixel clusters

Do not replace canonical art simply because a code path is easier to test with another sprite set.

## Asset manifest

`assets/mochi/manifest.json` is the intended source of truth for runtime animation metadata.

Code should refer to animation names, while the manifest defines the associated asset paths and timing metadata.

Benefits:

- avoids hardcoded frame paths scattered through runtime code
- makes packaging auditable
- simplifies replacement of one animation without rewriting behavior logic
- allows tests to validate missing/unreferenced assets

## Frame and spritesheet formats

Mochi has used both individual 128×128 PNG frames and horizontal spritesheets.

For horizontal strips, the runtime should:

1. load the source image once
2. slice cells once
3. normalize each cell to the 128×128 logical canvas
4. cache the resulting surfaces
5. reuse them during playback

Some newer authored strips use **64×64 cells**, rendered at 2× nearest-neighbor into the 128×128 logical frame.

## Animation timing

Respect authored timing where possible.

Avoid treating all animations as a single global FPS. Different reactions need different rhythm:

- idle: slow and subtle
- click/squish: tactile and quick
- heart/emote: readable one-shot
- pickup/drop: elegant transition
- held sway: slower, suspended feel
- sleep/wake: deliberate transition

If a loop visibly restarts, fix timing/frame continuity rather than masking the seam with smoothing.

## Endpoint locking

Transitions around dragging should share exact visual endpoints.

For pickup:

```text
frame 0 = exact idle endpoint
...
final frame = exact held endpoint
```

For put-down:

```text
frame 0 = exact held endpoint
...
final frame = exact idle endpoint
```

This is preferred over approximate similarity because it eliminates visible popping at state boundaries.

## Transparency QA

Generated art has historically produced baked checkerboards and gray matte pixels.

For every new sprite or strip, verify:

- alpha channel contains real transparency
- corner/background pixels are alpha 0 where expected
- no low-saturation gray halo remains around the silhouette
- intentional dark outline remains intact
- white/off-white eye highlights are not accidentally removed

A source PNG with opaque matte pixels will look worse under nearest-neighbor scaling; the renderer does not create that artifact.

## Eye consistency

Mochi's eyes are a small but important identity cue.

When editing drag or transition art:

- preserve black/dark pupils
- preserve canonical off-white highlights
- avoid replacing eyes with solid black blocks
- check each frame, not only the first

## Anchor consistency

Every frame should be bottom-center anchored to the same logical canvas.

When trimming/resizing generated art:

1. trim only source whitespace if necessary
2. resize with nearest-neighbor
3. place the sprite on a transparent 64×64 or 128×128 canvas
4. align to bottom-center
5. confirm no feet/body pixels are clipped

Do not let per-frame bounding boxes determine runtime window placement.

## Asset migration rules

When introducing new art:

- copy only the named animation(s) being replaced
- do not copy an entire new asset set over `assets/mochi/`
- preserve old working states until their replacements exist and are validated
- update manifest references deliberately
- verify no runtime file is missing or orphaned
- inspect the packaged wheel, not just the working tree
- checkpoint before broad migrations

A previous whole-folder overwrite replaced canonical PixelLab idle/squish art and changed manifest frame counts. This is exactly the class of migration the project should avoid.

## Art acceptance checklist

Before integrating an animation:

- [ ] canonical Mochi silhouette preserved
- [ ] dimensions correct
- [ ] transparent RGBA background
- [ ] no checkerboard baked into pixels
- [ ] no gray matte/halo
- [ ] outline preserved
- [ ] eyes/highlights consistent
- [ ] bottom-center anchored
- [ ] nearest-neighbor compatible
- [ ] first/last transition endpoints correct
- [ ] loop seam acceptable if looping
- [ ] timing documented
- [ ] manifest updated
- [ ] package contains the intended asset
- [ ] live preview visually inspected

## Preview workflow

Use the animation preview command when available:

```bash
mochi --preview-animations
```

A good preview should make it easy to inspect:

- animation name
- current frame
- timing/FPS
- loop status
- transparency
- alignment
- transition endpoints

Visual inspection is required for art. Passing code tests alone cannot prove that the sprite looks correct.
