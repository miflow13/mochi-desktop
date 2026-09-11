# Sleep/wake ambient lifecycle

The GNOME helper owns the existing 120-second server-global inactivity threshold.
Mutter resets inactivity on keyboard, pointer and touch input; Mochi's animation
ticks and autonomous walking do not count as user activity. The persistent idle
watch retains its ID across cycles and is removed by extension disable. Only the
user-active watch is one-shot. See [Mutter's idle watch API](https://mutter.gnome.org/meta/method.IdleMonitor.add_idle_watch.html)
and [active watch API](https://mutter.gnome.org/meta/method.IdleMonitor.add_user_active_watch.html).

`presence_activity.py` forwards semantic D-Bus events to Buddy. `_on_user_idle`
records inactivity but only starts automatic sleep from idle/blinking/walking;
menus and active contextual states retain ownership. If deferred, the existing
5–15-second ambient action timer retries when Mochi is idle (also with Stay put).
Playback guards still prevent sleep. No separate sleep timer is added.

Typing and direct interaction clear deferred inactivity and request wake once.
New media/file activity and terminal/VS Code focus can also request wake.
`_wake_up` changes state before marking interaction, preventing recursive wake.
The existing animation callback ignores stale completions, finishes wake, then
resolves current typing or the existing contextual priority chain. A typing burst
that ends during wake is not replayed. Manual Sleep remains an explicit action.

## Verification

`tests/test_sleep_lifecycle.py` exercises real Buddy state and animation methods
without a display: repeated cycles, typing through wake, deferred sleep, cancelled
deferred sleep, and activity during sleep's intro. `tests/test_presence_watches.py`
runs the actual helper watch methods with persistent-idle/one-shot-active semantics
using Node (skipped if Node is absent).

The full suite has six failures also reproduced in a clean `origin/main` archive:
Fedora harness logger, sparse Chromium media expectation, phrase count, dance PNG
inventory, blink endpoint pixels, and blink timings. They are outside this fix.

## Fedora/Wayland QA

Install this branch with `./install.sh`, then log out/in so GNOME loads the updated
helper. Quit any existing Mochi before launching `mochi --debug` in a terminal.

1. Confirm the log says presence awareness is enabled. Leave the desktop untouched
   for two minutes with no active contextual mode: sleep intro should play once,
   followed by the sleeping loop.
2. Move the mouse, then repeat using typing. Wake should play once and finish in
   idle or the still-active typing/contextual mode. Repeat a second full cycle.
3. Test direct click and pickup during sleep intro and the sleeping loop. Confirm
   drop returns cleanly and old sleep completion never replaces pickup/wake.
4. Keep terminal, VS Code, video or music active past two minutes. Confirm sleep
   does not steal the active mode. End that mode and check subsequent sleep/wake.
5. Repeat with Stay put, context menu and developer menu; confirm menus still open,
   dragging works, and no traceback appears.

This change does not supply global inactivity detection on desktops without the
GNOME helper. Real Shell input delivery and visible GTK transitions require desktop
QA; passing the isolated tests is not evidence of those hardware checks.
