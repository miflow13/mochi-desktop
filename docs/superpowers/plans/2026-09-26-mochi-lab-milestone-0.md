# Mochi Lab Milestone 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove Mochi's appearance architecture by letting classic Mochi wear round glasses, a green beanie, and a scarf through idle, blink, walk, sleeping, and dragged animations with crisp, stable pixel alignment.

**Architecture:** Add a platform-neutral appearance domain that loads validated accessory manifests, resolves per-frame attachment points, normalizes a one-item-per-slot loadout, and produces ordered render-layer metadata. Keep Cairo drawing in the existing sprite renderer: `SpriteAtlas` normalizes 64×64 accessory PNGs to Mochi's 256×256 logical frame and composites those layers under the same transform as the active base frame. The developer-only milestone uses a hidden CLI preview flag; persistence, the public Mochi Lab window, alternate bodies, community packs, and effects remain later plans.

**Tech Stack:** Python 3.11+, dataclasses/pathlib/json/logging, Cairo, GTK4/PyGObject integration only at the existing renderer/application seam, pytest/unittest, existing setuptools data-file packaging.

**Spec:** `docs/superpowers/specs/2026-09-26-mochi-lab-appearance-system-design.md`

## Global Constraints

- Mochi's runtime animation cell remains **256 × 256**, bottom-center anchored, nearest-neighbor scaled.
- First-party v1 accessory source cells are **64 × 64** transparent PNGs representing the full Mochi frame, normalized exactly **4×** to 256×256 at render time.
- Accessory source-grid anchors and offsets are normalized by the same 4× scale factor before placement.
- Initial slots are `head`, `face`, `neck`, `back`, and `held`; only one item may occupy a slot.
- Initial draw order is back < base/body < neck < held-behind < face < head < held-front.
- Equipped accessories remain visible by default; an animation override wins over the default asset; hiding is allowed only through an explicit compatibility rule.
- Runtime code must not auto-rotate, blur, non-integer stretch, or otherwise distort accessory pixel art.
- Invalid manifests, stale IDs, missing assets, missing attachment points, or malformed appearance input must not prevent Mochi from launching.
- The appearance domain must not depend on GTK gestures, X11/Wayland movement, or behavior-state transitions.
- Effects, persistence, public Mochi Lab UI, alternate body variants, community pack discovery, remote assets, and arbitrary user uploads are out of scope for this milestone.
- Existing animation behavior, mood variants, drag motion, menus, Focus, AmbiSense, updater, and installed-build packaging must continue to work.

## Review Focus

- **A mood/derived animation renders a different asset name from Mochi's semantic state:** resolve attachment/override data from the actual player animation first and use the semantic animation only as a fallback; tests cover actual-vs-semantic name resolution.
- **A selected accessory ID is missing, malformed, corrupt on disk, or belongs to a different slot:** keep it out of the catalogue/loadout instead of raising; tests cover unknown IDs, invalid manifests, corrupt/wrong-size PNGs, and slot mismatch.
- **An attachment point is missing or the frame index is outside available metadata:** omit only that accessory layer and keep base Mochi visible; tests cover missing slot points and out-of-range frames.
- **A 64×64 accessory is composed at a negative logical origin or near frame edges:** preserve the signed origin and let Cairo clip naturally; tests cover the spec's `(0, -10)` placement example.
- **A source checkout works but an installed runtime cannot find appearance assets:** source-root and `sys.prefix/share/mochi` discovery plus setuptools data-file tests must prove both manifest/attachment and accessory PNG packaging paths.

---

## File map

### New appearance-domain files

- `src/mochi/appearance/__init__.py` — package exports only.
- `src/mochi/appearance/models.py` — slots/layers, accessory/loadout/render-layer data types, layer-order constants.
- `src/mochi/appearance/validation.py` — strict manifest/path/source-cell validation and typed parse errors.
- `src/mochi/appearance/catalogue.py` — source/install root discovery, valid accessory discovery, lookup by ID.
- `src/mochi/appearance/attachments.py` — classic attachment-map loading and actual/semantic animation fallback.
- `src/mochi/appearance/loadout.py` — empty/default loadout and normalization of requested accessory IDs/slots.
- `src/mochi/appearance/compositor.py` — override selection, anchor normalization, signed logical origins, deterministic render layers.

### New assets

