# Live VS Code checklist

Use the packaged VSIX and the F5 development launch. Unit/browser tests cannot prove VS Code hosting integration.

- [ ] Install VSIX on desktop VS Code >=1.90; activity icon opens the Mochi view.
- [ ] Run Show/Pet/Sleep/Reset with the view closed and already open.
- [ ] Idle/breathing and blink remain quiet; pet hearts play once and recover.
- [ ] Drag left, reverse right, release, cancel with Escape, then pet/sleep again.
- [ ] Transparent canvas padding does not start a gesture. Drag does not activate unrelated controls.
- [ ] Sleep, hide/reopen, reload window, wake; no invisible or permanently held state.
- [ ] Placement survives reload; narrow/short panels and 100%/200% zoom keep the sprite in bounds.
- [ ] Typing reactions stay off initially; opt in and verify entry/loop/exit and direct-interaction priority.
- [ ] Disable typing during its loop; it exits. Editing another document or a hidden Mochi view does not react.
- [ ] Keyboard focus, Enter/Space, native buttons and screen-reader labels work.
- [ ] System/extension reduced motion shows still poses; pet/sleep/drag remain available.
- [ ] Light, dark and high-contrast themes keep controls and focus outlines readable.
- [ ] Repeated hide/show closes animation timers; extension deactivation releases subscriptions.
- [ ] Devtools show no failed asset loads, CSP violations, script errors or extension-originated network calls.

Desktop runtime files and assets are unchanged by this feature. Existing full desktop pytest CI remains required for merge; live GTK interaction checks are relevant only if a follow-up changes that runtime.
