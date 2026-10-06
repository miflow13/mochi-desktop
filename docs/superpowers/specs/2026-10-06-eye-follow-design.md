# Eye-Follow — Design

**Date:** 2026-10-06

**Builds on:** the Pocket Hover Tray (`docs/superpowers/specs/2026-10-06-pocket-hover-tray-design.md`). Both features extend the same pointer handlers, and this one ships second.

**Design canvas:** https://claude.ai/artifact/EEcdHQWgSR5BWenQzMoRDJ ("Eyes follow the pointer" board; the prototype's eyes really follow)

**Status:** design written for review. The implementation plan is deliberately deferred until the Pocket hover tray lands, because its code would otherwise target pointer handlers that are about to change.

## Purpose

When the pointer comes close, Mochi's eyes follow it. It is a small, silent sign that he notices you. It costs nothing to ignore, and it makes resting on him (to open the Pocket) feel like he is looking at what you are doing.

## Goals

- While Mochi is standing idle, his eyes look toward the pointer when it is near him.
- Eight directions plus "ahead", snapped to his pixel grid. No smooth pupils.
- Calm: no jitter at sector edges, and he loses interest when the pointer stops moving.
- Works on every session while the pointer is over Mochi's own window.
- Reaches about twice his size away when the GNOME helper is installed.
- No pointer coordinates ever leave GNOME Shell. Mochi learns a direction, never a position.
- Costs nothing while the pointer is far away or the feature is off.
- One off switch.

## Non-goals

- Head turning, leaning, or body motion. Only the eyes move.
- Following while walking, sleeping, waking, held, mid-emote, mid-reaction, in Focus or Fedora, or during an idle look beat.
- Following beyond Mochi's own window without the GNOME helper.
- Polling `XQueryPointer`. Under XWayland the X server only learns the pointer position over X11 surfaces, so polling would freeze while the pointer is over native Wayland apps. This is a strong hypothesis that the plan's first task verifies; polling would also add a wakeup loop Mochi does not have today.
- A new `MochiState`, speech, or sound.

## Behavior

### Zones

Measured from Mochi's eye point: horizontally centred, and 68.4% of the way down his window. That is where the eyes sit in `idle_01`, at canvas rows 160–191 of 256.

| Zone | Rule | At the default 112 px size |
|---|---|---|
| Follow | distance ≤ 2.0 × size | ≤ 224 px |
| Keep following (hysteresis) | until distance > 2.35 × size | 263 px |
| Look ahead (dead zone) | distance ≤ 0.2 × size | ≤ 22 px |

Directions are eight 45° sectors centred on N, NE, E, SE, S, SW, W and NW. Screen y grows downward.

### Timing

- **Debounce.** A new direction must hold for 70 ms before the eyes switch, so the pointer sitting on a sector edge never flickers him.
- **Attention.** After 4 s without a direction sample (the pointer is still), he returns to his normal idle animation until the pointer moves again.

### When the eyes follow

Only when `Buddy._is_idle_visual_active()` is true (state `IDLE` with the `idle` animation) and `_idle_look_active` is false.

- **Blinks** keep playing: `BLINKING` draws the blink frames, and the gaze resumes when he returns to `IDLE`.
- **The hover heart, the Pocket offer, walks, emotes and reactions** all draw their own frames.
- **After the Pocket tray opens,** Mochi returns to `IDLE` and his eyes follow the pointer into the tray.

### Pointer sources

1. **Over Mochi** (every session). The existing `Gtk.EventControllerMotion` already delivers `(x, y)` inside his window. The mixin extends `_on_motion` and `_on_leave` with `super()` first, like the Pocket dwell.
2. **Near Mochi** (GNOME helper). The helper gains:
   - a method, `SetGazeTracking(b enabled)`;
   - a signal, `PointerGaze(s direction)`, where `direction` is one of `ahead`, `n`, `ne`, `e`, `se`, `s`, `sw`, `w`, `nw`, `far`.

   While enabled, the helper's **existing 50 ms poll** (`POLL_INTERVAL_MS`) also does three things:
   - reads `global.get_pointer()`;
   - finds Mochi's window by its WM_CLASS (cached, and refreshed on window created and unmanaged; the exact WM_CLASS is verified on device in the plan's first task);
   - applies the same zone rule to the window's frame rect, and emits only when the bucket changes.

   Disabled means no pointer reads and no emission.
