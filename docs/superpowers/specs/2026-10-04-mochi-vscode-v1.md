# Mochi VS Code v1 design

Approved scope: standalone sidebar companion, canonical art, idle/blink, pet reaction, directional dragging, sleep/wake, optional typing reactions, persistent preferences, reduced motion, and an installable VSIX. Mika authorized implementation with “I approve all”.

## Architecture
Create `extensions/mochi-vscode/` as an independent Node/CommonJS extension with a Canvas webview and no runtime npm dependencies. JavaScript with JSDoc keeps the first release small and directly runnable; VS Code hosts extension APIs, and plain browser modules render the pet. This desktop VS Code release does not claim vscode.dev support.

An extension host owns settings, commands, persisted sleep and normalized placement, and privacy-safe typing notifications. The webview owns animation and pointer gestures. A pure model owns semantic state and entry/loop/exit recovery; direct input outranks typing and idle. The sidebar stays within supported VS Code UI.

## Canonical artwork contract
Source: `artist-kit/README.md`, `assets/mochi/master/mochi_default.png`, `assets/mochi/manifest.json`, `src/mochi/sprites.py`, `src/mochi/interaction_tuning.py`, at initial commit 398ff2dc4dafe716640c3b1a405f8e57563d8651.
Build copies the exact runtime PNG bytes into the packaged extension. No redraw, recolor, resampling, or alternate recovery-repository art. The generated manifest retains source frame order, source cell sizes, spritesheet strips, and loop flags. Use desktop per-frame timing overrides for idle, blink, bounce, squish, sleep, wake, and pickup. Dragged assets are semantic poses selected by velocity, never a sequential loop.

Canvas uses nearest-neighbor rendering, bottom-center placement, and HiDPI backing scale. Sprite alpha is used for pointer hit testing to avoid grabbing transparent padding. One-shot completion returns to idle or current valid typing; sleep enters sleeping and wake returns to idle.

## v1 behavior
- “Mochi: Show”, “Pet”, “Sleep / Wake”, and “Reset Position” commands plus sidebar buttons.
- Default idle breathing with occasional blink; click or keyboard pet action plays heart once.
- Pointer movement over 3 logical pixels begins pickup and drag. Directional soft/medium poses follow velocity (medium enter 0.22, exit 0.16; soft enter 0.10 normalized to 600 px/s). Release plays settle direction 70 ms, neutral 140 ms, then drop and idle. Cancellation always exits held state.
- Manual sleep persists across restart. Pet or drag while sleeping wakes first; explicit sleep overrides typing.
- Typing reactions default off. When enabled, user text edits in the active document send only an activity timestamp, never code, text, filenames, paths, or keystrokes. Typing intro → loop → outro; four seconds without activity ends typing. Commands, drag and pet reactions interrupt typing; ambient events cannot steal direct interaction.
- Persist normalized placement and manual sleep in VS Code globalState. Clamp on resize. Never persist transient drag/one-shot state. Settings: size (96–256, default 160), typingReactions (false), reducedMotion (false). System reduced-motion preference also applies.
- Reduced motion uses static state poses, while buttons, dragging and sleep controls remain functional.
- Pause all drawing callbacks when hidden; restore when visible without catch-up bursts. Dispose subscriptions cleanly. Save placement only at completed drag/reset; validate incoming messages.

## Security and UX
Local assets only via asWebviewUri and constrained localResourceRoots. Strict CSP; no inline scripts, eval, network or workspace access. Theme-aware chrome, readable focus outlines, native button keyboard navigation, labeled controls and polite status text. Sidebar narrow/short layouts scroll chrome as needed while pet stays inside its stage.

## Delivery
Source, build scripts, tests, manual QA checklist, install documentation, and VSIX CI artifact. No Marketplace publishing, desktop bridge, speech, AI provider, focus timer, bond economy, or desktop runtime modifications.

## Verification
Unit tests for animation timing/recovery, priority, drag reversal and cancellation, malformed persisted state/messages, typing privacy/throttle, resource restrictions, and host teardown. Build validates canonical asset presence, dimensions and runtime overrides. Browser smoke checks real PNG rendering, alpha hit testing, pet/drag/sleep/resize/reduced motion, CSP and script errors. Package with official vsce; inspect VSIX paths and manifest. Full desktop pytest is a separate CI check because this workspace is an extension-focused materialized snapshot rather than a full GTK checkout. Live VS Code Extension Host verification remains required if VS Code is unavailable here.