- `assets/mochi/attachments.json` — classic Mochi attachment points for the milestone animations.
- `assets/accessories/round_glasses/manifest.json`
- `assets/accessories/round_glasses/default.png`
- `assets/accessories/green_beanie/manifest.json`
- `assets/accessories/green_beanie/default.png`
- `assets/accessories/pink_scarf/manifest.json`
- `assets/accessories/pink_scarf/default.png`
- Add animation-specific override PNGs only where live Milestone 0 QA proves the default sprite cannot meet the approved visual standard.

### Runtime integration

- `src/mochi/sprites.py` — accessory surface cache plus composite drawing under the same base-frame transform.
- `src/mochi/buddy.py` — initialize appearance runtime, resolve current layers, call composite renderer; no appearance logic.
- `src/mochi/app.py` — pass developer preview IDs to Buddy.
- `src/mochi/main.py` — hidden repeatable `--preview-accessory ACCESSORY_ID` developer flag.
- `pyproject.toml` — package attachment metadata and first-party accessory manifests/PNGs.
- `REGRESSION_WATCHLIST.md` — add appearance-rendering regressions after live proof.

### Tests

- `tests/test_appearance_catalogue.py`
- `tests/test_appearance_attachments.py`
- `tests/test_appearance_compositor.py`
- `tests/test_appearance_rendering.py`
- Modify `tests/test_main.py`
- Modify `tests/test_sprites.py`

---

### Task 1: Define and validate accessory manifests/catalogue

**Files:**
- Create: `src/mochi/appearance/__init__.py`
- Create: `src/mochi/appearance/models.py`
- Create: `src/mochi/appearance/validation.py`
- Create: `src/mochi/appearance/catalogue.py`
- Test: `tests/test_appearance_catalogue.py`

**Interfaces:**
- Produces:
  - `SOURCE_CELL_SIZE = (64, 64)`
  - `RUNTIME_CELL_SIZE = (256, 256)`
  - `SOURCE_TO_RUNTIME_SCALE = 4`
  - `BASE_LAYER_ORDER = 20`
  - `SLOT_DEFAULT_LAYER: dict[str, str]`
  - `LAYER_ORDER: dict[str, int]`
  - `AppearanceAssetError(ValueError)`
  - `AccessoryDefinition(id: str, display_name: str, slot: str, layer: str, source_cell_size: tuple[int, int], anchor: tuple[int, int], offset: tuple[int, int], assets: dict[str, Path], hide_during: frozenset[str], tags: tuple[str, ...])`
  - `load_accessory_definition(manifest_path: Path) -> AccessoryDefinition`
  - `AccessoryCatalogue(root: Path | None = None)`
  - `AccessoryCatalogue.get(accessory_id: str) -> AccessoryDefinition | None`
  - `AccessoryCatalogue.items() -> tuple[AccessoryDefinition, ...]`

- [ ] **Step 1: Write failing manifest/catalogue tests**

Add tests that create temporary accessory directories and assert:

```python
definition = load_accessory_definition(manifest_path)
assert definition.id == "round_glasses"
assert definition.slot == "face"
assert definition.source_cell_size == (64, 64)
assert definition.anchor == (32, 24)
assert definition.assets["default"] == accessory_dir / "default.png"
```

Also assert rejection of unsupported format, unknown slot/layer, missing default asset, declared source size other than 64×64, anchor outside 0–63, malformed JSON, and `../` asset-path escape.

Create temporary PNG fixtures and assert that an unreadable/corrupt PNG and a decodable PNG whose actual dimensions do not match the declared 64×64 source cell are rejected before entering the catalogue.

Add a catalogue test with one valid and one invalid directory: `items()` contains only the valid accessory and `get("missing") is None`.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_appearance_catalogue.py -q
```

Expected: FAIL because the appearance package/interfaces do not exist.

- [ ] **Step 3: Implement models and strict manifest parsing**

Use string slot/layer identifiers from the spec rather than introducing a dependency on GTK or current behavior enums.

`load_accessory_definition()` resolves asset paths against the manifest directory and verifies they remain inside that directory. During validation, decode each referenced PNG with Cairo only far enough to prove it is readable and that its dimensions exactly match the declared 64×64 v1 source cell; discard the temporary validation surface immediately. Cairo stays out of `models.py`, `attachments.py`, `loadout.py`, and `compositor.py`, so composition remains renderer-independent.

`AccessoryCatalogue` discovers:
1. an explicitly supplied `root`;
2. source-tree `assets/accessories`;
3. installed `Path(sys.prefix) / "share" / "mochi" / "accessories"`.

Invalid accessory directories are logged and skipped; they do not make catalogue construction fail.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_appearance_catalogue.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/appearance tests/test_appearance_catalogue.py
git commit -m "feat: add Mochi accessory catalogue"
```

