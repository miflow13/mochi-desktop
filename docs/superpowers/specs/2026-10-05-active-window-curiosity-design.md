# Active Window Curiosity — Design

**Date:** 2026-10-05

**Builds on:** PR #133 (`feat/active-window-curiosity`), which this work supersedes

**Status:** design approved; implementation plan not yet written

## Purpose

Mochi should notice when you move your attention: switching windows or settling on a different browser tab. The reaction must be noticeable when Mochi is free to show it and nearly invisible when he is busy. It must never interrupt direct interaction or a higher-priority presentation.

PR #133 shipped an overlay-only version: a thought bubble with a category label and a small lean. It is safe, but easy to miss, and it cannot see tab changes. This design keeps PR #133's signal plumbing and safety guards, and adds three things: browser tab awareness, a real "investigating" beat built from the existing magnifying-glass `searching` art, and calmer rate limits.

## Goals

- React to focused-window switches, including two windows of the same category.
- React to browser tab changes after the user settles on a tab.
- When Mochi is standing idle, play one short magnifying-glass beat and return to idle where he left off.
- When Mochi is busy, show only a small overlay cue that never changes his animation or behavior state.
- Keep AmbiSense's privacy boundary: no window title, application ID, URL, or content leaves GNOME Shell.
- Degrade gracefully when the GNOME extension is old, disabled, or missing.

## Non-goals

- Knowing *what* the user switched to beyond the existing coarse category.
- Pointing Mochi at the focused window's on-screen location. That would need window geometry, which AmbiSense deliberately does not expose.
- Reacting to title changes in non-browser apps. Terminals and editors retitle constantly.
- A new user-facing toggle. Quiet mode and the existing ambient-reactions control already cover opting out.
- New animation assets.

## Behavior

### Triggers