3. **Precedence.** While the pointer is inside Mochi's window, the GTK source wins and helper signals are ignored.

Mochi calls `SetGazeTracking(true)` when the setting is on, the helper is present, he is not asleep, and he is not in preview mode. He calls `SetGazeTracking(false)` when the setting turns off, he falls asleep, or presence shuts down. He does **not** toggle tracking on every state change, which would be bus chatter; signals that arrive while he is not in the idle visual are simply ignored. A helper that predates the method returns an error, which is logged at debug level only; Mochi then uses source 1 alone.

### The off switch

The user context menu gains an **Eyes follow you** switch row after **Stay put**, built the same way as Stay put and Edge roam (the whole row is the target). It is stored in `config.json` as `eye_follow_enabled` and defaults to `true`.

## Art

Nine gaze frames are needed. "Ahead" is the existing `idle_01`. The other eight are new.

- **Placeholder set (proposed to ship):** generated deterministically from `idle_01` by `tools/build_gaze_frames.py`. The script follows the existing `tools/build_*.py` convention and uses Pillow at build time only, not at runtime. It flood-fills each eye (eye black, highlight, outline), fills the vacated pixels with the surrounding body colour, and redraws the eye 2 art-px sideways and 1 art-px up or down. One art pixel is 4 canvas pixels. These frames are what the design canvas shows.
- **Runtime location:** `assets/mochi/gaze/gaze_{n,ne,e,se,s,sw,w,nw}.png`, on the canonical 256 × 256 canvas and bottom-centre anchored. They are declared in `manifest.json` as one non-looping `gaze` set in the fixed order `n, ne, e, se, s, sw, w, nw`, and packaged with a new `"share/mochi/gaze"` entry in `pyproject.toml`, following Manual §9 "Adding a new animation".
- **Artist replacement:** an artist can later replace the eight files one-for-one without code changes.

## Presentation seam

Add one tiny seam to `Buddy._draw`: `frame = self._frame_for_draw()`. The base implementation returns `self.player.frame`; the existing default-frame fallback stays in `_draw`.

`EyeFollowMixin._frame_for_draw()` returns the gaze frame only while following and in the idle visual, and otherwise defers to `super()`. Nothing else in the draw path changes: no `_play_animation`, no transition. Mochi calls `queue_draw()` only when the direction changes.

## Architecture

```text
GTK motion (inside Mochi) ─┐
                           ├─► GazeTracker (gaze.py, GTK-free) ─► EyeFollowMixin._frame_for_draw()
Helper PointerGaze(s) ─────┘        zones · debounce · attention
        ▲
        │ SetGazeTracking(b)
EyeFollowMixin (presence/eye_follow.py)
```

- **`src/mochi/gaze.py` (new, GTK-free):**
  - `Gaze` enum;
  - `gaze_for_offset(dx, dy, size, *, following) -> Gaze | None` (zones and hysteresis; `None` means far);
  - `GazeTracker`, which holds the debounce and attention timers through injected `timeout_add` and `source_remove`, like `PocketHoverDwell`, and calls `on_change(gaze | None)`.
- **`src/mochi/presence/eye_follow.py` (new):** `EyeFollowMixin`. It is a mixin because every entry point is a cooperative-chain hook (`_frame_for_draw`, `_on_motion`, `_on_leave`, `_build_context_menu`, `shutdown_presence`, presence hooks), the same rationale the manual gives for `ActiveWindowCuriosityMixin`. It sits directly below `IdleLookMixin` in both buddy class lists.
- **`src/mochi/presence/signals.py`:** `PointerGazeSignalAdapter`, following `AppCategorySignalAdapter`, plus the fire-and-forget `SetGazeTracking` call on the existing helper connection.
- **`gnome-extension/mochi-typing@miflow13/extension.js`:** the interface XML method and signal, the poll addition, and the cached window lookup. There is no new JS module, because the installer copies files by name.
- **`src/mochi/config.py`:** `load_eye_follow_enabled()` and `save_eye_follow_enabled()`.
- **`src/mochi/buddy.py`:** the one-line `_frame_for_draw()` seam.
- **Assets:** eight PNGs, a manifest entry, and a `pyproject.toml` data-files entry.