---

### Task 2: Add classic per-frame attachment maps

**Files:**
- Create: `src/mochi/appearance/attachments.py`
- Create: `assets/mochi/attachments.json`
- Test: `tests/test_appearance_attachments.py`

**Interfaces:**
- Consumes: `RUNTIME_CELL_SIZE` from Task 1.
- Produces:
  - `AttachmentMap(path: Path | None = None)`
  - `AttachmentMap.point(animation_name: str, frame_index: int, slot: str, *, fallback_animation_name: str | None = None) -> tuple[int, int] | None`
  - `AttachmentMap.frame_count(animation_name: str) -> int | None`

- [ ] **Step 1: Write failing attachment-map tests**

Use a temporary attachment JSON file and assert:

```python
assert points.point("idle", 0, "head") == (128, 54)
assert points.point("idle", 0, "face") == (128, 102)
assert points.point("missing", 0, "head", fallback_animation_name="idle") == (128, 54)
assert points.point("idle", 99, "head") is None
assert points.point("idle", 0, "unknown") is None
```

Add malformed-format and non-integer/out-of-256-range point tests.

Add one test proving the actual animation name is preferred over the fallback when both exist.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_appearance_attachments.py -q
```

Expected: FAIL because `AttachmentMap` does not exist.

- [ ] **Step 3: Implement attachment loading and safe lookup**

The default path discovery mirrors the animation asset strategy:

```text
source:    assets/mochi/attachments.json
installed: $PREFIX/share/mochi/attachments.json
```

The file format is `mochi-attachments-v1`.

Populate authored `head`, `face`, and `neck` points for every frame of:

```text
idle
blink
walk
walk_left
sleeping
dragged
```

Use the current 256×256 runtime frame as the coordinate reference. These points are art metadata, not behavior data.

- [ ] **Step 4: Add a manifest/frame-count consistency test**

Load the real `AnimationAssetSet` and real attachment map. For every animation listed above, assert:

```python
assert attachments.frame_count(name) == len(ANIMATIONS[name].frames)
```

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_appearance_attachments.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/appearance/attachments.py assets/mochi/attachments.json tests/test_appearance_attachments.py
git commit -m "feat: add Mochi appearance attachment maps"
```

---

### Task 3: Add loadout normalization and pure appearance composition

**Files:**
- Create: `src/mochi/appearance/loadout.py`
- Create: `src/mochi/appearance/compositor.py`
- Modify: `src/mochi/appearance/models.py`
- Test: `tests/test_appearance_compositor.py`

**Interfaces:**
- Consumes:
  - `AccessoryCatalogue.get(id) -> AccessoryDefinition | None`
  - `AttachmentMap.point(...)`
  - Task 1 scale/layer constants.
- Produces:
  - `AppearanceLoadout(base: str, equipped: dict[str, str])`
  - `empty_loadout() -> AppearanceLoadout`
  - `normalize_loadout(requested: AppearanceLoadout, catalogue: AccessoryCatalogue) -> AppearanceLoadout`
  - `loadout_from_accessory_ids(ids: tuple[str, ...], catalogue: AccessoryCatalogue) -> AppearanceLoadout`
  - `RenderLayer(accessory_id: str, asset_path: Path, source_cell_size: tuple[int, int], x: int, y: int, order: int)`
  - `AppearanceCompositor(catalogue: AccessoryCatalogue, attachments: AttachmentMap)`
  - `AppearanceCompositor.layers_for(*, animation_name: str, frame_index: int, loadout: AppearanceLoadout, semantic_animation_name: str | None = None) -> tuple[RenderLayer, ...]`

- [ ] **Step 1: Write failing loadout/compositor tests**

Cover:

```text
unknown ID -> dropped
accessory placed under wrong requested slot -> dropped
later item in same slot replaces earlier preview item
animation-specific asset -> selected before default
actual animation override/attachment -> preferred over semantic fallback
semantic animation fallback -> used when actual name has no data
hide_during -> no layer
missing attachment -> no layer
negative origin -> preserved
layers -> returned in deterministic order
```

