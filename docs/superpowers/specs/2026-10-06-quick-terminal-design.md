# Quick Terminal — Design

**Date:** 2026-10-06

**Builds on:** the Focus window's placement beside Mochi (`presence/focus_session.py`), the context-menu row pattern (`presence/edge_roam_controls.py`), and the updater's child-environment hygiene (`update/worker.py`)

**Status:** proposed, awaiting owner approval. Implementation plan: `docs/superpowers/plans/2026-10-06-quick-terminal.md`. Mockup: `docs/design/quick-terminal/`. No runtime code exists yet.

## Purpose

Sometimes you want to run one command, such as checking for updates, restarting a service, or peeking at a log, without hunting for a terminal app. Quick Terminal adds one row to Mochi's right-click menu that opens a small, real terminal right next to Mochi. It is a full shell, so `sudo`, `vim`, `top` and tab completion all work. When the shell exits the window goes away, and nothing about the session is kept.

Mochi only hosts the terminal. It never reads what is typed or printed, and nothing outside Mochi's own menu can open the terminal or put text in it.

## Goals

- One click from the context menu to a working shell, placed beside Mochi.
- A real terminal (PTY, colours, job control, interactive programs), not a command box.
- Temporary: one window at a time, gone when the shell exits, not restored on restart.
- Never lose a running command by accident: closing the window or quitting Mochi while something runs asks first.
- GUI apps launched from the terminal behave as they would from Ptyxis. In particular they must not inherit the `GDK_BACKEND=x11` that Mochi sets for itself.
- Mochi keeps working, with the row disabled and a hint, when the terminal library is not installed.

## Non-goals

- Running commands on Mochi's behalf, suggesting commands, or reading output. Mochi does not interpret the terminal at all.
- Opening the terminal from anything except the menu row: no app action, D-Bus method, CLI flag, keyboard shortcut or agent event in v1.
- Tabs, splits, profiles, font settings, or saved scrollback.
- A coworking scene while the terminal is focused. It is a natural follow-up and is in the parking lot.
- Replacing the user's terminal app.

## Fit with the project philosophy

The philosophy warns against turning Mochi into "a chatbot window" or "a dense settings surface" (`docs/wiki/Project-Philosophy.md:13-19`) and asks that the runtime stay small (§13, `:170-181`). Quick Terminal stays inside those lines:

- It is a tool the user opens on purpose, never ambient behavior. Mochi does not speak about it, and it adds no timers.
- It adds one menu row, next to Focus, which is the other "open a window beside Mochi" feature.
- The terminal library is a system typelib detected at runtime, the same way GStreamer is (`sound.py:258-268`). `pyproject.toml` keeps `dependencies = []`, and Mochi runs normally without it.
- The philosophy's authority order puts the owner's explicit request first (`Project-Philosophy.md:253-262`).

## Behavior

### Opening

- The context menu gains **Quick terminal** (row id `quick-terminal`, icon `utilities-terminal-symbolic`) directly after **Focus**.
- Clicking it closes the menu first (`_close_context_menu_then`), then opens the window. If a quick terminal is already open, it is presented instead: there is only ever one.
- On X11/XWayland the window is placed beside Mochi using the Focus window's placement rule (`_focus_window_position_for_anchor`, `focus_session.py:35-112`): beside Mochi when it fits, otherwise above, then below, clamped to the monitor. It does not follow Mochi afterwards. On pure Wayland the compositor places it.
- Mochi waves once (`wave`, through `_play_idle_beat`) unless curiosity suppression applies, for example while dragging. The wave is an acknowledgement, not a state change.
- Opening is direct interaction, so quiet mode never blocks it.

### The window

