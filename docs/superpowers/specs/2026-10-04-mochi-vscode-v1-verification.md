# Mochi VS Code v1 verification

Implemented on `feat/mochi-vscode-v1`. Desktop runtime source and original artwork are not modified.

## Verified in this workspace
- `npm run build`: prepares 16 animations / 95 original PNG files; checks canonical dimensions, metadata, and runtime timing overrides.
- `npm test`: 23 tests pass, including real PNG decoding/Canvas rendering, alpha hit testing, directional gestures and cancellation, sleep/wake, reduced motion controls, hidden timer cleanup, privacy/opt-in, state persistence and duplicated readiness.
- `npm run check`: all JavaScript syntax checks pass.
- `npm run package`: official vsce produces a VSIX with 107 files, approximately 521 KB.
- VSIX audit: every packaged PNG is byte-identical to its canonical desktop asset; no tests or npm dependencies are packaged.
- `git diff --check`: clean.
- Independent code review found a duplicate-ready initialization race; a failing regression reproduced it before the fix. Review also identified Reset Position leaving typing active; a Canvas regression reproduced it and the behavior was corrected. An additional regression guards early visibility from announcing readiness before PNG loading completes.

## Pending verification
- Live VS Code Extension Host installation, focus, restoration and disposal: VS Code is not installed in this environment.

See `extensions/mochi-vscode/MANUAL-QA.md`. Do not treat the unchecked live-host cases as passed. No Marketplace publishing or merge has been performed.

## Implementation choices
- Plain JavaScript with JSDoc-friendly module boundaries avoids a compilation/bundling layer for v1. The code has no runtime npm dependencies.
- Canonical generated assets are built from the repository source, rather than committing a second artwork tree.
- Typing reactions default off and carry only an activity event, not document content or filenames.

## GitHub Actions verification
- [Extension CI run 37205386247](https://github.com/miflow13/mochi-desktop/actions/runs/37205386247) passed build, all 23 tests, syntax checks, real Chromium smoke, official VSIX packaging and artifact upload.
- Chromium exercised the actual HTML/CSP and original PNG rendering, petting, sleep/wake, left/right drag, persisted placement, narrow viewport, keyboard actions and reduced motion without page errors.
- Browser CI first exposed a resource URL bug in the harness adapter and then an edge-pixel pointer mapping bug when CSS canvas size differs from backing dimensions. Failing regressions pin both fixes; pointer coordinates now map to rendering coordinates before alpha hit testing and dragging.
- [Desktop CI run 37205386236](https://github.com/miflow13/mochi-desktop/actions/runs/37205386236) passed the desktop suite (1,034 passed, 1 skipped), Python compilation, installer shell syntax, committed whitespace checks and wheel build/audit.
- Local browser binaries could not launch, so the real-browser result above comes from GitHub Actions. Live VS Code Extension Host QA remains pending.