Pin the normalization example from the spec:

```python
# 64x64 source anchor (32, 16) -> runtime (128, 64)
# Mochi head point (128, 54)
layer = compositor.layers_for(...)[0]
assert (layer.x, layer.y) == (0, -10)
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_appearance_compositor.py -q
```

Expected: FAIL because loadout/compositor interfaces do not exist.

- [ ] **Step 3: Implement loadout normalization**

`loadout_from_accessory_ids()` is developer-preview support only. For each valid ID, use the accessory's own declared slot; later IDs replace earlier IDs in the same slot.

`normalize_loadout()` keeps base `classic` for this milestone and discards unknown IDs or slot/accessory mismatches without raising.

- [ ] **Step 4: Implement pure layer resolution**

For each normalized equipped accessory:

1. skip when the actual or semantic animation is explicitly hidden;
2. choose `assets[animation_name]`, then `assets[semantic_animation_name]`, then `assets["default"]`;
3. resolve attachment point from actual animation with semantic fallback;
4. multiply source anchor/offset coordinates by `256 / source_cell_size[0]` (v1 is exactly 4);
5. calculate signed logical origin;
6. assign deterministic layer order;
7. return sorted immutable layer tuple.

No Cairo, GTK, animation state transitions, or filesystem mutation belongs in this function.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_appearance_compositor.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/appearance tests/test_appearance_compositor.py
git commit -m "feat: compose Mochi appearance layers"
```

---

### Task 4: Composite accessory surfaces through the existing sprite renderer

**Files:**
- Modify: `src/mochi/sprites.py`
- Test: `tests/test_appearance_rendering.py`
- Modify/Test: `tests/test_sprites.py`

**Interfaces:**
- Consumes: `RenderLayer` from Task 3.
- Produces:
  - `SpriteAtlas.draw_composite(context: cairo.Context, frame: AnimationFrame, width: int, height: int, layers: tuple[RenderLayer, ...] = ()) -> None`
  - internal cached accessory loading keyed by resolved asset path and declared source cell size.
- Preserves:
  - existing `SpriteAtlas.draw(...)` as a compatibility wrapper calling `draw_composite(..., layers=())`.

- [ ] **Step 1: Write failing accessory-surface normalization tests**

Create a temporary 64×64 Cairo PNG and a synthetic `RenderLayer`.

Assert the renderer's cached normalized accessory surface is 256×256 and repeated loads reuse the cached object.

Add a regression assertion that ordinary `SpriteAtlas.draw()` remains callable and base-only rendering behavior is unchanged.

- [ ] **Step 2: Write a failing composite-order/offset test**

Render to an in-memory Cairo target with:
- one synthetic back layer below `BASE_LAYER_ORDER`;
- one synthetic front layer above it;
- a base frame between them;
- at least one signed/negative logical origin.

Assert representative pixels prove back → base → front order and that negative origins clip rather than raising.

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_appearance_rendering.py tests/test_sprites.py -q
```

Expected: FAIL because composite rendering is not implemented.

- [ ] **Step 4: Implement composite drawing**

Compute the base transform exactly once using the same centering, window scale, and `AnimationFrame.horizontal_offset` / `vertical_offset` math currently used by `SpriteAtlas.draw()`.

Within that transform:
1. draw accessory layers with order < `BASE_LAYER_ORDER`;
2. draw the base 256×256 sprite at logical origin `(0, 0)`;
3. draw remaining accessory layers at their signed logical `(x, y)`.

