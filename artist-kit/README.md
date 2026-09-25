# Mochi Artist Kit 🌱

Want to make Mochi do something new? This kit is the starting point for community-made Mochi art and animation.

You do **not** need to be a programmer to make an animation. The goal is to give pixel artists and animators the same visual and runtime references used by Mochi itself, then make the handoff into the project predictable.

## What's already released

Mochi's production artwork is kept openly in this repository:

- [Master reference](../assets/mochi/master/mochi_default.png) — the canonical default Mochi pose.
- [Animation library](../assets/mochi/) — the shipped PNG frames and spritesheets.
- [Animation manifest](../assets/mochi/manifest.json) — exact frame order, timing, loop behavior, source cell sizes, and runtime names.
- [Runtime asset rules](../assets/mochi/README.md) — the production contract used by the app.

The shipped animation library is intentionally the best reference for Mochi's current proportions, expressions, movement, props, and animation language.

## Character rules

Mochi should read as the same little character even when an animation gets weird.

- Preserve the soft green blob silhouette and simple pixel-art language.
- Keep the face readable at desktop scale.
- Favor expressive body deformation over adding unnecessary detail.
- Props can support the joke or action, but Mochi should remain the focal point.
- Keep hard pixel edges. Do not blur, antialias, interpolate, or smooth the artwork.
- Preserve transparent backgrounds.
- Keep Mochi grounded consistently unless the animation intentionally jumps, floats, hangs, or is being held.
- Start and end one-shot animations in poses that can transition cleanly to the intended surrounding state.

For exact visual reference, work from `assets/mochi/master/mochi_default.png` and existing shipped animations rather than recreating Mochi from memory.

## Canvas and export contract

The runtime contract is:

| Property | Mochi standard |
| --- | --- |
| Canonical runtime canvas | **256 × 256 px** |
| Format | **PNG with alpha** |
| Anchor | **bottom-center** |
| Scaling | **nearest-neighbor** |
| Normal frame naming | `<animation>_01.png`, `<animation>_02.png`, ... |
| Background | transparent |

Smaller authored cells are supported. Existing animations use source cells such as 64 × 64 and 128 × 128; when that happens, `source_cell_size` is declared in the manifest and Mochi scales the artwork in memory with nearest-neighbor filtering. Do not resample source artwork just to make it 256 × 256.

Keep transparent padding intentional and consistent across frames. A changing canvas origin will make Mochi appear to jitter even when the drawing itself is correct.

## Animation language

Think in states and transitions rather than isolated GIFs:

`current state → entry → active action/loop → exit → appropriate idle state`

A short emote such as a wave or heart is normally a one-shot. A sustained activity such as sleeping, walking, typing, or focusing can loop. If an activity has a distinct entry or exit, author those separately rather than forcing the loop to perform both jobs.

Existing animations in `assets/mochi/` are examples of both patterns.

### Timing

There is no single required FPS. Timing is part of the animation.

The current manifest includes deliberately different rates: slow breathing loops, faster tactile reactions, and longer contextual sequences. Choose timing that makes the action readable, then include your intended FPS with the submission. The maintainer may tune runtime timing during integration.

## Make an animation

1. Copy `assets/mochi/master/mochi_default.png` into your art workspace as the character reference.
2. Decide whether the idea is a **one-shot emote**, **loop**, or **entry / loop / exit** state.
3. Draw each frame without smoothing or interpolation.
4. Keep the bottom-center anchor and transparent padding stable.
5. Export transparent PNGs using sequential names.
6. Preview the sequence at nearest-neighbor scaling.
7. Include a short note with:
   - animation name,
   - what triggers it,
   - intended FPS,
   - whether it loops,
   - source cell size,
   - and any sound/prop notes.
8. Share it with the Mochi project. Runtime integration can happen separately from the artwork.

## Submission template

```text
Animation:
Creator:
Type: one-shot / loop / entry-loop-exit
Source cell size:
Intended FPS:
Loop:
Trigger idea:
Description:
Notes:
```

A GIF preview is welcome, but please include the original transparent PNG frames or spritesheet. The preview is not the runtime source.

## For contributors integrating the animation

Production assets belong under `assets/mochi/<animation>/`.

When integrating art into Mochi:

1. Add only final runtime PNGs/spritesheets.
2. Add the animation definition to `assets/mochi/manifest.json`.
3. Add a new asset directory to `pyproject.toml` when necessary.
4. Make loop/transition semantics match the behavior.
5. Preview it in Mochi Lab.
6. Run `python -m pytest tests/test_sprite_loader.py`.
7. Run the full test suite.
8. Verify the transition back to the correct live state.

Do not place Pixelorama project files, export ZIPs, temporary renders, or superseded frames inside the runtime asset tree.

## Attribution

Community submissions should include the creator's preferred name/handle and, when applicable, a link they want associated with the contribution. Contributions accepted into Mochi will be credited in the project where practical.

## License

Mochi is released under the repository's [MIT License](../LICENSE). By submitting artwork for inclusion in Mochi, make sure you have the right to contribute it under the project's license. Do not submit copyrighted characters, logos, or artwork you do not have permission to contribute.

## Make Mochi weird 💚

Cute is welcome. Tiny is welcome. Dramatic is welcome. Linux jokes are *very* welcome.

The important part is that when the animation ends, it still feels like Mochi.
