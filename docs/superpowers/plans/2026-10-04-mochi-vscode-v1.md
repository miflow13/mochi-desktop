# Mochi VS Code v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Ship the approved standalone Mochi sidebar v1 on feat/mochi-vscode-v1.

**Architecture:** Dependency-free CommonJS extension host and Canvas webview. A pure browser/CommonJS model owns animation transitions and gesture state. Build derives an asset subset from the desktop manifest and timing overrides; packaged PNGs are byte-identical to the source.

**Tech Stack:** Node.js 22+ for development/tests, JavaScript/JSDoc, VS Code >=1.90, Canvas, official @vscode/vsce 4.0.0 for packaging.

**Spec:** docs/superpowers/specs/2026-10-04-mochi-vscode-v1.md

## Global Constraints
- No desktop runtime changes or artwork changes.
- No runtime npm dependencies; no workspace content in activity messages.
- Typing reactions default off; size 96–256/default 160; reduced motion default false and respect system preference.
- Same source FPS, per-frame runtime overrides, PNG bytes, cell sizes and bottom-center anchor.
- Hidden webviews stop drawing; direct interaction outranks ambient behavior.
- No speech, network, desktop IPC, publishing or merge.

## Review Focus
- Pointer cancellation/lost capture must recover rather than persist dragged.
- Late messages and hidden-view timestamps must not steal sleep or user interaction.
- Malformed persisted placement must reset to finite normalized coordinates.
- Missing/mismatched PNG dimensions must fail build clearly rather than ship broken artwork.
- Theme/HiDPI/short sidebar and reduced motion must leave controls readable and usable.

### Task 1: Canonical assets and animation model
**Files:** scripts/build-assets.js, media/model.js, test/model.test.js, test/assets.test.js, package.json.
**Interfaces:** model exports sanitizeState(raw), clampPosition(position), dragPose(velocity, previous), frameAt(animation, elapsed), Companion(manifest, state) with pet/sleep/toggleSleep/activity/beginDrag/drag/endDrag/tick/snapshot. Build emits media/mochi/manifest.json with durations_ms and exact PNG copies.
- [x] Write failing node:test cases for timings, one-shots, sleep/wake, typing priority, directional drag/cancellation, invalid state and spritesheet indexing.
- [x] Run node --test test/model.test.js; expect missing behavior failures before implementation.
- [x] Implement model and build asset subset/overrides; verify PNG signature/IHDR dimensions and presence.
- [x] Run npm test and npm run build; expect green and byte-identical asset checks.

### Task 2: Extension host and webview integration
**Files:** src/extension.js, src/webview.js, media/main.js, media/style.css, test/host.test.js, test/webview.test.js, media/mochi-icon.svg.
**Interfaces:** activate(context, injectedApi?) registers Mochi view/commands, sends init/settings/action/activity messages, receives ready/state messages; renderWebview(webview, extensionUri) returns CSP-protected HTML.
- [x] Write failing host tests for message validation, local resources, typing opt-in/privacy, globalState save and disposal.
- [x] Run npm test; expect missing host/render failures.
- [x] Implement view provider, settings, commands and normalized state persistence.
- [x] Implement Canvas rendering, alpha hit testing, pointer gestures, controls, visibility lifecycle and accessibility against model from Task 1.
- [x] Run npm test including real-PNG Canvas interaction tests for pet/drag/cancel/sleep and lifecycle. Browser smoke is implemented but could not run locally: browser installation/launch failed; CI performs it.

### Task 3: Packaging and review
**Files:** README.md, MANUAL-QA.md, .vscodeignore, .github/workflows/vscode-extension.yml, extension LICENSE, docs/spec/plan, CHANGELOG.md.
**Interfaces:** npm run build derives assets; npm run check checks JS syntax; npm run package calls vsce package --no-dependencies; workflow uploads VSIX after tests/build/package.
- [x] Build/check/package and all 23 extension tests pass. Real Chromium verification passes in CI. Live Extension Host verification remains pending as documented in the verification record.
- [x] Package with official vsce, inspect archive for entrypoint and all referenced assets, exclude tests/source authoring material.
- [x] Request fresh branch review; address material findings with failing regression tests first.
- [x] Commit only extension source, CI and documentation to approved GitHub branch; do not merge or publish.