- A normal, focusable app window titled "Quick terminal — Mochi", with a GTK header bar showing "🌱 Quick terminal" and the standard close button (mockup: `docs/design/quick-terminal/mockup-light.png`). Unlike Mochi's overlays, it must take keyboard focus.
- A `Vte.Terminal` sized to 80 × 16 cells, with 2 000 lines of scrollback.
- Colours follow the theme. The window reads GTK's resolved foreground: light text means a dark theme, which gives `#eeeeec` on `#1e1e1e`; otherwise `#2e3436` on `#ffffff`. The cursor is Mochi green `#79c98b`. The colours are re-applied when GTK's dark-preference or theme-name setting changes (`color_scheme.py` mirrors the desktop's choice into the former). A scheme change that touches neither setting shows up the next time the terminal opens.
- Ctrl+Shift+C and Ctrl+Shift+V copy and paste. Every other key goes to the shell, including Escape and Ctrl+C.

### The shell

- The user's login shell from the password database (`pwd.getpwuid(os.getuid()).pw_shell`), falling back to `/bin/sh` if it is missing, relative or not executable.
- A fixed argv: the shell path alone, never `-c` and never extra words.
- Working directory `$HOME`.
- Environment from `terminal_child_environment()`: the session environment, minus `PYTHONPATH` and `MOCHI_UPDATER_*` (reusing `update.worker.child_environment()`), minus `GDK_BACKEND` when Mochi itself forced it. "Forced" is decided by re-running `main.configure_display_backend`'s own predicate on a copy, so the two can never disagree and `main.py` is not touched. A `GDK_BACKEND` the user set themselves is kept.

### Closing

| How | What happens |
|---|---|
| The shell exits (`exit`, Ctrl+D) | The window closes at once. |
| Close button with an idle shell | The window closes. |
| Close button while a command runs | A dialog: "Something's still running — Close the terminal anyway? The running command will be stopped." Buttons **Keep open** (default and Escape) and **Close anyway**. |
| Quitting Mochi (menu Close or Mochi Lab Quit) while a command runs | The terminal comes to the front and asks "Quit Mochi anyway?" Mochi quits only after **Close anyway**. |
| Quitting Mochi with an idle shell | Mochi quits and the terminal closes with it. |
| Session logout, or the updater restarting Mochi | The terminal closes without asking, like every other terminal at logout. The shell and its jobs get SIGHUP. |

"A command runs" means the terminal's foreground process group is not the shell's own: `os.tcgetpgrp(pty_fd) != shell_pid`. This was verified with VTE 0.76: the check is false for an idle `/bin/sh`, true during `sleep 30`, and false again after Ctrl+C.

### When VTE is missing

The row stays in the menu but is disabled, with a second line "Needs vte291-gtk4" and a tooltip saying what to install. Nothing else in Mochi changes. `install.sh` adds `vte291-gtk4` to its Fedora package list so new installs get it.

## Security and privacy

### Trust boundary

The Agent Companion spec records that any process running as the same user can send Mochi events (`docs/ambisense.md:69-84`). Quick Terminal therefore adds **no** externally reachable entry point: no `Gio` action, no D-Bus method, no command-line flag, no agent event. The only way to open it is a click on the menu row, and the only text that reaches the shell is what the user types or pastes. A same-user process could already start a shell itself, so this design adds no new capability for one. It just declines to add a convenient remote control.

### What Mochi sees

- Mochi never calls VTE's text accessors (`get_text*`), never logs input or output, and never passes terminal data to a `markup=` parameter. A source test enforces the first and last.
- VTE stores scrollback the way it does for Ptyxis and GNOME Console. With VTE 0.76, a 5 000-line run created an unlinked temporary file under `/tmp` held open by the process. Upstream documents that file as encrypted; this session saw the file but did not verify the encryption. Mochi caps scrollback at 2 000 lines and does not touch that storage.
- Mochi's existing content-blind typing detection (`docs/ambisense.md:43-67`) sees keystrokes in this window exactly as it does in any other app. It may start Mochi's typing animation, and it never reads the keys.

### Environment hygiene

Mochi's process carries settings that make sense only for Mochi: `GDK_BACKEND=x11` on GNOME Wayland (`main.py:53`), and possibly `PYTHONPATH` or `MOCHI_UPDATER_*` after an update. The shell gets none of them, so `nautilus .` or `code .` typed into the quick terminal opens natively on Wayland.

## VTE availability

| Platform | Package | Status |
|---|---|---|
| Fedora Workstation 41+ (Ptyxis is the default terminal) | `vte291-gtk4` | Expected to be installed already, because Ptyxis uses VTE for GTK 4. To verify on the owner's machine: `rpm -q vte291-gtk4`. |
| Fedora with GNOME Terminal only | `vte291-gtk4` | May be missing (GNOME Terminal uses the GTK 3 build); `install.sh` installs it. |
| Ubuntu 24.04 / Debian | `gir1.2-vte-3.91` | Verified in this session: installs and works with GTK 4.14 and VTE 0.76. |
| Anything else | (varies) | The row is disabled with the hint; Mochi is otherwise unaffected. |

Runtime check: `python3 -c 'import gi; gi.require_version("Vte", "3.91"); from gi.repository import Vte; print(Vte.get_minor_version())'`.

## Rejected alternatives

| Alternative | Why not |
|---|---|
| Launch the user's terminal (`ptyxis --new-window`, `gnome-terminal`, `xdg-terminal-exec`) | No new dependency and the least code. But it isn't "quick" or "mini": it is a full app window that Wayland will not let Mochi place beside the pet, there is no way to ask before quitting, and Ptyxis has no geometry flag. Worth keeping in mind as a fallback if VTE ever becomes a problem. |
| A one-line command box that runs `subprocess` and shows output | No PTY, so `sudo` prompts, colours, `top`, `vim` and job control all break. It looks like a shell but behaves like a trap. |
| Embedding the user's terminal through `Gtk.Socket` | GTK 3 only; GTK 4 removed it. |
| A keyboard shortcut to open it | Useful, but every shortcut is another entry point to review and another GNOME setting to install. Parking lot. |

## Verified facts

Gathered in this session against `main` @ `4713426`, on Ubuntu 24.04 with GTK 4.14 and VTE 0.76 under Xvfb:

| Fact | Evidence |
|---|---|
| The plan's `spawn_async` call works | Called with 11 positional arguments (`None` for the child-setup function and its data, timeout `-1`), it spawned `/bin/sh` and reported the pid to the callback. The introspected signature lists 10 named parameters; PyGObject accepts the extra child-setup data argument. |
| `child-exited` passes a raw wait status | Status 768 for `exit 3`; `os.waitstatus_to_exitcode(768) == 3` |
| The busy check works | `tcgetpgrp(pty_fd) == shell_pid` idle → `False` during `sleep 30` → `True` after Ctrl+C |
| GTK 4 `close()` only acts on a realized window, and `destroy` fires on dispose | Prototype tests: cleanup moved from the `destroy` signal to the close path |
| `update/worker.py` and `main.py` import without GTK | `'gi' in sys.modules` is `False` after importing both |
| `Gtk.AlertDialog` is available | GTK 4.14 (`Gtk.AlertDialog` exists since 4.10) |
| Every code block in the plan works | 40 tests written and run, including a real-VTE test; the plan's code applied to a clean checkout passes the full suite (see the plan) |
| Mochi without VTE stays green | With the VTE typelib removed, the full suite gives 1393 passed, 7 skipped (only the real-VTE test skips) |
| VTE keeps scrollback in an unlinked temp file | `/proc/self/fd` showed `/tmp/#… (deleted)` after 5 000 lines; encryption not verified |

## Architecture

```
context menu ── "Quick terminal" row ──► QuickTerminalMixin            presence/quick_terminal_controls.py
                                           ├─ load_vte() → row enabled/disabled
                                           ├─ one QuickTerminalWindow at a time
                                           ├─ wave beat (curiosity suppression)
                                           ├─ _quit_application: ask first if busy
                                           └─ shutdown_presence: destroy window
                                                   │
                                                   ▼
                               QuickTerminalWindow                         presence/quick_terminal_window.py
                                 ├─ Gtk.ApplicationWindow + HeaderBar
                                 ├─ Vte.Terminal 80×16, 2 000 lines, theme palette
                                 ├─ spawn_async(shell alone, $HOME, clean env)
                                 ├─ child-exited → close; close-request → confirm if busy
                                 └─ placement beside Mochi (Focus window rule)
                                                   │
                                                   ▼
                               quick_terminal.py (GTK-free)                src/mochi/quick_terminal.py
                                 terminal_child_environment · login_shell · shell_argv
                                 foreground_job_running · exit_code_from_wait_status
```

### `src/mochi/quick_terminal.py` (new, GTK-free)

Pure helpers with injected seams (`getpwuid`, `is_executable`, `tcgetpgrp`), following the injection style of `presence/signals.py`. It imports `update.worker.child_environment` and `main.configure_display_backend`, both of which import without GTK.

### `src/mochi/presence/quick_terminal_window.py` (new)

`load_vte()` caches the `Vte` module or `None`. `QuickTerminalWindow` owns the window, the terminal, two `Gtk.Settings` notify handlers for theme changes, and the placement serial. Its cleanup runs on the allowed close path and in `destroy()`, not on the `destroy` signal: GTK 4 emits that only when the object is disposed, which a Python reference can delay indefinitely. `confirm_close()` shows one `Gtk.AlertDialog` at a time.

### `src/mochi/presence/quick_terminal_controls.py` (new, `QuickTerminalMixin`)

A cooperative mixin, like `FocusSessionMixin`, which also owns one window: every entry point is a chain hook (`_build_context_menu`, `_quit_application`, `shutdown_presence`). Its hooks use `getattr` defaults so objects built with `object.__new__`, which other suites use, pass straight through.

### `src/mochi/presence/click_dialogue.py`

Insert `QuickTerminalMixin` between `QuickStartMixin` and `FocusSessionMixin` in both buddy classes. It must come before `FocusSessionMixin` in the MRO so the `focus` row already exists when it registers `after="focus"`.

### `install.sh` and CI

`vte291-gtk4` joins the Fedora package list. `.github/workflows/tests.yml` gains `gir1.2-vte-3.91`, so the real-VTE test runs in CI instead of skipping. Both are one-line changes, called out for the owner to accept or drop.

## Edge cases

| Case | Handling |
|---|---|
| VTE not installed | Row disabled with the hint; `load_vte()` returns `None`; nothing else changes. |
| Shell fails to start (bad `pw_shell` that still passes the checks, exhausted PTYs) | The terminal shows "Mochi couldn't start your shell. Close this window and try again." in plain text; the window stays until closed. |
| Row clicked twice quickly | The second click presents the existing window. |
| Close clicked twice while busy | One dialog (`confirm_close` is re-entrancy safe). |
| Shell exits while the confirm dialog is open | `child-exited` closes the window; the dialog's parent goes with it. |
| Mochi dragged or resized while the terminal is open | The terminal stays where it is. |
| Theme switched while open | Colours re-applied on the next idle after GTK's dark-preference or theme-name setting changes. |
| Fractional scaling on GNOME Wayland | The window is an XWayland window like the rest of Mochi, so text may be slightly soft. See Risks. |
| `sudo` inside the terminal | Works: real PTY, and polkit or sudo prompts appear in the terminal. |
| User's own `GDK_BACKEND=x11` outside GNOME Wayland | Kept: the predicate only strips the value Mochi set itself. |

## Testing

Run with `PYTHONPATH=src xvfb-run -a python3 -m pytest -q`. CI is the authoritative gate.

1. **Helpers** (`tests/test_quick_terminal.py`): Mochi's forced `GDK_BACKEND` is dropped and a user's is kept; native-Wayland opt-out respected; private variables dropped; the input is not mutated; the shell comes from `pw_shell` with all three fallbacks plus an unknown uid; argv is the shell alone; the busy check covers idle, busy and a closed PTY; wait status → exit code; and one test against a real pseudo-terminal.
2. **Window, with a fake VTE** (`tests/test_quick_terminal_window.py`): spawn uses the shell alone, `$HOME`, and a clean env; 80×16 with 2 000 lines of scrollback; `busy` uses the PTY fd and the shell pid; a spawn failure explains itself in plain text; shell exit closes and notifies once; an idle close needs no dialog; a busy close asks first; the dialog defaults to Keep open, shows once and has quit wording; `destroy()` disconnects the theme watch and is idempotent; palette selection; green cursor; copy and paste; a source check that nothing calls `.get_text` or passes `markup=`.
3. **Window, with real VTE** (same file, skipped when VTE is missing): spawn → idle → `sleep 30` busy → Ctrl+C idle → `exit` closes.
4. **Controls** (`tests/test_quick_terminal_controls.py`): the row sits after `focus` and is enabled with VTE; disabled with the hint without it; one window at a time; wave unless suppressed; no window without VTE; closing forgets the window; an idle quit quits; a busy quit asks first and quits after confirming; shutdown destroys once; half-built objects pass through; MRO placement.
5. **Existing suites:** `tests/test_installer.py` and `tests/test_context_menu_layout.py` pass unchanged.

All 40 tests were written and run while planning; the full suite went from 1354 to 1394 passed.

## Documentation

- `CHANGELOG.md` Unreleased → Added: one plain-language entry.
- `README.md`: *Quick terminal* in the controls section, plus the optional `vte291-gtk4` package.
- `docs/ambisense.md`: one paragraph under Privacy saying that Mochi hosts but never reads the quick terminal.
- `docs/CODEBASE_MANUAL.md` §6: add `QuickTerminalMixin` to the layer list.
- `REGRESSION_WATCHLIST.md`, new **Quick Terminal** section:
  - [ ] Menu → Quick terminal opens a working shell beside Mochi; clicking again focuses the same window
  - [ ] `exit` closes it; closing with `sleep 60` running asks, and **Keep open** keeps it running
  - [ ] Quitting Mochi with `sleep 60` running asks first; with an idle shell it quits at once
  - [ ] `echo $GDK_BACKEND` is empty in the terminal on GNOME Wayland; `gnome-text-editor &` opens as a native Wayland window
  - [ ] `sudo -v` works; `vim`, `top` and colours render
  - [ ] Light and dark themes give readable colours, and switching themes while open updates them
  - [ ] Without `vte291-gtk4` the row is disabled with the hint and nothing else breaks
  - [ ] Right-click, drag and sleep on Mochi still work while the terminal is open and focused

## Delivery

- This spec, the plan and the mockup ship as a docs-only draft PR from `claude/quick-terminal-design`, separate from Resource Sense (one feature per diff).
- After approval, implementation happens on a new branch from `main` following the plan, test-first, as one reviewable PR.
- Live verification on Fedora / GNOME / Wayland (XWayland) by the owner before merge.

## Risks

- **XWayland text rendering.** Under fractional scaling, X11 windows can look slightly soft. The terminal inherits this from Mochi's process-wide `GDK_BACKEND=x11` and cannot opt out without becoming a separate process.
- **Package name and availability on Fedora** are expected but unverified here; the runtime check above settles it.
- **Logout and updater restarts** close the terminal without asking. The terminal behaves like any other here, but a long `dnf upgrade` started from it would be interrupted.
- **Mochi's typing animation** may play while you type in the terminal. This is existing behavior for every app and is harmless, but QA should confirm it feels right.

## Stress Test Results: Quick Terminal

### Resolved Decisions

- **Technology (owner, 2026-10-06):** embedded VTE in a Mochi window, detected at runtime, with the row disabled and a hint when missing.
- **Delivery (owner):** a separate design PR from Resource Sense.
- **Trust boundary:** no external entry point at all; the menu click is the only way in.
- **Environment leak:** Mochi's forced `GDK_BACKEND=x11` is stripped using `main.py`'s own predicate, with no change to `main.py`.
- **Busy detection:** a foreground process group check, verified against real VTE.
- **Cleanup timing (found while prototyping):** GTK 4's `destroy` signal waits for dispose, so cleanup runs on the close path instead; tests cover both shell exit and `destroy()`.

### Changes Made

- The window module lives in `presence/`, not `src/mochi/`, because it reuses the Focus window's placement helper (`presence/focus_session.py`).
- The scrollback claim changed from "in memory only" to what was observed (an unlinked temp file, encryption per upstream).

### Deferred / Parking Lot

- A terminal-coworking scene while the quick terminal is focused (Mochi at the laptop).
- A keyboard shortcut, after deciding how it interacts with GNOME custom shortcuts (`developer_shortcut.py`).
- Falling back to launching the user's terminal when VTE is missing, if owners prefer that to a disabled row.
- Font and size preferences.

### Confidence Assessment

- **High** for the code: every module was prototyped and run, including against real VTE, and the plan was applied to a clean checkout.
- **Medium** for live behavior: Fedora package availability, XWayland rendering and dialog placement need owner QA on GNOME.
