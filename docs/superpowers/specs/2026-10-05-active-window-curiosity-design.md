# Active Window Curiosity — Design

**Date:** 2026-10-05

**Builds on:** PR #133 (`feat/active-window-curiosity`), which this work supersedes

**Status:** design approved and stress-tested (2026-10-05); implemented from `docs/superpowers/plans/2026-10-05-active-window-curiosity.md`, with the changes listed under [Post-plan amendments](#post-plan-amendments-2026-10-05)

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

The cooldowns below are base values; they grow during busy sessions (see Habituation). When a trigger survives its gate, Mochi takes the first reaction that is allowed. Nothing is queued or retried.

1. **Investigate beat.** Allowed when Mochi is in his plain standing-idle visual (`_is_idle_visual_active()`), curiosity is allowed (see Suppression), at least 120 s have passed since the last beat, and at least 20 s have passed since the last reaction of either kind. Mochi plays `investigate`, a single pass of `searching` lasting about 2.4 s, then resumes idle at the saved frame and elapsed time.
2. **Overlay cue.** Allowed when curiosity is allowed, Mochi's state is one of `IDLE`, `BLINKING`, `WALKING`, `TYPING`, `COMPUTER`, and at least 20 s have passed since the last reaction of either kind. It shows a thought bubble containing a small Cairo-drawn magnifying glass for 1.8 s, plus a lean of up to 4 px toward the monitor center (lean only when Mochi is smaller than 80 px). Behavior state and animation stay untouched.
3. **Drop.**

The 20 s gap is shared: every reaction, beat or cue, resets it, so no two reactions ever land within 20 s of each other. The beat additionally has its own 120 s cooldown.

### Habituation

Like a real pet, Mochi gets used to busy browsing. `streak` counts reactions (beats and cues) since the last reset. The cooldowns are:

- shared reaction gap = `min(20 s × 1.5^streak, 120 s)`
- beat cooldown = `min(120 s × 1.5^streak, 600 s)`

A trigger is *eligible* when it survives its debounce or settle gate **and** is not suppressed (see Suppression). Suppressed triggers are dropped without touching habituation. When an eligible trigger arrives at least 300 s after the previous eligible trigger, `streak` resets to 0 before the decision. Every eligible trigger updates the last-trigger time, whether or not it produces a reaction. The cooldown calculation is one pure function of `(streak, base, cap)`, so it is trivially testable.

Effect: he is visibly curious when browsing starts, settles in over a long session (at most one cue per 2 min and one beat per 10 min), and is curious again after a 5-minute break.

### Suppression

A trigger that fires its gate while any of these hold is dropped, with no reaction and no habituation update. An active cue is cleared on the next tick while any of them hold:

- preview mode or presence shutdown
- user idle / sleeping
- context menu open, active press, or active drag
- `PresentationState` other than `NORMAL` (a level-up or emote-unlock presentation)
- Focus work or Focus "thinking": `_focus_should_work()` or `_focus_should_think()`, the same predicates that keep other presence reactions quiet during Focus (see Post-plan amendments)
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
3. If the digest equals the stored one, stop.
4. Store the new digest. This keeps the baseline current even when nothing is emitted.
5. **Input gate:** emit only if `this._idleMonitor.get_idletime()` is below `TAB_INPUT_WINDOW_MS = 2000`, meaning keyboard or pointer input happened within the last 2 s. Tab switches and link clicks always follow input. Badge updates, title blinkers and autoplay retitles happen with hands off, so they are dropped. The input gate is the primary filter and the badge strip is cheap extra protection.
6. Emit `BrowserTabChanged` through the existing zero-payload `_emitSignal()` helper.

On `disable()`: disconnect the title handler, and clear the tracked window and digest.

A focused window classified `media` (a browser on YouTube) is paused rather than tracked, and leaving YouTube for another tab in the same window sends one pulse behind the same input gate; see Post-plan amendments.

**Keep all of this inside `extension.js`.** Use two small top-level helpers, `normalizeTabTitle(title)` and `shouldEmitTabPulse(idleMs)`, with no new module file. `scripts/install-typing-extension.sh:53` copies only `metadata.json`, `extension.js` and `README.md` by name. A separate JS module would be silently left out of the install, its `import` would fail, and every AmbiSense signal would stop, not just curiosity.

Privacy properties:

- The title never leaves GNOME Shell, and it is never logged or stored by the extension. For change detection the extension keeps only a one-way SHA-256 digest of the normalized title, and only for the focused browser window. This is defense in depth, not a hard boundary: GNOME Shell already holds every raw window title, and a digest of a known title can be matched by guessing. What it guarantees is that a future debug log or state dump of the extension cannot leak a title.
- Signals are accepted only from the helper's unique bus name (`helper_connection.py` subscribes with `owner`), so another session process cannot inject `BrowserTabChanged` while the extension owns the name. This is the same trust model as every existing AmbiSense signal.
- Titles of non-browser windows are never observed.
- `BrowserTabChanged` carries no payload. It reveals only *when* the user changed tab or page.
- Like every AmbiSense signal, these pulses go over the session bus, so other processes in the user's session could observe their timing. This is documented next to the signal.

### Rejected alternatives for tab detection

- **Browser WebExtension (`tabs.onActivated`).** Exact tab events, but it needs separate Firefox and Chromium extensions with store review, a native-messaging bridge to Mochi, and it sees URLs and tab titles. That is a far larger privacy and maintenance surface than a content-free pulse.
- **AT-SPI tab-strip events.** Mochi already uses AT-SPI for typing, but tab events would expose tab names and document text inside Mochi's own process, breaking the "Mochi only sees categories" boundary. Chromium also emits them only with accessibility enabled.

The title pulse adds no installs, keeps content inside GNOME Shell, and with the input gate is accurate enough for a cosmetic, rate-limited reaction.

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
| `CURIOSITY_BEAT_COOLDOWN_SECONDS` | 120.0 (base) |
| `CURIOSITY_BEAT_COOLDOWN_CAP_SECONDS` | 600.0 |
| `CURIOSITY_CUE_COOLDOWN_SECONDS` | 20.0 (base; also the shared reaction gap) |
| `CURIOSITY_CUE_COOLDOWN_CAP_SECONDS` | 120.0 |
| `CURIOSITY_HABITUATION_FACTOR` | 1.5 |
| `CURIOSITY_HABITUATION_RESET_SECONDS` | 300.0 |
| `CURIOSITY_CUE_DURATION_SECONDS` | 1.8 |
| `CURIOSITY_LEAN_PX` | 4.0 (rounded to whole device pixels at draw time) |
| `CURIOSITY_BUBBLE_MIN_SIZE_PX` | 80 |
| `CURIOSITY_BEAT_ANIMATION` | `"investigate"` |

Changes from PR #133:

- Remove `CURIOSITY_MIN_GAP_SECONDS`, `CURIOSITY_SAME_CATEGORY_GAP_SECONDS`, `_CURIOSITY_LABELS` and the text rendering. The bubble draws a magnifying glass (circle plus handle) with Cairo.
- Replace `_curiosity_category: str | None` with `_curiosity_cue_active: bool`. Keep the category only for the debug log.
- Add `_on_presence_browser_tab_changed()`, which (re)starts the shared pending source with the settle delay.
- `_on_presence_app_focus_changed(category)` validates the category, then (re)starts the shared source with the debounce delay.
- `_react_to_curiosity()` applies the habituation reset, then the reaction ladder. It records `_curiosity_now()` timestamps for `_curiosity_last_trigger_at`, `_curiosity_last_beat_at` and `_curiosity_last_reaction_at`, and increments `_curiosity_streak` on each reaction.
- `_curiosity_now()` is the **single clock** for all curiosity timing (cooldowns, habituation, cue progress): `time.clock_gettime(time.CLOCK_BOOTTIME)`, falling back to `time.monotonic()` if `CLOCK_BOOTTIME` is unavailable. `CLOCK_MONOTONIC` stops counting during suspend, so overnight a high habituation streak would never reset and cooldowns would stretch across the sleep. `CLOCK_BOOTTIME` counts suspended time. Tests patch this one method.
- `_habituated_cooldown(base, cap, streak) -> float` is a static pure function: `min(base * FACTOR ** streak, cap)`.
- Keep `_curiosity_allowed`, `_curiosity_alpha`, `_curiosity_lean_factor`, `_curiosity_direction` (with its fall-back-to-right `try`), the `_draw` wrap, `_tick` expiry and continuation, `_on_pressed` cancellation, and `shutdown_presence` cleanup.
- **Pixel-snapped lean.** `_draw` rounds both lean offsets to whole device pixels before `context.translate`. `SpriteAtlas.draw` already rounds sprite placement (`sprites.py:158-164`) and samples with `FILTER_NEAREST`, and a fractional outer translate would make source pixels render at uneven widths, so the art shimmers during the ease. The lean therefore steps in whole pixels.
- **Small-size cue.** Below `CURIOSITY_BUBBLE_MIN_SIZE_PX = 80` (`min(width, height)`), skip the bubble and keep only the lean. At 64 px the glyph would be about 8 px and unreadable.

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
| Wall-clock change | `CLOCK_BOOTTIME` is not affected by wall-clock changes |
| Laptop suspend / resume | `CLOCK_BOOTTIME` includes suspended time, so cooldowns elapse and a long sleep resets habituation |
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
   - a beat resets the shared reaction gap;
   - an idle trigger inside the shared gap after a cue gives a drop, not a beat;
   - a suppressed trigger does not update the habituation streak or the last-trigger time;
   - habituation: `_habituated_cooldown` grows by 1.5× per streak step and clamps at the cap;
   - habituation: after several reactions the next one needs the longer gap;
   - habituation: a surviving trigger 300 s or more after the previous one resets the streak;
   - clock: `_curiosity_now()` uses `CLOCK_BOOTTIME` when available and falls back to `time.monotonic()` when it is not.
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
   - the emit is guarded by `get_idletime()` compared against `TAB_INPUT_WINDOW_MS`, and the digest is stored before that guard;
   - `BrowserTabChanged` is emitted through `_emitSignal`, with no title variable passed;
   - the handler is disconnected in `disable()`;
   - **installer guard:** every `*.js` file under `gnome-extension/mochi-typing@miflow13/` is named in `scripts/install-typing-extension.sh`'s copy step. This prevents the silent-omission trap for any future split of the extension.

   Extension *behavior* (real Mutter title notifications, idle times, D-Bus delivery) is verified by the owner's Fedora QA. No JS test runner is added.
7. **Draw:**
   - a cue render differs from the baseline;
   - an expired cue clears without changing behavior state;
   - the lean translate receives integer offsets at several progress values;
   - at 64 px no bubble pixels are drawn above the sprite region, while at 112 px they are.

## Documentation

- `CHANGELOG.md` Unreleased → Added: one entry replacing PR #133's.
- `gnome-extension/mochi-typing@miflow13/README.md`: list `AppFocusChanged` and `BrowserTabChanged`, plus the digest and timing-only privacy statement.
- `docs/ambisense.md`: the same signal and privacy notes.
- `REGRESSION_WATCHLIST.md` → Contextual Presence:
  - [ ] Flicking through browser tabs produces one curiosity reaction after settling, not one per tab
  - [ ] Title changes with hands off the keyboard and mouse (unread badges, chat title blinkers, YouTube autoplay) do not trigger curiosity
  - [ ] Investigate beat returns to idle without a visible frame jump
  - [ ] Dragging Mochi mid-investigate recovers cleanly
  - [ ] Quiet mode / ambient reactions off suppress all curiosity
  - [ ] Curiosity lean stays crisp (no pixel shimmer) and the bubble is legible at 112 px and 256 px; 64 px shows lean only

## Delivery

- Branch: `claude/optimistic-volta-9jc07e`. Merge `origin/feat/active-window-curiosity` into it, preserving PR #133's commits. Make it a **standalone merge commit**: resolve the `CHANGELOG.md` conflict by keeping `main`'s entries, and include no feature changes.
- **Green baseline before new behavior.** Run the full suite on the merge commit before implementing this design. First try installing the CI GTK4 packages in the working container and running under `xvfb-run`; if that is not possible, the first CI run on the PR is the baseline. Drift check (2026-10-05): every symbol PR #133 relies on still exists on `main`: `PresentationState`/`state.presentation`, `_on_pressed(*args)`, `_press`/`_user_idle`/`_preview_mode`, and the tuning `quiet_mode`/`ambient_reactions_enabled`. The only textual conflict is `CHANGELOG.md`.
- Open a new draft PR. The owner closes #133 as superseded.
- Live verification on Fedora / GNOME / Wayland (XWayland) by the owner before merge.

## Risks

- **Title churn without user input** (Gmail's `Inbox (12)`, chat title blinkers, YouTube autoplay). The input gate drops it at the source; the badge strip, the 1.5 s settle and the cooldowns are extra layers.
- **Slow page loads.** A click whose page takes more than 2 s to retitle is not noticed. This is accepted; `TAB_INPUT_WINDOW_MS` is one constant if live testing shows misses.
- **Mutter `notify::title` semantics.** Duplicate notifications for identical titles are harmless, because the digest comparison drops them.
- **`_curiosity_direction` relies on private placement helpers** (`_monitor_for_position`, `_x11_coordinate_scale`). This is guarded by the existing `try` fallback.

## Stress Test Results: Active Window Curiosity

### Resolved Decisions

- **Title churn without input:** resolved by adding the input gate. Tab pulses are emitted only when keyboard or pointer input happened within 2 s (Mutter idle monitor), which drops badge, blinker and autoplay retitles at the source.
- **Security and privacy:** no regression. Signals are subscribed by the helper's unique bus name (`helper_connection.py:55-61`), the new signal carries no payload, and the title regex runs in linear time. The SHA-256 digest is kept as defense in depth, and its privacy claim was reworded honestly.
- **Heavy-use frequency:** resolved with habituation. Cooldowns grow 1.5× per reaction up to 2 min (cue) and 10 min (beat), and reset after 5 min without triggers.
- **Alternative tab detection:** a browser WebExtension and AT-SPI were both rejected and recorded in the spec with reasons.
- **Rendering:** the lean is pixel-snapped to avoid nearest-neighbor shimmer, and the bubble is skipped below 80 px.
- **Extension testability:** the logic stays in `extension.js`, because the installer copies files by name, and an installer guard test was added.
- **Merge drift:** checked; every PR #133 dependency still exists on `main`. Plan: a standalone merge commit, then a green full-suite baseline before new behavior.
- **Suspend (found during reflexion):** all curiosity timing goes through `_curiosity_now()` on `CLOCK_BOOTTIME`.
- **Resolved from code without a decision:** Ctrl+Tab does not enter `TYPING` (`typing_activity.py:21` needs 5 events within 1.25 s), so keyboard tab switching can still produce the beat. `investigate` reuses `searching` frames, which are already packaged (`pyproject.toml:62`).

### Changes Made

- Extension: input gate (`TAB_INPUT_WINDOW_MS = 2000`); digest stored before the gate; helpers kept inside `extension.js`.
- Behavior: habituation section and constants.
- Architecture: `_habituated_cooldown`, `_curiosity_now` (`CLOCK_BOOTTIME`), pixel-snapped lean, `CURIOSITY_BUBBLE_MIN_SIZE_PX = 80`.
- Privacy wording now describes the digest accurately and documents sender filtering.
- Rejected-alternatives section added.
- Tests added: input-gate ordering, installer guard, habituation (×3), clock fallback, integer lean, small-size bubble.
- Watchlist: hands-off title changes, crispness and legibility at 64/112/256 px.
- Delivery: standalone merge commit, green baseline first.

### Deferred / Parking Lot

- Respecting GNOME's `enable-animations` (reduced motion) app-wide. The cue is decorative with no flashing, and quiet mode is today's opt-out.
- Per-site title filters, only if live QA shows the input gate letting churn through.
- Whether `TAB_INPUT_WINDOW_MS` misses slow page loads; tune after Fedora testing.
- Broader installer robustness (copying `*.js` instead of named files) is out of scope; the guard test covers the risk.

### Confidence Assessment

- Overall: **High** for the Mochi-side design (it reuses the tested idle-look lifecycle and adds no behavior state); **Medium** for the extension's tab detection, because real Mutter `notify::title` timing and browser title behavior can only be verified live on Fedora.
- Areas of concern: input-gate tuning against real browsing; visual feel of the beat and cue, which needs owner QA.

## Post-plan amendments (2026-10-05)

Changes made during implementation and review, after the plan was written. Where this section and the text above disagree, this section wins.

- **YouTube exit pulse and broadened media pause (extension).** Any focused window the helper classifies `media` (a browser on YouTube) becomes the paused window: only its reference is kept, and its title is never read for tab tracking. When that same window returns to `browser` (the user left YouTube for another tab), the helper takes a fresh baseline digest and emits `BrowserTabChanged` behind the same 2 s input gate. Another window becoming the target is a window switch, which `AppFocusChanged` already covers. The pause starts immediately when focus lands on a window already on YouTube; a tracked window that navigates to YouTube is reclassified on the next 1 s heartbeat, and until then its title changes are handled like any other.
- **Focus suppression.** Focus is not a `PresentationState`: Focus work runs as `MochiState.COMPUTER`, a cue-allowed state. `_curiosity_allowed()` therefore also returns false while `_focus_should_work()` or `_focus_should_think()` is true, the predicates `FocusSessionMixin._focus_allows_presence_action` uses for other presence reactions. The same check gates the cue's per-tick continuation, so an active cue clears once Focus starts. Breaks and paused sessions follow the normal rules.
- **Streak exponent clamp.** `_habituated_cooldown` uses `min(max(0, streak), 16)` as the exponent. `1.5 ** 16` is far past both caps, so results are unchanged, but a very long streak can no longer overflow the float power.
- **Docs precision.** The extension README and `docs/ambisense.md` say exactly when the YouTube pause starts, and that unread counters and autoplay are ignored only when they retitle the page while the user is hands-off. The adapter docstrings describe all three helper signals and no longer call the tab pulse "settled"; the settle belongs to curiosity. Both base hooks in `integration.py` are docstring-only and the adapter logs each pulse once, superseding "a base hook that only logs at debug level" above.
