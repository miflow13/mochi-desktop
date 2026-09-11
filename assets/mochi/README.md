# Mochi Animation Library

`assets/mochi/` is the runtime animation library for Mochi. Keep this directory small, predictable, and production-only.

## Source of truth

`manifest.json` is authoritative. Every runtime PNG in this directory must be declared by the manifest, and every manifest frame must exist on disk.

Do not keep export ZIPs, spritesheets, Pixelorama source files, temporary renders, superseded animation sets, or handoff packages in this directory. Keep authoring/source material outside the runtime asset tree.

## Canonical asset rules

- Canvas: **256 × 256 px** per runtime frame.
- Format: **PNG with alpha**.
- Scaling: **nearest-neighbor**.
- Character anchor: **bottom-center**.
- Keep transparent padding intentional and consistent within an animation.
- Normal sequential frames use `<animation>_01.png`, `<animation>_02.png`, and so on.
- Semantic drag poses are the intentional exception and use names such as `drag_left_soft.png` and `drag_settle_neutral.png`.
- Looping should describe sustained states only. Transitions and one-shot emotes should not loop unless the animation is explicitly designed as a held state.
- Update `manifest.json` in the same change whenever frames are added, removed, renamed, or reordered.
- Run `python -m pytest tests/test_sprite_loader.py` after changing the animation library.

## Current library roles

### Core / locomotion

- `default` — canonical single-frame fallback.
- `idle` — breathing/base idle loop.
- `blink` — one-shot blink layered into idle behavior.
- `walk`, `walk_left` — autonomous/manual walking loops.
- `pickup` — transition into being held.
- `dragged` — held/drag velocity poses, sourced from `drag/`.
- `drop` — release transition.
- `sleep`, `sleeping`, `wake` — sleep transition, held sleep state, and wake transition.

### Direct interaction emotes

- `bounce` — tactile click reaction.
- `squish` — tactile click reaction.
- `heart` — affectionate one-shot emote.

### Ambient / contextual activity

- `computer` — computer-use emote source sequence.
- `typing_intro`, `typing_loop`, `typing_outro` — sustained typing state.
- `terminal_loop` — focused-terminal coworking loop; intro/outro slots intentionally reserved.
- `watch` — media/watch-along state.
- `searching` — file/search activity state.
- `sway_idle` — drag/held idle motion.

The runtime also derives helper animations such as `computer_intro`, `computer_typing`, `computer_outro`, and `excited` in Python. Those derived names do not need duplicate assets in the manifest.

## Adding a new emote

1. Finish and clean the source animation first.
2. Export only final 256 × 256 transparent PNG frames.
3. Create one clearly named folder under `assets/mochi/`.
4. Add the animation to `manifest.json` with the correct frame order, frame count, FPS, and loop behavior.
5. Add/package the folder in `pyproject.toml` if it is a new directory.
6. Preview it in Mochi Lab and verify transitions back to the intended state.
7. Run the sprite-loader tests and the full test suite.

Reading will be integrated after its source ZIP is cleaned and re-exported; it should enter as a low-energy ambient idle emote rather than as an undeclared loose asset.