Normalize accessory source surfaces with nearest-neighbor scaling only.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_appearance_rendering.py tests/test_sprites.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/sprites.py tests/test_appearance_rendering.py tests/test_sprites.py
git commit -m "feat: render layered Mochi accessories"
```

---

### Task 5: Integrate appearance composition into Buddy without changing behavior ownership

**Files:**
- Modify: `src/mochi/buddy.py`
- Modify: `src/mochi/app.py`
- Modify: `src/mochi/main.py`
- Modify/Test: `tests/test_main.py`
- Test: `tests/test_appearance_rendering.py`

**Interfaces:**
- Consumes:
  - `AccessoryCatalogue`, `AttachmentMap`, `AppearanceCompositor`;
  - `AppearanceLoadout`, `empty_loadout()`, `loadout_from_accessory_ids()`;
  - `SpriteAtlas.draw_composite(...)`.
- Produces:
  - hidden repeatable CLI option `--preview-accessory ACCESSORY_ID`;
  - `MochiApplication(..., appearance_preview_ids: tuple[str, ...] = ())`;
  - `Buddy(..., appearance_preview_ids: tuple[str, ...] = ())`;
  - `Buddy.set_appearance(loadout: AppearanceLoadout) -> None` as the future public-Lab seam.

- [ ] **Step 1: Write failing CLI/plumbing tests**

In `tests/test_main.py`, assert:

```python
args = build_parser().parse_args([
    "--preview-accessory", "green_beanie",
    "--preview-accessory", "round_glasses",
])
assert args.preview_accessory == ["green_beanie", "round_glasses"]
```

The flag uses `argparse.SUPPRESS` help because it is developer-only for Milestone 0.

Add a lightweight Buddy/compositor seam test using an injected/fake catalogue/attachment setup or a directly assigned loadout so base-only and equipped drawing both reach `draw_composite` without altering state transitions.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_main.py tests/test_appearance_rendering.py -q
```

Expected: FAIL because preview IDs and Buddy appearance integration do not exist.

- [ ] **Step 3: Wire appearance initialization into Buddy**

During Buddy construction:
- build the default catalogue/attachment/compositor once;
- create an empty loadout unless preview IDs are supplied;
- expose `set_appearance()` to normalize/replace the loadout and `queue_draw()`.

In `_draw()`:
- keep the existing fallback to `ANIMATIONS["default"].frames[0]`;
- use `self.player.animation.name` as the actual rendered animation when available;
- pass `self._current_animation` as semantic fallback;
- request layers for the current `player.frame_index`;
- call `self.atlas.draw_composite(...)`.

Do not modify behavior state, animation selection, drag ownership, or timing.

- [ ] **Step 4: Pass developer preview IDs from CLI → application → Buddy**

Unknown/invalid preview IDs are ignored by loadout normalization. Launch must still succeed as plain Mochi.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_main.py tests/test_appearance_catalogue.py tests/test_appearance_attachments.py tests/test_appearance_compositor.py tests/test_appearance_rendering.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/main.py src/mochi/app.py src/mochi/buddy.py tests/test_main.py tests/test_appearance_rendering.py
git commit -m "feat: integrate Mochi appearance rendering"
```

---

### Task 6: Add the three production Milestone 0 accessories and package them

**Files:**
- Create: `assets/accessories/round_glasses/manifest.json`
- Create: `assets/accessories/round_glasses/default.png`
- Create: `assets/accessories/green_beanie/manifest.json`
- Create: `assets/accessories/green_beanie/default.png`
- Create: `assets/accessories/pink_scarf/manifest.json`
- Create: `assets/accessories/pink_scarf/default.png`
- Optional only if required by live QA: animation override PNGs within the same three directories.
- Modify: `pyproject.toml`
- Modify/Test: `tests/test_appearance_catalogue.py`
- Modify/Test: `tests/test_sprites.py`

**Interfaces:**
- Consumes: the Task 1 `mochi-accessory-v1` format and Task 2 classic attachment points.
- Produces built-in IDs:
  - `round_glasses` → slot `face`, layer `face`;
  - `green_beanie` → slot `head`, layer `head`;
  - `pink_scarf` → slot `neck`, layer `neck`.

- [ ] **Step 1: Write failing built-in inventory/package tests**

Assert a default `AccessoryCatalogue()` finds exactly those required milestone IDs (additional future built-ins do not fail the test).

Assert every built-in asset:
- is a valid 64×64 PNG;
- loads through `load_accessory_definition()`;
- has a default asset;
- has hard metadata-valid anchors.

In `tests/test_sprites.py`, inspect `pyproject.toml` and assert installed data includes:
- `assets/mochi/attachments.json`;
- each milestone accessory's `manifest.json`;
- each milestone accessory's `*.png`.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_appearance_catalogue.py tests/test_sprites.py -q
```

Expected: FAIL because built-in accessory assets/package entries are absent.

- [ ] **Step 3: Author and review the three real pixel-art accessories**

Create 64×64 full-frame transparent PNGs following the approved art rules:
- hard pixel edges;
- no anti-aliasing;
- no runtime-generated blur;
- restrained palette;
- readable at desktop size;
- anchor point located on the intended contact point.

Generated concepts may be used as references, but production files receive a pixel-level cleanup/review before commit.

