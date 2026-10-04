# Mochi VS Code v1 verification

Implemented on `feat/mochi-vscode-v1`. Desktop runtime source and original artwork are not modified.

## Verified in this workspace
- `npm run build`: prepares 16 animations / 95 original PNG files; checks canonical dimensions, metadata, and runtime timing overrides.
- `npm test`: 21 tests pass, including real PNG decoding/Canvas rendering, alpha hit testing, directional gestures and cancellation, sleep/wake, reduced motion controls, hidden timer cleanup, privacy/opt-in, state persistence and duplicated readiness.
- `npm run check`: all JavaScript syntax checks pass.
- `npm run package`: official vsce produces a VSIX with 107 files, approximately 521 KB.
- VSIX audit: every packaged PNG is byte-identical to its canonical desktop asset; no tests or npm dependencies are packaged.
- `git diff --check`: clean.
- Independent code review found a duplicate-ready initialization race; a failing regression reproduced it before the fix. Review also identified Reset Position leaving typing active; a Canvas regression reproduced it and the behavior was corrected. An additional regression guards early visibility from announcing readiness before PNG loading completes.

## Pending verification
- Live VS Code Extension Host installation, focus, restoration and disposal: VS Code is not installed in this environment.
- Real-browser smoke: Playwright's Chromium download returned an invalid ZIP. An alternate npm-provided Chromium binary could report its version but exited with SIGTRAP on launch. Canvas tests exercise the real renderer adapter and decoded PNGs, but do not prove browser CSS/CSP enforcement or live VS Code hosting.
- Full desktop pytest: the local checkout is an extension-focused materialized snapshot without GTK runtime dependencies. Existing repository CI remains the full desktop test gate; the extension workflow adds browser checks and VSIX artifacts.

See `extensions/mochi-vscode/MANUAL-QA.md`. Do not treat the unchecked live-host/browser cases as passed. No Marketplace publishing or merge has been performed.

## Implementation choices
- Plain JavaScript with JSDoc-friendly module boundaries avoids a compilation/bundling layer for v1. The code has no runtime npm dependencies.
- Canonical generated assets are built from the repository source, rather than committing a second artwork tree.
- Typing reactions default off and carry only an activity event, not document content or filenames.