| Trigger | Source | Gate before reacting |
|---|---|---|
| Window switch | `AppFocusChanged(s category)` (from PR #133) | 180 ms debounce, so a quick Alt-Tab pass doesn't flash |
| Browser tab change | `BrowserTabChanged()` (new, no payload) | 1.5 s settle: no further tab pulse while the same browser window stays focused |

There is one pending timer, and the latest trigger wins. A window pulse cancels a pending tab settle, and each new tab pulse restarts the settle.

### Reaction ladder

When a trigger survives its gate, Mochi takes the first reaction that is allowed. Nothing is queued or retried.

1. **Investigate beat.** Allowed when Mochi is in his plain standing-idle visual (`_is_idle_visual_active()`), curiosity is allowed (see Suppression), at least 120 s have passed since the last beat, and at least 20 s have passed since the last reaction of either kind. Mochi plays `investigate`, a single pass of `searching` lasting about 2.4 s, then resumes idle at the saved frame and elapsed time.
2. **Overlay cue.** Allowed when curiosity is allowed, Mochi's state is one of `IDLE`, `BLINKING`, `WALKING`, `TYPING`, `COMPUTER`, and at least 20 s have passed since the last reaction of either kind. It shows a thought bubble containing a small Cairo-drawn magnifying glass for 1.8 s, plus a lean of up to 4 px toward the monitor center. Behavior state and animation stay untouched.
3. **Drop.**

The 20 s gap is shared: every reaction, beat or cue, resets it, so no two reactions ever land within 20 s of each other. The beat additionally has its own 120 s cooldown.

### Suppression

No trigger is scheduled or acted on, and an active cue is cleared, while any of these hold:

- preview mode or presence shutdown
- user idle / sleeping
- context menu open, active press, or active drag
- `PresentationState` other than `NORMAL` (Focus session and similar)
- AmbiSense tuning has `quiet_mode` on or `ambient_reactions_enabled` off

An active cue started in an allowed state may finish if Mochi moves into another cue-allowed state, such as `IDLE` to `TYPING` when terminal coworking begins. This is PR #133's existing continuation rule.

### Interruption

- **Press:** cancels the pending timer and clears an active cue immediately.
- **Any real state change during the beat** (typing, coworking, heart, watching, searching, dancing, computer, or any `_play_animation` with another name): handled by the existing idle-look cancellation, which restores idle. The beat cooldown stays consumed.

## Signals and privacy

### GNOME extension (`gnome-extension/mochi-typing@miflow13/extension.js`)

On every `notify::focus-window`:

1. Disconnect the title handler from the previously tracked window, if any.
2. If the new focused window classifies as `browser`, connect `notify::title` on it. Record a **baseline digest** of its normalized title, and emit nothing.
3. Otherwise, track no window and clear the digest.

On `notify::title` for the tracked window:

1. Read the title and normalize it: trim, then strip one leading unread badge matching `^\(\d+\+?\)\s*`, e.g. `(3) ` or `(99+) `.
2. Compute `GLib.compute_checksum_for_string(GLib.ChecksumType.SHA256, normalized, -1)`.
3. If the digest differs from the stored one, store it and emit `BrowserTabChanged` through the existing zero-payload `_emitSignal()` helper.

On `disable()`: disconnect the title handler, and clear the tracked window and digest.

Privacy properties:

- The raw title is never logged, stored, or sent. Only a one-way digest of the normalized title stays in GNOME Shell memory, and only for the focused browser window.
- Titles of non-browser windows are never observed.
- `BrowserTabChanged` carries no payload. It reveals only *when* the user changed tab or page.
- Like every AmbiSense signal, these pulses go over the session bus, so other processes in the user's session could observe their timing. This is documented next to the signal.

### Mochi (`src/mochi/presence/signals.py`, `integration.py`)

- `AppCategorySignalAdapter` gains `TAB_SIGNAL_NAME = "BrowserTabChanged"` and an optional `on_tab_changed: Callable[[], None]`. It subscribes alongside `AppCategoryChanged` and `AppFocusChanged`, for 3 subscriptions in total.
- `integration.py` wires `on_tab_changed=self._on_presence_browser_tab_changed`, a base hook that only logs at debug level, mirroring PR #133's focus hook.

### Version mismatch

| Extension | Mochi | Result |
|---|---|---|
| old (no tab signal) | new | Window-only curiosity; the tab subscription simply never fires |
| new | old | Signal ignored |

Extension code reloads only after GNOME Shell restarts (log out and back in on Wayland).

## Architecture

```
extension.js ──AppFocusChanged(cat)──┐
             ──BrowserTabChanged()───┤
                                     ▼
signals.py  AppCategorySignalAdapter (on_focus_changed / on_tab_changed)
                                     ▼
integration.py  base hooks (debug log only)
                                     ▼
curiosity.py  ActiveWindowCuriosityMixin
   ├─ window pulse → 180 ms debounce ─┐
   ├─ tab pulse    → 1.5 s settle ────┤  single pending GLib source; latest wins
   │                                  ▼
   │               _react_to_curiosity()
   │                  ├─ beat allowed → _play_idle_beat("investigate")  ──► idle_look.py
   │                  ├─ cue allowed  → overlay cue (lean + magnifier bubble)
   │                  └─ else drop
   └─ _draw / _tick / _on_pressed / shutdown_presence
```

### `src/mochi/sprites.py`

```python
ANIMATIONS["investigate"] = replace(
    ANIMATIONS["searching"], name="investigate", looping=False
)
```

This follows the existing `excited` derivation. It reuses `searching` frames that are already loaded, and the file-activity `searching` loop is unaffected.

### `src/mochi/presence/idle_look.py`: one owner for standing-idle beats

- Add `_idle_beat_animation: str | None`, the name of the beat currently owning presentation.
- Add `_play_idle_beat(name: str) -> bool`. It has the same guard as today (`_can_start_idle_look()`), saves the idle resume position, sets `_idle_look_active = True` and `_idle_beat_animation = name`, and plays `ANIMATIONS[name]`.
- `_play_idle_look()` becomes `return self._play_idle_beat(self.IDLE_LOOK_ANIMATION)`.
- `_finish_reaction`, `_play_animation`, `_restore_idle_after_look` and the debug logs compare against `_idle_beat_animation` instead of the hard-coded `IDLE_LOOK_ANIMATION`. Restore clears `_idle_beat_animation`.
- `_idle_look_active` keeps its name and remains the **single** flag. Its docstring changes to "a standing-idle beat owns presentation". Existing interruption overrides (typing, watching, searching, dancing, computer, heart, terminal and VS Code coworking) therefore cover the investigate beat with no new code.
- The `look` timer is unchanged. If it fires during a beat, `_can_start_idle_look()` is false and it reschedules, which is existing behavior.

### `src/mochi/presence/curiosity.py`: PR #133's mixin, revised

Constants block (the one place to tune):

| Constant | Value |
|---|---|
| `CURIOSITY_DEBOUNCE_MS` | 180 |
| `CURIOSITY_TAB_SETTLE_MS` | 1500 |
| `CURIOSITY_BEAT_COOLDOWN_SECONDS` | 120.0 |
| `CURIOSITY_CUE_COOLDOWN_SECONDS` | 20.0 |
| `CURIOSITY_CUE_DURATION_SECONDS` | 1.8 |
| `CURIOSITY_LEAN_PX` | 4.0 |
| `CURIOSITY_BEAT_ANIMATION` | `"investigate"` |

Changes from PR #133:

- Remove `CURIOSITY_MIN_GAP_SECONDS`, `CURIOSITY_SAME_CATEGORY_GAP_SECONDS`, `_CURIOSITY_LABELS` and the text rendering. The bubble draws a magnifying glass (circle plus handle) with Cairo.
- Replace `_curiosity_category: str | None` with `_curiosity_cue_active: bool`. Keep the category only for the debug log.
- Add `_on_presence_browser_tab_changed()`, which (re)starts the shared pending source with the settle delay.
- `_on_presence_app_focus_changed(category)` validates the category, then (re)starts the shared source with the debounce delay.
- `_react_to_curiosity()` implements the reaction ladder and records `time.monotonic()` timestamps for `_curiosity_last_beat_at` and `_curiosity_last_reaction_at`.
- Keep `_curiosity_allowed`, `_curiosity_alpha`, `_curiosity_lean_factor`, `_curiosity_direction` (with its fall-back-to-right `try`), the `_draw` wrap, `_tick` expiry and continuation, `_on_pressed` cancellation, and `shutdown_presence` cleanup.

### `src/mochi/presence/click_dialogue.py`

Insert `ActiveWindowCuriosityMixin` immediately before `IdleLookMixin` in both `PresenceBuddy` and `PresenceX11Buddy`.

## Edge cases

| Case | Handling |
|---|---|
| Pulse during shutdown | `_presence_shutting_down` guard; `shutdown_presence()` cancels the pending source |
| Beat requested while `look` (or any non-idle visual) is playing | Not idle visual, so it falls to the cue ladder |
| Drag or typing mid-beat | Existing idle-look cancel restores idle; cooldown stays consumed |
| Tab change while watching YouTube | `WATCHING` is not allowed, so the pulse is dropped |
| Window pulse during a pending tab settle | Pending source replaced by the window debounce |
| Placement private API changed or monitor lookup fails | `_curiosity_direction` returns `+1` |
| Wall-clock change | All timing uses `time.monotonic()` |
| Extension disabled mid-session | Pulses stop; nothing pending survives shutdown |

## Testing

Run with `python3 -m pytest -q`. CI (`xvfb-run`, with GTK) is the authoritative gate.

1. **Signals** (`tests/test_presence_engine.py`, `tests/test_helper_lifecycle.py`, `tests/test_helper_dbus_integration.py`): a tab pulse invokes `on_tab_changed`; subscription counts include `BrowserTabChanged`; the adapter works with no tab callback.
2. **Reaction ladder** (`tests/test_active_window_curiosity.py`):
   - idle gives a beat;
   - a second trigger inside the beat cooldown, but past the cue cooldown, gives a cue;
   - inside the cue cooldown gives a drop;
   - `TYPING` gives a cue;
   - suppressed gives nothing;
   - a beat resets the shared 20 s gap;
   - an idle trigger within 20 s of a cue gives a drop, not a beat.
3. **Settle and debounce:**
   - N tab pulses inside 1.5 s produce one scheduled reaction;
   - a window pulse replaces a pending tab settle;
   - a press cancels the pending source and clears the cue;
   - shutdown cancels the pending source.
4. **Idle beats** (existing idle-look tests plus new ones):
   - all existing idle-look tests pass unchanged;
   - when the `investigate` beat finishes, idle resumes at the saved frame and elapsed time;
   - a typing start during the beat restores idle;
   - `_play_animation("other")` during the beat restores idle;
   - the look timer firing mid-beat reschedules.
5. **Sprite:** `ANIMATIONS["investigate"].looping is False` and its frames equal `ANIMATIONS["searching"].frames`.
6. **Extension** (source-text assertions, the same style as `tests/test_gnome_shortcuts.py`):
   - the title handler is connected only for browser-classified windows;
   - `compute_checksum_for_string` with SHA256 is used;
   - the badge-strip pattern is present;
   - `BrowserTabChanged` is emitted through `_emitSignal`, with no title variable passed;
   - the handler is disconnected in `disable()`.
7. **Draw:** a cue render differs from the baseline; an expired cue clears without changing behavior state.

## Documentation

- `CHANGELOG.md` Unreleased → Added: one entry replacing PR #133's.
- `gnome-extension/mochi-typing@miflow13/README.md`: list `AppFocusChanged` and `BrowserTabChanged`, plus the digest and timing-only privacy statement.
- `docs/ambisense.md`: the same signal and privacy notes.
- `REGRESSION_WATCHLIST.md` → Contextual Presence:
  - [ ] Flicking through browser tabs produces one curiosity reaction after settling, not one per tab
  - [ ] An unread-badge title change (`(3)` → `(4)`) does not trigger curiosity
  - [ ] Investigate beat returns to idle without a visible frame jump
  - [ ] Dragging Mochi mid-investigate recovers cleanly
  - [ ] Quiet mode / ambient reactions off suppress all curiosity

## Delivery

- Branch: `claude/optimistic-volta-9jc07e`. Merge `origin/feat/active-window-curiosity` into it, preserving PR #133's commits, and resolve the `CHANGELOG.md` conflict. Then implement this design on top.
- Open a new draft PR. The owner closes #133 as superseded.
- Live verification on Fedora / GNOME / Wayland (XWayland) by the owner before merge.

## Risks

- **Title churn the badge filter misses.** Some sites rewrite titles on a timer, such as chat apps or "● Recording". This is mitigated by the 1.5 s settle and the 20 s / 120 s cooldowns, and the constants are tunable in one place. Per-pattern filtering is deferred unless live testing shows a need.
- **Mutter `notify::title` semantics.** Duplicate notifications for identical titles are harmless, because the digest comparison drops them.
- **`_curiosity_direction` relies on private placement helpers** (`_monitor_for_position`, `_x11_coordinate_scale`). This is guarded by the existing `try` fallback.
