# Pocket Hover Tray — Design

**Date:** 2026-10-06

**Builds on:** the Mochi Pocket prototype (`docs/superpowers/specs/2026-09-27-mochi-pocket-prototype-design.md`), which explicitly left "dragging Pocket items back out to other applications" out of scope

**Design canvas:** https://claude.ai/artifact/EEcdHQWgSR5BWenQzMoRDJ (playable prototype, timeline, tray anatomy)

**Status:** design approved (2026-10-06); implemented from `docs/superpowers/plans/2026-10-06-pocket-hover-tray.md`, with the changes listed under [Post-plan amendments](#post-plan-amendments-2026-10-06)

## Purpose

Putting things *into* Mochi's Pocket is one gesture: drag onto him. Getting them back out takes four: right-click, choose `Pocket · N`, find the row in a separate window, press Open. This design makes the way out as easy as the way in.

> Rest the pointer on Mochi for two seconds. A small tray comes out of his mouth. Click a row to use it, or drag it straight into another app.

The character stays the interface: the tray is presented by Mochi's own mouth animation, and he goes back to whatever he was doing.

## Goals

- Open a Pocket tray by resting the pointer on Mochi, with no click.
- Show progress during the wait, so the gesture is learnable and easy to abandon.
- Never open anything when the pointer merely passes over Mochi, or when Mochi walks under a resting pointer.
- From the tray: open, copy, show in folder, view text, and drag an item into another application.
- Keep the existing Pocket window for management (remove, clear all), one click away from the tray.
- Let the user change the dwell or turn it off.
- Keep a keyboard path: the context menu's `Pocket · N` opens the same tray with keyboard focus.

## Non-goals

- Removing an item when it is grabbed. Grabbing leaves the item in the Pocket; the 10-item cap already ages things out (decision 2026-10-06).
- Remove or Clear All inside the tray. Those stay in the Pocket window.
- Changing the hover heart, its timing, or the fact that hovering wakes a sleeping Mochi.
- Eye-follow. That is a separate design: `docs/superpowers/specs/2026-10-06-eye-follow-design.md`.
- The hover tray on the opt-in native Wayland layer-shell path. That path has no X11 root coordinates to anchor a tray, so it keeps today's behavior (the menu row opens the Pocket window).
- New sound or new art. The mouth animation reuses `pocket_grab` frames.
- Thumbnails or previews of file contents.

## Behavior

### Timeline (default 2 s dwell)

| Time after the first pointer motion on Mochi | What happens |
|---|---|
| 0 ms | Nothing new. The cursor is already a hand (existing). |
| 280 ms | The existing hover heart, unchanged. |
| 600 ms | A small "peek" bar appears just above Mochi: the Pocket icon, `Pocket · N`, and a progress bar that fills over the remaining dwell. |
| dwell (2000 ms) | The peek becomes the tray. Mochi plays `pocket_offer` (his mouth opens and closes) when his current state allows it. |

The dwell is configurable: Off, 1.5 s, 2 s (default), or 3 s. The peek always appears 600 ms after arming, so with 1.5 s the bar fills for 900 ms.

### Arming

The dwell **arms on the first pointer motion inside Mochi's window**, not on enter. A window moving under a resting pointer is not the user reaching for Mochi.

It arms only when all of these hold:

- the dwell setting is not Off;
- the Pocket holds at least one item;
- `behavior.can_arm_pocket_hover(state)` is true. The allowed states are `IDLE`, `BLINKING`, `IDLE_EMOTE`, `HEART`, `COMPUTER`, `TYPING`, `WATCHING`, `DANCING`, `SEARCHING`, `SLEEPING` and `WAKING`. `WALKING`, `EXCITED`, click reactions (`BOUNCING`, `SQUISHING`), `EATING`, `PICKUP`, `DRAGGED`, `DROPPING` and `FEDORA` keep ownership;
- presentation state is `NORMAL` (no level-up or emote-unlock presentation);
- the context menu is closed, there is no active press or drag on Mochi, and no Pocket drag-in or receive is in progress;
- the Pocket window is not already visible;
- Mochi's speech bubble is not on screen (see [Speech and the tray](#speech-and-the-tray));
- Mochi is not in preview mode and not on the layer-shell path;
- the pointer has left Mochi since the tray last opened or closed (the re-arm rule below).

All of these are checked again when the peek is due and when the tray is due. If any fails, arming resets silently.

**Sleeping.** Hovering already wakes a sleeping Mochi today (`Buddy._on_enter` → `_mark_interaction` → `_on_user_active`). That stays. `SLEEPING` and `WAKING` are arm-allowed so the tray is never held hostage by the wake animation. In those states the tray opens without the mouth animation.

> This corrects the canvas sticky "he stays asleep": the code wakes him on hover, and changing that is out of scope.

### Cancelling

Every cancel is silent: nothing opens, nothing is written, no speech.

- **Pointer leaves Mochi before the dwell ends:** the peek hides and arming resets.
- **Primary press, right-click, or drag on Mochi:** arming resets. If a hover-opened tray is open, it closes. The dwell will not re-arm until the pointer leaves Mochi and comes back.
- **State or condition change mid-dwell** (he starts walking, a drag-in begins, the menu opens): caught at the next due check, and arming resets.

### Re-arm rule

After the tray opens or closes while the pointer is still on Mochi, the dwell does not re-arm until the pointer leaves Mochi. Without this rule, closing the tray with the pointer resting on him would reopen it two seconds later.

### The tray

The tray is one undecorated, transient, keep-above window anchored to Mochi:

- **Placement:** centred horizontally on Mochi, 8 px above him. If there is no room above on his monitor, it goes 8 px below him. It is clamped 12 px inside the nearest monitor, using the same monitor and scale handling as `MenuWindow`.
- **Header:** `Pocket` and `N of 10`.
- **Rows:** newest first, at most 10 (the Pocket capacity). Each row shows the type icon, title, and subtitle from the existing `pocket_window.row_model()`, so the tray and window never disagree. The list scrolls past 480 px.
- **Footer:** a `Manage Pocket…` button that closes the tray and opens the existing Pocket window.
- **Empty state** (reachable only from the menu, since hover never arms on an empty Pocket): "Nothing in here yet. Drag a file, link, image, or text onto Mochi."

#### What each kind does

| Kind | Click (primary) | Quick action (icon button) | Drag out |
|---|---|---|---|
| Local file or folder | Open with the default app | Show in folder | The file itself (`GdkFileList`) |
| URL | Open in the default browser | Copy link | The URL (`text/uri-list` plus plain text) |
| Text | **Copy** to the clipboard | View all (existing read-only text window) | The text |
| Saved image | Open with the default app | Copy image | The managed PNG file (`GdkFileList`) |
| Missing file | Disabled | None | Not draggable |

Text copies on click because pasting it somewhere is why you grab text.

The primary verb ("Open" or "Copy") and the quick action appear when a row is hovered or keyboard-focused. The whole row is the click target and the drag handle.

#### After an action

- **Primary action succeeds:** the tray closes. A text copy also shows nameplate feedback, "Copied". Opens show nothing, because the app opening is the feedback.
- **Quick action succeeds:** the tray stays open. Copy actions show an inline "Copied" on that row for 1.5 s. View all opens the read-only text window, which takes focus, so the tray then closes by the focus rule below.
- **Any action fails** (launch error, a missing file, an unreadable image): the tray stays open and the row shows "Couldn't open it. It's still here." The item is never removed as a side effect.
- **Drag delivered:** the tray closes.
- **Drag cancelled or refused:** the tray stays open.

Dropping a tray item back onto Mochi is refused. `PocketDropAdapter` ignores drags that originate inside Mochi's own process, so it never re-adds or reacts.

### Closing

| How the tray was opened | Closes when |
|---|---|
| Hover | The pointer has been outside both Mochi and the tray for 450 ms (enough to cross the 8 px gap), a primary action or delivered drag, Esc after the tray was clicked, a press or right-click on Mochi, `Manage Pocket…`, or the tray losing focus after it was clicked |
| Context menu (`Pocket · N`) | Esc, focus loss (a click elsewhere), a primary action or delivered drag, `Manage Pocket…`, a press or right-click on Mochi. Pointer movement alone never closes it. |

The tray never closes while a drag from it is in progress. Unmapping the source window would cancel the drag.

### Focus

- **Hover-opened:** the tray must not take keyboard focus, because the user may be typing in another app. Before mapping, the tray sets `_NET_WM_USER_TIME` to 0 through `GdkX11.X11Surface.set_user_time(0)`, which asks an EWMH window manager not to focus it on map. This is a strong hypothesis for Mutter on XWayland, and it is a manual QA item.
- **Menu-opened:** the tray is presented normally and focus lands on the first row. ↑ and ↓ move between rows, Enter runs the primary action, Tab reaches the quick action, and Esc closes.

### Speech and the tray

The tray and Mochi's speech bubble both live just above (or below) him, so they never share the space:

- **While Mochi is speaking, the dwell does not arm.** Resting the pointer on a talking Mochi is how you read him; the menu path still opens the tray.
- **While the peek or tray is on screen, ambient speech waits,** exactly as it waits for a press or a drag. `PocketBuddyMixin` extends the new `PresenceBuddyMixin._presence_interaction_active()` seam that feeds `AmbientContext.interaction_active`. The Pocket code never calls the bubble; it only reads `presence_speech_visible()`.

### The context-menu row

`Pocket · N` now opens the tray (menu-opened, focused) instead of the Pocket window. The Pocket window is one click further, through `Manage Pocket…`. On the layer-shell path the row still opens the Pocket window directly.

### Settings

The Pocket window gains one row under its subtitle: **Open by resting on Mochi** with a dropdown of `Off`, `1.5 s`, `2 s` and `3 s`.

- Stored in `config.json` as `pocket_hover_delay_ms`: one of `0`, `1500`, `2000`, `3000`, where `0` means Off.
- Missing or invalid values read as `2000`.
- A change applies to the next arming. A dwell already counting checks the setting at its next due point.

## Character and state ownership

Opening the tray is direct user interaction, but it is presentation only. It never introduces a new behavior state.

`PocketController.begin_offer()` follows the existing receive pattern:

1. If `behavior.can_start_pocket_offer(state)` is false, return `False`. The offer states are `POCKET_RECEIVE_STATES` plus `HEART`. The hover heart (1.92 s, starting at 0.28 s) is usually still playing when a 2 s dwell completes, so the offer must be able to replace it.
2. Cancel a walk, or cancel the ambient emote (which includes `HEART`).
3. `_transition_to(EXCITED)`. If that is rejected, log a warning and return `False`.
4. Mark the interaction and play `pocket_offer` (`pocket_grab` frames 4 → 8, 120 ms each, one-shot, `next_state="idle"`). The normal one-shot completion returns Mochi to `IDLE`.

The tray opens whether or not the offer animation was allowed.

For about 0.6 s while the offer plays, Mochi is `EXCITED`, so a simultaneous Pocket drag-in gets the existing "My paws are full". That is acceptable.

## Architecture

```text
Buddy motion/press handlers (super() chain)
        │ pointer_entered / pointer_moved / pointer_left / interrupt
        ▼
PocketHoverDwell (pocket_hover.py, GTK-free)
        │ show_peek / hide_peek / open_tray(focus) / close_tray
        ▼
PocketBuddyMixin (pocket_integration.py, composition only)
        │                                   │
        ▼                                   ▼
PocketController.begin_offer()        PocketTray (pocket_tray.py, GTK)
  behavior guard → EXCITED →            peek view ↔ tray view, rows,
  pocket_offer                          drag sources, clipboard, keys
                                              │ tray_entered / tray_left /
                                              │ drag_started / drag_finished / close
                                              ▼
                                        PocketHoverDwell
```

### `src/mochi/behavior.py`

Adds `POCKET_HOVER_ARM_STATES`, `can_arm_pocket_hover()`, `POCKET_OFFER_STATES` and `can_start_pocket_offer()`. These are the only priority tables for this feature (Manual rule 3). `can_transition()` is unchanged: the offer cancels `HEART` before requesting `EXCITED`.

### `src/mochi/sprites.py`

Adds `ANIMATIONS["pocket_offer"]`, derived from `pocket_grab`, next to `pocket_hover` and `pocket_finish`. There are no new frames, so the manifest and packaging are unchanged.

### `src/mochi/pocket_controller.py`

Adds `begin_offer() -> bool`, described above.

### `src/mochi/pocket_hover.py` (new, GTK-free)

- Constants: `POCKET_HOVER_DELAY_CHOICES_MS = (0, 1500, 2000, 3000)`, `DEFAULT_POCKET_HOVER_DELAY_MS = 2000`, `POCKET_PEEK_DELAY_MS = 600`, `POCKET_TRAY_CLOSE_GRACE_MS = 450`.
- `normalize_hover_delay_ms(value) -> int`.
- `DwellPhase`: `IDLE`, `ARMED`, `PEEK`, `OPEN`.
- `PocketHoverDwell`: the arming, peek, open, close, re-arm and drag rules above, as one small state machine. Its collaborators are injected callables, and GLib's `timeout_add`/`source_remove` are injectable, so every rule is unit-tested without a display. It owns three timers (peek, open, close), and `shutdown()` cancels them all.

### `src/mochi/pocket_actions.py` (new, GTK-free)

- `launch_uri_for(item)`: the only URI Pocket hands to the desktop for an item. URL items use their validated HTTP(S) value; files and saved images use `Path.as_uri()`; text raises `ValueError`.
- `folder_uri_for(item)`: the parent folder of a local file.

`PocketWindow.open_item()` and `open_containing_folder()` switch to these helpers with no behavior change, so the window and the tray cannot drift on what they launch.

### `src/mochi/pocket_tray.py` (new, GTK)

- `tray_position_for_anchor(...)`: a pure placement function with the same unit conventions as `menu_position_for_anchor`.
- `TrayRowModel` and `tray_row_model(item)`: built on `row_model(item)`, adding the primary and quick-action labels.
- `drag_content_for(item)` and `clipboard_content_for(item)`: `Gdk.ContentProvider` builders.
- `PocketTray`: owns the window, the peek and tray views, the rows, drag sources, inline feedback, keyboard handling, the no-focus present, positioning, and any text detail windows it opened. Every source it creates is stored and removed in `close()` or `destroy()` (Manual rule 4).

### `src/mochi/x11.py`

Adds `request_no_focus_on_map(window) -> bool`, next to `request_keep_above`.

### `src/mochi/pocket_integration.py`

Composition only, as it is today. It:

- builds the dwell and lazily builds the tray;
- extends `_on_enter`, `_on_leave`, `_on_motion`, `_on_pressed` and `_on_context_pressed` with a `super()` call first or last, as the plan specifies;
- provides `can_arm`;
- calls `begin_offer()` when the tray opens;
- routes `Pocket · N` to the menu-opened tray;
- refreshes an open tray when items change;
- owns the hover-delay setting;
- tears down the dwell, then the tray, in `shutdown_presence()`.

### `src/mochi/pocket_drop.py`

Ignores in-process drags. `Gtk.DropTarget.get_current_drop().get_drag()` is non-`None` only for drags that started in this application.

### `src/mochi/config.py`

Adds `load_pocket_hover_delay_ms()` and `save_pocket_hover_delay_ms()`.

### `src/mochi/pocket_window.py`

Adds the setting row, and adds `hover_delay_ms` and `on_hover_delay_changed` constructor parameters. It uses `pocket_actions` for URIs.

## Privacy and safety

- No new data leaves Mochi. No network. The pointer position is never stored; the dwell sees only enter, motion and leave events inside Mochi's own window.
- The clipboard is written only on an explicit click, and never read.
- Launching is unchanged: `Gio.AppInfo.launch_default_for_uri` with a URI from `launch_uri_for`. There is no shell and no command strings, and only previously validated HTTP(S) URLs are launched as URLs.
- Drag-out offers only `COPY`. Mochi never deletes or moves the original. Saved images are offered as their managed PNG path.
- Text is never interpreted as markup. Tray labels use `set_text`/`label=`, never `set_markup`.
- No speech is added. The only feedback is the existing Pocket nameplate path ("Copied") and inline row text.

## Accessibility

- Hover is never the only way in. The context-menu path opens the same tray with focus and full keyboard support.
- The dwell can be turned off.
- Every icon-only quick action has an accessible label and a tooltip.
- Rows are `Gtk.ListBoxRow`s, so screen readers announce a list, and arrow keys and Enter work.
- Targets are at least 44 × 44 px (quick action buttons) and rows are at least 56 px tall.
- Colors come from the GTK theme (`@theme_bg_color`, `@theme_fg_color`), so the tray follows light and dark. The mint accent reuses the existing Pocket primary pair (`#79c98b` on `#102417`).

## Failure and edge cases

| Case | Result |
|---|---|
| Pocket emptied while armed | The next due check fails `can_arm`; arming resets |
| Item removed in the Pocket window while the tray is open | `_on_pocket_changed` refreshes the tray rows |
| Mochi dragged while the tray is open | A press calls `interrupt()`, which closes a hover tray; a menu-opened tray also closes |
| Mochi walks under a resting pointer | No motion inside the window, so no arming. `WALKING` is not arm-allowed either |
| Tray would go off-screen | Flips below Mochi, then clamps to the monitor |
| Mochi on a second monitor | The nearest monitor to Mochi's centre is chosen |
| Shutdown while the peek or tray is showing | `shutdown_presence()` → `dwell.shutdown()` (timers cancelled) → `tray.destroy()` |
| Drag started, then Mochi's tray is asked to close by a grace timer | Suppressed while dragging |
| `begin_offer()` rejected | The tray still opens; Mochi stays in his current presentation |
| Image copy of a missing PNG | `GLib.Error` is caught; inline error; tray stays open |

## Testing strategy

All tests run headless under `xvfb-run`, like the existing Pocket tests.

- **`tests/test_pocket_controller.py`:**
  - arm-state and offer-state tables (parametrized over every `MochiState`);
  - `begin_offer()` cancelling `HEART` before `EXCITED`;
  - rejection in protected states;
  - no offer while `busy` or `hover_active`.
- **`tests/test_sprites.py`:** `pocket_offer` frames 4–8, 120 ms, one-shot, `next_state == "idle"`.
- **`tests/test_pocket_hover.py` (new), with a fake scheduler:**
  - motion arms but enter alone does not;
  - peek at 600 ms with the correct fill;
  - open at the dwell;
  - leave before the dwell resets;
  - each `can_arm` failure point;
  - Off;
  - empty;
  - the re-arm rule;
  - interrupt;
  - grace close;
  - the tray hover keeps the tray open;
  - drag suppresses close;
  - delivered and cancelled drags;
  - a pinned (menu) tray ignores pointer leave;
  - the setting changed mid-dwell;
  - failed open;
  - shutdown cancels all timers;
  - `normalize_hover_delay_ms`.
- **`tests/test_pocket_actions.py` (new):** URIs for every kind, text rejection, and the folder URI.
- **`tests/test_pocket_tray.py` (new):**
  - placement (above, flip below, clamp, scale, nearest monitor);
  - row models for every kind, including missing;
  - drag and clipboard provider formats;
  - peek and tray views;
  - a primary action per kind, including closing and feedback;
  - a quick action per kind, including staying open and the inline confirmation;
  - launch failure keeps the tray open and shows the inline error;
  - missing rows are insensitive with no drag source;
  - Esc closes;
  - the no-focus path calls `request_no_focus_on_map`;
  - `destroy()` removes timers and detail windows;
  - empty state;
  - `Manage Pocket…`.
- **`tests/test_pocket_integration.py`:**
  - the motion handlers forward to the dwell;
  - press and right-click interrupt;
  - `can_arm` covers each condition;
  - the menu row opens the pinned tray, with the layer-shell fallback to the window;
  - `begin_offer` is called on open;
  - item changes refresh an open tray;
  - shutdown order;
  - the setting is loaded, saved, and passed to the Pocket window.
- **`tests/test_pocket_drop.py`:** an in-process drag is ignored on enter, motion and drop.
- **`tests/test_config.py`:** delay load and save, with invalid values normalized.
- **`tests/test_pocket_window.py`:**
  - the setting dropdown reflects the stored value and reports changes;
  - existing open behavior unchanged.

## Manual Fedora/GNOME verification

Automated tests cannot prove pointer feel, focus behavior, or cross-application drag-and-drop. The maintainer checks:

1. Pointer passes over Mochi without stopping: the heart may play; no peek; no tray.
2. Rest on Mochi: the peek appears at about 0.6 s and fills; the tray opens at 2 s with the mouth animation.
3. Leave at 1 s: the peek disappears; nothing else happens.
4. Typing in a text editor while the hover tray opens: keystrokes still go to the editor (no focus steal).
5. Move from Mochi into the tray and back: it stays open. Move away: it closes after about half a second.
6. Close the tray with the pointer still on Mochi: it does not reopen until you leave and come back.
7. Mochi walks under a resting pointer: no tray.
8. Sleeping Mochi: hovering wakes him (existing) and the tray still opens at 2 s, without the mouth animation if he is mid-wake.
9. For each kind: click, then quick action, then drag into GNOME Files, a browser text field, a text editor, and a chat or upload field.
10. Drag a tray item back onto Mochi: refused, with no reaction.
11. Right-click → `Pocket · N`: the tray opens focused. Check ↑, ↓, Enter, Tab and Esc. Click elsewhere and it closes.
12. `Manage Pocket…` opens the window. Set "Open by resting on Mochi" to Off, then 3 s, and confirm; restart Mochi and confirm the setting persists.
13. Mochi near the top edge: the tray flips below. Near a side edge: it clamps. On a second monitor: it stays on Mochi's monitor.
14. Light and dark GNOME styles.
15. Repeat 2 and 9 on the normal GNOME/XWayland path. Confirm the native Wayland layer-shell path keeps the menu → window behavior.

Manual results are reported separately from unit-test results.

## Documentation

- **`CHANGELOG.md` (Unreleased):** Added (hover tray, drag-out, setting) and Changed (`Pocket · N` opens the tray).
- **`README.md`:** a Controls table row for "Rest the pointer on Mochi", and a "What's new" bullet.
- **`REGRESSION_WATCHLIST.md`:** Pocket section additions mirroring the manual QA list.
- **`docs/CODEBASE_MANUAL.md`:** in §11 Hover/motion, one paragraph that the Pocket dwell extends the motion handlers through `super()` and never changes the hover heart.

## Decisions (2026-10-06)

- Grabbing leaves the item in the Pocket.
- The default dwell is 2 s, with Off / 1.5 / 2 / 3 s.
- The tray still opens for a sleeping Mochi. Hover wakes him as it does today; the original "he stays asleep" proposal was withdrawn after reading `Buddy._on_enter`.
- Eye-follow ships as a separate task after this one.
- `Pocket · N` opens the tray; management moves one click deeper.

## Risks

- **Focus steal on map** under Mutter/XWayland if `_NET_WM_USER_TIME=0` is ignored. Fallback, if QA fails: map the tray as a utility window that refuses input focus (`WM_HINTS.input = False`) through a small `x11.py` helper. That needs its own plan amendment.
- **Cross-protocol drag-out** (XWayland source to Wayland targets) depends on Mutter's XWayland DnD bridge. Drag-in already uses it in the other direction; manual QA item 9 is the evidence.
- **`EXCITED` reuse** means a drag-in during the 0.6 s offer gets "My paws are full". This is accepted for now.

## Post-plan amendments (2026-10-06)

These came from implementing the plan and driving the real app under Xvfb.

1. **Speech and the tray.** The first smoke run showed the first-run greeting bubble overlapping the peek. This added the rules in [Speech and the tray](#speech-and-the-tray), two `PresenceBuddyMixin` seams (`_presence_interaction_active`, `presence_speech_visible`), and the matching tests.
2. **Copy image.** `Gdk.ContentProvider.new_for_value(texture)` records the texture's concrete type (`GdkMemoryTexture`), which has no clipboard serializers, so other apps would have had nothing to paste. The value is now typed as `Gdk.Texture`, which offers `image/png` and other formats. The provider tests now assert the MIME types another application can actually receive.
3. **Peek bar colour.** The theme paints `progress` with a `background-image`, so the tray CSS uses the `background` shorthand to get Mochi mint.
