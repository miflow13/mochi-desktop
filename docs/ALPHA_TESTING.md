# Mochi public-alpha testing

Mochi `0.2.0a1` prioritizes reliable interaction and animation-state recovery.
Please test from a normal user session rather than running Mochi as root.

## Quick validation

1. Launch `mochi --debug` and confirm the PixelLab idle artwork appears with a
   transparent background.
2. Single-click repeatedly, then double-click. Click reactions must finish and
   the heart must play without a delayed extra single-click reaction.
3. Drag Mochi slowly and quickly, hold for at least six swing cycles, then drop.
   The held loop should remain continuous and the plop should return to idle.
4. Immediately right-click after dragging. Open and close the menu repeatedly;
   input must remain responsive.
5. Start walking, interrupt it with a drag or click, and confirm the saved drop
   position is accurate.
6. Put Mochi to sleep, wake him, and verify both transitions finish cleanly.
7. Run Computer and Emote from the context menu. Computer should play its intro,
   type for 3–4 seconds, play its outro, and return to idle; neither action
   should interrupt a held or sleep/wake transition.
8. Use the Developer section to test Held, Drop, and Computer repeatedly, then
   choose Return to Idle.
9. Leave Mochi running for at least 30 minutes and confirm ambient actions do not
   accelerate, overlap, or accumulate.
10. Quit and relaunch. Size, sound settings, and the last valid position should
    be restored.

For an automated baseline, run:

```bash
python3 -m unittest discover -s tests -v
git diff --check
python3 -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
```

## Known limitations

- Fedora GNOME is the primary alpha target. Other GTK4 Linux desktops need more
  coverage.
- GNOME Wayland uses XWayland by default so the undecorated window can be moved
  reliably. Set `MOCHI_NATIVE_WAYLAND=1` only when intentionally testing native
  Wayland behavior.
- Walking currently reuses the canonical bounce cycle and does not face left or
  right with distinct artwork.
- Audio files are placeholders and missing sounds are intentionally ignored.
- The status panel reports presentation-only placeholder health; there is no
  health or care gameplay system in this alpha.

## Reporting a problem

Include:

- distribution, desktop environment, and whether the session is Wayland or X11;
- installation method and Mochi version;
- exact interaction sequence;
- expected and observed behavior;
- whether right-click and dragging still worked afterward;
- relevant `mochi --debug` lines;
- a short screen recording for visual seams or transparency problems, if useful.