- [ ] **Step 4: Add first-party manifests and setuptools data entries**

Package:
- `share/mochi/attachments.json`;
- `share/mochi/accessories/<id>/manifest.json`;
- `share/mochi/accessories/<id>/*.png`.

Ensure source checkout and installed-prefix catalogue discovery use the same directory shape.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_appearance_catalogue.py tests/test_sprites.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add assets/mochi/attachments.json assets/accessories pyproject.toml tests/test_appearance_catalogue.py tests/test_sprites.py
git commit -m "feat: add first Mochi Lab accessories"
```

---

### Task 7: Prove Milestone 0 live and lock regressions

**Files:**
- Modify only if QA proves required: `assets/mochi/attachments.json`
- Create only if QA proves required: override PNGs/manifests under the three milestone accessory directories.
- Modify: `REGRESSION_WATCHLIST.md`

**Interfaces:**
- Uses developer launch:
  - `mochi --preview-animations --preview-accessory round_glasses --preview-accessory green_beanie --preview-accessory pink_scarf`
- No new runtime interface unless a visual defect demonstrates a missing requirement from the approved spec.

- [ ] **Step 1: Run the complete automated appearance suite**

Run:

```bash
pytest   tests/test_appearance_catalogue.py   tests/test_appearance_attachments.py   tests/test_appearance_compositor.py   tests/test_appearance_rendering.py   tests/test_main.py   tests/test_sprites.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full regression suite**

Run:

```bash
pytest -q
```

Expected: PASS with only already-documented environment skips.

- [ ] **Step 3: Launch the dressed animation preview**

Run:

```bash
mochi --debug --preview-animations   --preview-accessory round_glasses   --preview-accessory green_beanie   --preview-accessory pink_scarf
```

Cycle and visually inspect:

```text
idle
blink
walk
sleeping
dragged
```

Also inspect `walk_left` because real autonomous motion uses both directions.

Pass criteria for every required animation:
- all three accessories remain equipped;
- no blur/interpolation;
- no obvious one-frame jump caused by missing attachment metadata;
- accessory follows whole-frame drag/body offsets;
- head/face/neck item does not visibly detach from Mochi;
- base animation timing/state behavior is unchanged.

- [ ] **Step 4: Fix art metadata before writing behavior code**

For a failing visual:
1. adjust attachment coordinates if the item is merely misplaced;
2. add an animation-specific accessory override if the pose changes the item's shape/occlusion;
3. use `hide_during` only if a required override cannot reasonably preserve the item.

Do not add special cases to Buddy/state logic to fix artwork.

Repeat Steps 1–3 until the Milestone 0 pass criteria hold.

- [ ] **Step 5: Verify base-only Mochi**

Run:

```bash
mochi --debug --preview-animations
```

Expected: visual behavior matches pre-feature Mochi with no accessories and no new warnings/errors.

- [ ] **Step 6: Update regression watchlist**

Add:
- accessory surfaces must stay nearest-neighbor;
- actual/semantic animation fallback must not detach items;
- drag frame offsets must move base + accessories together;
- missing/broken appearance assets must fall back without startup failure;
- installed package must include attachment/accessory data.

- [ ] **Step 7: Commit QA corrections/documentation**

```bash
git add assets/mochi/attachments.json assets/accessories REGRESSION_WATCHLIST.md
git commit -m "test: lock Mochi appearance regressions"
```

If Step 4 required no asset changes, commit only the watchlist update.

---

## Milestone completion gate

Milestone 0 is complete only when all of the following are true:

- `pytest -q` passes;
- `round_glasses`, `green_beanie`, and `pink_scarf` are discoverable in both source and installed layouts;
- dressed Mochi passes idle, blink, walk, walk-left, sleeping, and dragged live QA;
- the same accessory loadout follows authored `AnimationFrame` whole-frame offsets during drag;
- launching with no preview accessories is visually/regression-equivalent to current classic Mochi;
- invalid or missing accessory data cannot prevent base Mochi from rendering;
- no persistence, public Lab UI, alternate bodies, community packs, or effect-system scope has leaked into this branch.

## Follow-on plans after Milestone 0

Write separate plans only after this milestone is proven:

1. **Attachment editor + accessory stress-test tooling**
2. **Appearance persistence + live switching**
3. **Public Mochi Lab character-creator UI**
4. **Alternate base variants**
5. **Community accessory-pack discovery**
6. **Effects subsystem**