## Privacy

`docs/CODEBASE_MANUAL.md` §14 says the helper never transmits pointer coordinates. **That stays true.** What crosses D-Bus is one of ten words about where the pointer is relative to Mochi's own window, and only when all of these hold:

- the pointer is within about twice his size;
- Mochi asked for it;
- the direction changed.

Like every other helper signal, it is visible to other processes on the session bus, and that reveals the coarse direction of the pointer relative to Mochi while it is near him. `docs/ambisense.md` and §14 will say exactly that.

Mochi never stores or logs gaze directions at info level.

## Performance

- **Helper:** only while enabled, one `global.get_pointer()` and a cached rect read per existing 50 ms tick, and emission only on change. Disabled, it does no extra work.
- **Mochi:** a redraw only on a direction change. The attention timer exists only while following. While the pointer is far away there is no timer and no redraw.

## Testing strategy

- **`tests/test_gaze.py`:**
  - every sector;
  - the dead zone;
  - hysteresis at 2.0 and 2.35 × size;
  - scaling with Mochi's size;
  - the 70 ms debounce;
  - the 4 s attention timeout;
  - far clears the gaze.
- **`tests/test_eye_follow.py`:**
  - the draw seam swaps the frame only in the idle visual, and not during an idle look;
  - blink, heart, walk and the offer are untouched;
  - motion and leave forward to `super()` first;
  - helper signals are ignored while hovered and while not idle;
  - setting off stops tracking and calls `SetGazeTracking(false)`;
  - sleep disables tracking;
  - shutdown cancels the timers;
  - the context-menu row toggles and persists.
- **`tests/test_presence_engine.py`, `tests/test_helper_lifecycle.py`, `tests/test_helper_dbus_integration.py`:**
  - the adapter subscription count;
  - signal dispatch;
  - a method-call failure is tolerated.
- **`tests/test_gnome_shortcuts.py`** (extension source contracts):
  - the method and the `(s)` signal are declared;
  - no numeric variant is emitted;
  - the pointer is read only inside the enabled branch;
  - there is no new JS file.
- **`tests/test_sprites.py` and `tests/test_sprite_loader.py`:** the eight gaze frames exist, load on the canonical canvas, and are packaged.

## Manual Fedora/GNOME verification

1. With the helper: move the pointer in a slow circle about 150 px around Mochi. His eyes step through all eight directions without flicker.
2. Rest the pointer next to him for 5 s. He goes back to his idle breathing.
3. Move away past about 2.4 × his size. He looks ahead.
4. Without the helper (disable the extension): his eyes follow only while the pointer is over him.
5. Hover over native Wayland apps (GNOME Text Editor, Files) near Mochi. With the helper, tracking still works.
6. During blink, heart, walk, Pocket offer, sleep, Focus and Fedora, there is no gaze. After each, he resumes.
7. Open the Pocket tray. His eyes follow the pointer into it.
8. Turn the context-menu switch off. No following, and `dbus-monitor` shows no `PointerGaze` traffic. Turn it on again; the setting persists across a restart.
9. Fractional scaling at 125% and 150%: directions stay correct.
10. Check `journalctl` for no gaze logging at info level.

## Open decisions

1. **Ship the generated placeholder gaze frames, or wait for artist-drawn ones?** Proposed: ship them; they are replaceable one-for-one.
2. **Where does the switch live: the user context menu, or Mochi Lab?** Proposed: the context menu, after Stay put.
3. **On by default?** Proposed: yes. It is silent, local, and off is one click away.

## Risks

- **Window lookup:** the helper's lookup depends on Mochi's real WM_CLASS under GTK4/XWayland. The plan's first task records it from a running session before writing the lookup.
- **Sessions without the helper** get a much smaller effect. That is acceptable and documented.
- **Bus visibility** of the coarse direction while near Mochi is a real, if small, disclosure. It is documented, and it stops completely when the switch is off.
