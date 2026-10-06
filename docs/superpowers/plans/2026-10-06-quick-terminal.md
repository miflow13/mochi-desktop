# Quick Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use beads-superpowers:subagent-driven-development (recommended) or beads-superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent <epic-id>`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.
>
> **Do not start until the spec and this plan are approved by the owner.**

**Goal:** A **Quick terminal** row in Mochi's context menu opens one small, real VTE terminal beside Mochi. The shell is the user's login shell in `$HOME`, with Mochi's private environment removed. The window closes when the shell exits, and it asks before stopping a running command, including when Mochi quits. Mochi never reads the terminal, and nothing but the menu row can open it.

**Architecture:**
- GTK-free helpers in `src/mochi/quick_terminal.py`: the child environment, shell choice, a fixed argv, foreground-job detection, and wait-status decoding.
- `QuickTerminalWindow` in `src/mochi/presence/quick_terminal_window.py`: the window, `Vte.Terminal`, spawning, closing and confirmation, theme colours, and placement through the Focus window's rule.
- `QuickTerminalMixin` in `src/mochi/presence/quick_terminal_controls.py`: the menu row, one window at a time, the wave beat, quit confirmation, and shutdown.
- One-line additions to `install.sh` (Fedora `vte291-gtk4`) and CI (`gir1.2-vte-3.91`).

Not touched: `MochiState`, `main.py` and GDK backend selection, the updater, `pyproject.toml` dependencies.

**Tech Stack:** Python 3.11+, GTK4/PyGObject, VTE 3.91 (optional system typelib), pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-quick-terminal-design.md`

**Mockup:** `docs/design/quick-terminal/mockup-light.png`, `mockup-dark.png` (source: `mockup.html`)

## Global Constraints

- The only entry point is the menu row. Add no `Gio` action, D-Bus method, CLI flag, shortcut or agent hook.
- The spawned argv is exactly `[shell]`; never `-c`, never extra words.
- No code calls VTE text accessors (`.get_text*`) or passes terminal data to `markup=`. A test checks the source.
- The child environment never contains `PYTHONPATH`, `MOCHI_UPDATER_*`, or a `GDK_BACKEND` that Mochi forced.
- At most one window. The window and its settings handlers are torn down on close, `destroy()` and shutdown (Manual Rule 4).
- VTE is optional: `load_vte()` returns `None` when it is missing, and `pyproject.toml` keeps `dependencies = []`.
- Constants: 80 × 16 cells; 2 000 scrollback lines; colours light `#2e3436`/`#ffffff`, dark `#eeeeec`/`#1e1e1e`, cursor `#79c98b`; fallback window size 660 × 360; beat `wave`.
- **Test command.** Use an interpreter with `gi` and the GTK 4 typelib. In the planning container:
  - `PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider <paths>`
  - CI runs `xvfb-run -a python3 -m pytest -q`.
- **Baseline** on `main` @ `4713426`: **1354 passed, 6 skipped** with `-k "not TypingActivityMonitorTests"`. Those 9 tests abort with SIGTRAP in a container without an accessibility bus, even alone; CI is expected to run them. Re-measure at Task 1.
- Commits end with the implementing session's attribution trailer.
- Work on a new branch from `main` (for example `claude/quick-terminal`).

## Verified facts

Gathered while writing this plan (2026-10-06), on Ubuntu 24.04, GTK 4.14, VTE 0.76, Xvfb, against a clean copy of `main` @ `4713426`:

| Fact | Evidence |
|---|---|
| Task 2's helpers and tests are correct | 15 passed, including one against a real `pty.fork()` |
| Task 3's window works with a fake and a real VTE | 14 passed; the real-VTE test spawns `/bin/sh`, sees busy during `sleep 30`, idle after Ctrl+C, and the window closes on `exit` |
| Task 4's mixin and wiring are correct | 11 passed, including MRO placement and half-built objects |
| Task 5 keeps the installer green | `tests/test_installer.py` 20 passed; `bash -n install.sh` ok |
| All of the above together | 1394 passed, 6 skipped, 0 failed (1354 + 40 new) |
| Mochi without VTE (today's CI) | With the VTE typelib removed: 1393 passed, 7 skipped; only the real-VTE test skips, and the row tests use a patched `load_vte` |
| The plan text itself is executable | Every code block was extracted from this document and applied to a pristine `main` checkout; the full suite passed (see totals) |
| GTK 4 cleanup timing | `close()` is ignored on an unrealized window, and the `destroy` signal waits for dispose, so cleanup runs on the close path |

**Not verified:** anything that needs a real GNOME session: Fedora package availability, XWayland text rendering, dialog stacking over the terminal. Those are the owner's QA.

## File Map

| File | Responsibility | Task |
|---|---|---|
| `src/mochi/quick_terminal.py` (new) | Environment, shell, argv, busy check, exit code | 2 |
| `tests/test_quick_terminal.py` (new) | Helper tests | 2 |
| `src/mochi/presence/quick_terminal_window.py` (new) | Window, terminal, spawn, close/confirm, colours, placement | 3 |
| `tests/test_quick_terminal_window.py` (new) | Window tests (fake VTE + one real-VTE test) | 3 |
| `src/mochi/presence/quick_terminal_controls.py` (new) | Menu row, lifecycle, quit confirmation | 4 |
| `tests/test_quick_terminal_controls.py` (new) | Mixin tests | 4 |
| `src/mochi/presence/click_dialogue.py` | Mixin order | 4 |
| `install.sh`, `.github/workflows/tests.yml` | VTE package | 5 |
| `CHANGELOG.md`, `README.md`, `docs/ambisense.md`, `docs/CODEBASE_MANUAL.md`, `REGRESSION_WATCHLIST.md` | Docs and QA | 6 |

---

### Task 1: Branch and baseline

**Files:** none.

**Interfaces:**
- Consumes: `main`.
- Produces: a feature branch and a recorded baseline count.

**Acceptance Criteria:**
- The branch is created from the latest `main`; the baseline is recorded for the PR body.

- [ ] **Step 1: Branch from main**

```bash
cd /home/user/mochi-desktop
git fetch origin main
git checkout -b claude/quick-terminal origin/main
```

- [ ] **Step 2: Record the baseline**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected on `4713426`: `1354 passed, 6 skipped` with the accessibility-bus tests deselected.

---

### Task 2: GTK-free helpers

**Files:**
- Create: `src/mochi/quick_terminal.py`
- Create: `tests/test_quick_terminal.py`

**Interfaces:**
- Consumes: `mochi.main.configure_display_backend`, `mochi.update.worker.child_environment` (both import without GTK).
- Produces:
  - `terminal_child_environment(base=None) -> dict[str, str]`
  - `mochi_forced_xwayland(environment) -> bool`
  - `login_shell(*, uid=None, getpwuid=..., is_executable=...) -> str`
  - `shell_argv(shell) -> list[str]`
  - `foreground_job_running(pty_fd, shell_pid, *, tcgetpgrp=...) -> bool`
  - `exit_code_from_wait_status(status) -> int | None`
  - `FALLBACK_SHELL = "/bin/sh"`

**Acceptance Criteria:**
- The module imports without `gi`.
- All 15 tests pass.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quick_terminal.py`:

```python
"""Quick Terminal pure helpers: child environment, shell choice, busy check."""

from __future__ import annotations

import os
import pwd
import unittest

from mochi.quick_terminal import (
    FALLBACK_SHELL,
    exit_code_from_wait_status,
    foreground_job_running,
    login_shell,
    mochi_forced_xwayland,
    shell_argv,
    terminal_child_environment,
)

GNOME_WAYLAND = {
    "XDG_SESSION_TYPE": "wayland",
    "XDG_CURRENT_DESKTOP": "GNOME",
    "DISPLAY": ":0",
    "WAYLAND_DISPLAY": "wayland-0",
    "HOME": "/home/mika",
}


def passwd(shell: str) -> pwd.struct_passwd:
    return pwd.struct_passwd(("mika", "x", 1000, 1000, "", "/home/mika", shell))


class ChildEnvironmentTests(unittest.TestCase):
    def test_drops_gdk_backend_that_mochi_forced(self) -> None:
        environment = terminal_child_environment({**GNOME_WAYLAND, "GDK_BACKEND": "x11"})
        self.assertNotIn("GDK_BACKEND", environment)
        self.assertEqual(environment["WAYLAND_DISPLAY"], "wayland-0")

    def test_keeps_gdk_backend_outside_gnome_wayland(self) -> None:
        base = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "GDK_BACKEND": "x11"}
        self.assertEqual(terminal_child_environment(base)["GDK_BACKEND"], "x11")

    def test_keeps_gdk_backend_when_native_wayland_was_requested(self) -> None:
        base = {**GNOME_WAYLAND, "MOCHI_NATIVE_WAYLAND": "1", "GDK_BACKEND": "x11"}
        self.assertFalse(mochi_forced_xwayland(base))
        self.assertEqual(terminal_child_environment(base)["GDK_BACKEND"], "x11")

    def test_keeps_a_users_own_non_x11_backend(self) -> None:
        base = {**GNOME_WAYLAND, "GDK_BACKEND": "wayland"}
        self.assertEqual(terminal_child_environment(base)["GDK_BACKEND"], "wayland")

    def test_drops_mochi_private_variables_like_updater_children(self) -> None:
        base = {
            **GNOME_WAYLAND,
            "PYTHONPATH": "/opt/mochi/stub",
            "MOCHI_UPDATER_WORKSPACE": "/tmp/x",
            "EDITOR": "vim",
        }
        environment = terminal_child_environment(base)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("MOCHI_UPDATER_WORKSPACE", environment)
        self.assertEqual(environment["EDITOR"], "vim")

    def test_does_not_mutate_the_input(self) -> None:
        base = {**GNOME_WAYLAND, "GDK_BACKEND": "x11"}
        terminal_child_environment(base)
        self.assertEqual(base["GDK_BACKEND"], "x11")


class LoginShellTests(unittest.TestCase):
    def test_uses_password_database_shell(self) -> None:
        shell = login_shell(uid=1000, getpwuid=lambda _uid: passwd("/usr/bin/fish"),
                            is_executable=lambda _path: True)
        self.assertEqual(shell, "/usr/bin/fish")

    def test_falls_back_when_shell_missing_relative_or_not_executable(self) -> None:
        for entry, executable in (("", True), ("fish", True), ("/usr/bin/fish", False)):
            with self.subTest(entry=entry, executable=executable):
                shell = login_shell(uid=1000, getpwuid=lambda _uid: passwd(entry),
                                    is_executable=lambda _path: executable)
                self.assertEqual(shell, FALLBACK_SHELL)

    def test_falls_back_for_unknown_uid(self) -> None:
        def missing(_uid):
            raise KeyError(_uid)
        self.assertEqual(login_shell(uid=4242, getpwuid=missing), FALLBACK_SHELL)

    def test_argv_is_the_shell_alone(self) -> None:
        self.assertEqual(shell_argv("/bin/bash"), ["/bin/bash"])


class BusyCheckTests(unittest.TestCase):
    def test_idle_shell_owns_the_foreground(self) -> None:
        self.assertFalse(foreground_job_running(7, 1234, tcgetpgrp=lambda _fd: 1234))

    def test_running_command_owns_the_foreground(self) -> None:
        self.assertTrue(foreground_job_running(7, 1234, tcgetpgrp=lambda _fd: 5678))

    def test_unknown_or_closed_pty_is_not_busy(self) -> None:
        def closed(_fd):
            raise OSError("bad fd")
        self.assertFalse(foreground_job_running(None, 1234))
        self.assertFalse(foreground_job_running(7, None))
        self.assertFalse(foreground_job_running(7, -1))
        self.assertFalse(foreground_job_running(7, 1234, tcgetpgrp=closed))

    def test_wait_status_to_exit_code(self) -> None:
        self.assertEqual(exit_code_from_wait_status(768), 3)
        self.assertEqual(exit_code_from_wait_status(0), 0)
        self.assertIsNone(exit_code_from_wait_status(-1))


class RealPtyTests(unittest.TestCase):
    """The busy check against a real pseudo-terminal, no VTE needed."""

    def test_busy_check_follows_the_real_foreground_group(self) -> None:
        import pty
        import time

        pid, fd = pty.fork()
        if pid == 0:  # child: become an idle "shell" owning the terminal
            os.execvp("sh", ["sh", "-c", "sleep 2"])
        try:
            time.sleep(0.2)
            # sh -c execs sleep in the session leader's group, so the child's
            # pid is the foreground group: "idle shell" from our viewpoint.
            self.assertFalse(foreground_job_running(fd, pid))
            self.assertTrue(foreground_job_running(fd, pid + 100000))
        finally:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and see them fail**

```bash
PYTHONPATH=src python3.12 -m pytest -q -p no:cacheprovider tests/test_quick_terminal.py 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'mochi.quick_terminal'`.

- [ ] **Step 3: Implement**

Create `src/mochi/quick_terminal.py`:

```python
"""Quick Terminal helpers that need no display: environment, shell, busy check.

Mochi only *hosts* the terminal. Nothing here (or in the window) reads what
the user types or what the shell prints.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
import pwd

from mochi.main import configure_display_backend
from mochi.update.worker import child_environment

FALLBACK_SHELL = "/bin/sh"


def mochi_forced_xwayland(environment: Mapping[str, str]) -> bool:
    """Whether GDK_BACKEND=x11 was set by Mochi itself (main.py), not the user.

    Re-runs main.configure_display_backend's own predicate on a copy, so the
    two can never disagree and main.py stays untouched.
    """
    if environment.get("GDK_BACKEND") != "x11":
        return False
    probe = dict(environment)
    probe.pop("GDK_BACKEND", None)
    return configure_display_backend(probe)


def terminal_child_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The shell's environment: the user's session, minus Mochi's private bits.

    - PYTHONPATH and MOCHI_UPDATER_* go, exactly as for updater children.
    - GDK_BACKEND=x11 goes when Mochi forced it, so GUI apps started from the
      terminal open natively on Wayland like they would from Ptyxis.
    """
    environment = child_environment(dict(os.environ if base is None else base))
    if mochi_forced_xwayland(environment):
        del environment["GDK_BACKEND"]
    return environment


def login_shell(
    *,
    uid: int | None = None,
    getpwuid: Callable[[int], pwd.struct_passwd] = pwd.getpwuid,
    is_executable: Callable[[str], bool] = lambda path: os.access(path, os.X_OK),
) -> str:
    """The user's shell from the password database, or /bin/sh."""
    try:
        shell = getpwuid(os.getuid() if uid is None else uid).pw_shell
    except KeyError:
        return FALLBACK_SHELL
    if shell and os.path.isabs(shell) and is_executable(shell):
        return shell
    return FALLBACK_SHELL


def shell_argv(shell: str) -> list[str]:
    """A fixed argv: the shell alone. Never ``-c``, never extra words."""
    return [shell]


def foreground_job_running(
    pty_fd: int | None,
    shell_pid: int | None,
    *,
    tcgetpgrp: Callable[[int], int] = os.tcgetpgrp,
) -> bool:
    """True while something other than the idle shell owns the terminal.

    An interactive shell with job control is its own process group; a running
    command becomes the terminal's foreground group (verified with VTE 0.76).
    """
    if pty_fd is None or shell_pid is None or shell_pid <= 0:
        return False
    try:
        return tcgetpgrp(pty_fd) != shell_pid
    except OSError:
        return False


def exit_code_from_wait_status(status: int) -> int | None:
    """VTE's child-exited passes a raw wait status (e.g. 768 -> exit code 3)."""
    try:
        return os.waitstatus_to_exitcode(status)
    except ValueError:
        return None
```

- [ ] **Step 4: Run them and see them pass**

```bash
PYTHONPATH=src python3.12 -m pytest -q -p no:cacheprovider tests/test_quick_terminal.py 2>&1 | tail -3
```

Expected: `15 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/quick_terminal.py tests/test_quick_terminal.py
git commit -m "feat: add Quick Terminal environment, shell and busy helpers"
```

---

### Task 3: The terminal window

**Files:**
- Create: `src/mochi/presence/quick_terminal_window.py`
- Create: `tests/test_quick_terminal_window.py`

**Interfaces:**
- Consumes: Task 2; `_focus_window_position_for_anchor` (`presence/focus_session.py:35`); `_window_coordinate_scale` (`menu_window.py`); `get_window_position`, `move_window` (`mochi.x11`).
- Produces:
  - `load_vte()` — the cached `Vte` module or `None`
  - `palette_for_foreground(red, green, blue) -> (fg, bg)`
  - `QuickTerminalWindow(*, owner, vte, on_closed, logger=None, environ=None, shell=None)` with `present()`, `busy`, `confirm_close(on_confirmed, *, quitting=False)`, `destroy()`, and the attributes `window` and `terminal`

**Acceptance Criteria:**
- Spawns `[shell]` in `$HOME` with `terminal_child_environment()`.
- Shell exit closes the window and calls `on_closed` exactly once; `destroy()` is idempotent and disconnects the settings handlers.
- Closing while busy shows one confirmation dialog, defaulting to **Keep open**.
- No source in the module calls `.get_text` or uses `markup=`.
- The real-VTE test passes where VTE is installed and skips cleanly where it is not.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quick_terminal_window.py`:

```python
"""QuickTerminalWindow with a fake VTE, plus one real-VTE run when installed."""

from __future__ import annotations

import inspect
import os
import time

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, GObject, Gtk

from mochi.presence import quick_terminal_controls, quick_terminal_window as module
from mochi.presence.quick_terminal_window import (
    DARK_COLORS,
    LIGHT_COLORS,
    QuickTerminalWindow,
    load_vte,
    palette_for_foreground,
)

GNOME_WAYLAND = {
    "XDG_SESSION_TYPE": "wayland",
    "XDG_CURRENT_DESKTOP": "GNOME",
    "DISPLAY": ":0",
    "WAYLAND_DISPLAY": "wayland-0",
    "HOME": "/home/mika",
    "GDK_BACKEND": "x11",
    "PYTHONPATH": "/opt/mochi/stub",
}


class FakePty:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def get_fd(self) -> int:
        return self.fd


class FakeTerminal(Gtk.Box):
    __gsignals__ = {"child-exited": (GObject.SignalFlags.RUN_FIRST, None, (int,))}

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple] = []
        self.spawn_args: tuple | None = None
        self.fed: list[bytes] = []
        self.colors = None
        self.cursor = None
        self.pty = FakePty(7)

    def set_scrollback_lines(self, lines):
        self.calls.append(("scrollback", lines))

    def set_size(self, columns, rows):
        self.calls.append(("size", columns, rows))

    def spawn_async(self, *args):
        self.spawn_args = args

    def get_pty(self):
        return self.pty

    def feed(self, data):
        self.fed.append(data)

    def set_colors(self, foreground, background, palette):
        self.colors = (foreground.to_string(), background.to_string(), palette)

    def set_color_cursor(self, color):
        self.cursor = color.to_string()

    def copy_clipboard_format(self, fmt):
        self.calls.append(("copy", fmt))

    def paste_clipboard(self):
        self.calls.append(("paste",))


class FakeVte:
    Terminal = FakeTerminal

    class PtyFlags:
        DEFAULT = "pty-default"

    class Format:
        TEXT = "text"


@pytest.fixture
def term_window():
    closed: list[int] = []
    owner = Gtk.Window()
    window = QuickTerminalWindow(
        owner=owner,
        vte=FakeVte,
        on_closed=lambda: closed.append(1),
        environ=dict(GNOME_WAYLAND),
        shell="/bin/bash",
    )
    # GTK only honours close() on a realized window, as in real use.
    window.window.present()
    yield window, window.terminal, closed
    window.destroy()


def test_spawns_the_shell_alone_in_home_with_a_clean_environment(term_window):
    window, terminal, _ = term_window
    flags, cwd, argv, envv, *_rest = terminal.spawn_args
    assert flags == "pty-default"
    assert cwd == "/home/mika"
    assert argv == ["/bin/bash"]
    assert "HOME=/home/mika" in envv
    assert not any(entry.startswith(("GDK_BACKEND=", "PYTHONPATH=")) for entry in envv)


def test_terminal_is_80_by_16_with_capped_scrollback(term_window):
    _, terminal, _ = term_window
    assert ("size", 80, 16) in terminal.calls
    assert ("scrollback", 2000) in terminal.calls


def test_busy_checks_the_pty_against_the_shell_pid(term_window, monkeypatch):
    window, _, _ = term_window
    seen = []
    monkeypatch.setattr(module, "foreground_job_running", lambda fd, pid: seen.append((fd, pid)) or True)
    window._on_spawned(None, 4242, None)
    assert window.busy is True
    assert seen == [(7, 4242)]


def test_spawn_failure_explains_in_plain_text_and_keeps_the_window(term_window):
    window, terminal, closed = term_window
    window._on_spawned(None, -1, GLib.Error("no such shell"))
    assert any(b"couldn't start your shell" in data for data in terminal.fed)
    assert closed == []
    assert window._shell_pid is None


def test_shell_exit_closes_the_window_and_notifies_once(term_window):
    window, terminal, closed = term_window
    window._on_spawned(None, 4242, None)
    terminal.emit("child-exited", 768)
    assert closed == [1]
    window.destroy()
    assert closed == [1]


def test_closing_an_idle_terminal_needs_no_confirmation(term_window, monkeypatch):
    window, _, closed = term_window
    monkeypatch.setattr(module, "foreground_job_running", lambda fd, pid: False)
    window.window.close()
    assert closed == [1]


def test_closing_a_busy_terminal_asks_first(term_window, monkeypatch):
    window, _, closed = term_window
    monkeypatch.setattr(module, "foreground_job_running", lambda fd, pid: True)
    asked = []
    monkeypatch.setattr(window, "confirm_close", lambda on_confirmed, **kw: asked.append(on_confirmed))
    window.window.close()
    assert closed == []
    assert asked == [window._close_now]
    window._close_now()
    assert closed == [1]


class FakeDialog:
    instances: list["FakeDialog"] = []

    def __init__(self) -> None:
        self.buttons = None
        self.callback = None
        self.detail = ""
        FakeDialog.instances.append(self)

    def set_message(self, text):
        self.message = text

    def set_detail(self, text):
        self.detail = text

    def set_buttons(self, buttons):
        self.buttons = buttons

    def set_default_button(self, index):
        self.default = index

    def set_cancel_button(self, index):
        self.cancel = index

    def set_modal(self, modal):
        self.modal = modal

    def choose(self, parent, cancellable, callback):
        self.callback = callback

    def choose_finish(self, result):
        return result


def test_confirm_dialog_defaults_to_keep_open_and_shows_once(term_window, monkeypatch):
    window, _, _ = term_window
    FakeDialog.instances = []
    monkeypatch.setattr(module.Gtk, "AlertDialog", FakeDialog)
    confirmed = []
    window.confirm_close(lambda: confirmed.append(True))
    window.confirm_close(lambda: confirmed.append(True))
    assert len(FakeDialog.instances) == 1
    dialog = FakeDialog.instances[0]
    assert dialog.buttons == ["Keep open", "Close anyway"]
    assert dialog.default == 0 and dialog.cancel == 0
    dialog.callback(dialog, 0)  # "Keep open"
    assert confirmed == []
    window.confirm_close(lambda: confirmed.append(True), quitting=True)
    second = FakeDialog.instances[1]
    assert "Quit Mochi" in second.detail
    second.callback(second, 1)  # "Close anyway"
    assert confirmed == [True]


def test_destroy_disconnects_the_theme_watch_and_is_idempotent(term_window):
    window, _, closed = term_window
    assert window._settings_handlers
    window.destroy()
    window.destroy()
    assert window._settings_handlers == []
    assert closed == [1]


def test_palette_follows_the_theme_foreground():
    assert palette_for_foreground(0.93, 0.93, 0.93) == DARK_COLORS
    assert palette_for_foreground(0.18, 0.20, 0.21) == LIGHT_COLORS


def test_cursor_is_mochi_green(term_window):
    _, terminal, _ = term_window
    assert terminal.cursor == "rgb(121,201,139)"
    assert terminal.colors[2] is None


def test_copy_and_paste_go_through_the_terminal(term_window):
    window, terminal, _ = term_window
    window._copy()
    window._paste()
    assert ("copy", "text") in terminal.calls and ("paste",) in terminal.calls


def test_mochi_never_reads_terminal_text():
    for source_module in (module, quick_terminal_controls):
        source = inspect.getsource(source_module)
        assert ".get_text" not in source
        assert "markup=" not in source


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.skipif(load_vte() is None, reason="Vte 3.91 (vte291-gtk4) not installed")
def test_real_vte_busy_detection_and_exit():
    closed: list[int] = []
    owner = Gtk.Window()
    window = QuickTerminalWindow(
        owner=owner,
        vte=load_vte(),
        on_closed=lambda: closed.append(1),
        environ={**os.environ, "PS1": "$ "},
        shell="/bin/sh",
    )
    try:
        window.present()
        assert _wait_until(lambda: window._shell_pid is not None)
        assert window.busy is False
        window.terminal.feed_child(b"sleep 30\n")
        assert _wait_until(lambda: window.busy)
        window.terminal.feed_child(b"\x03")
        assert _wait_until(lambda: not window.busy)
        window.terminal.feed_child(b"exit\n")
        assert _wait_until(lambda: closed == [1])
    finally:
        window.destroy()
```

- [ ] **Step 2: Run them and see them fail**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_quick_terminal_window.py 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'mochi.presence.quick_terminal_window'`.

- [ ] **Step 3: Implement**

Create `src/mochi/presence/quick_terminal_window.py`:

```python
"""Quick Terminal window: a real VTE shell in a small window beside Mochi.

Mochi only hosts the terminal. This module never asks the terminal for its
contents, never logs what is typed or printed, and spawns a fixed argv: the user's shell, alone. Nothing outside Mochi's own menu can open the
window or send it text.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import os

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.menu_window import _window_coordinate_scale  # noqa: E402
from mochi.quick_terminal import (  # noqa: E402
    exit_code_from_wait_status,
    foreground_job_running,
    login_shell,
    shell_argv,
    terminal_child_environment,
)
from mochi.x11 import get_window_position, move_window  # noqa: E402

from .focus_session import _focus_window_position_for_anchor  # noqa: E402

_UNSET = object()
_vte_module: object = _UNSET


def load_vte():
    """``gi.repository.Vte`` 3.91 (GTK 4) if installed, else ``None``. Cached."""
    global _vte_module
    if _vte_module is _UNSET:
        try:
            gi.require_version("Vte", "3.91")
            from gi.repository import Vte
        except (ImportError, ValueError):
            Vte = None
        _vte_module = Vte
    return _vte_module


QUICK_TERMINAL_CSS = """
window.mochi-quick-terminal headerbar {
    min-height: 36px;
}
.mochi-quick-terminal-title {
    font-weight: 700;
}
"""

LIGHT_COLORS = ("#2e3436", "#ffffff")  # foreground, background
DARK_COLORS = ("#eeeeec", "#1e1e1e")
CURSOR_COLOR = "#79c98b"


def _rgba(spec: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    color.parse(spec)
    return color


def palette_for_foreground(red: float, green: float, blue: float) -> tuple[str, str]:
    """Pick terminal colours from the theme's resolved foreground.

    A light foreground means a dark theme. Reading GTK's resolved colour
    works the same whether the dark preference came from the portal sync in
    color_scheme.py or from GTK itself.
    """
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return DARK_COLORS if luminance > 0.5 else LIGHT_COLORS


class QuickTerminalWindow:
    """One terminal window. Closes for good when the shell exits."""

    COLUMNS = 80
    ROWS = 16
    SCROLLBACK_LINES = 2000
    DEFAULT_WIDTH = 660
    DEFAULT_HEIGHT = 360
    _css_displays: set[int] = set()

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        vte,
        on_closed: Callable[[], None],
        logger: logging.Logger | None = None,
        environ: dict[str, str] | None = None,
        shell: str | None = None,
    ) -> None:
        self._owner = owner
        self._vte = vte
        self._on_closed: Callable[[], None] | None = on_closed
        self._logger = logger or logging.getLogger(__name__)
        self._position_serial = 0
        self._shell_pid: int | None = None
        self._confirming = False
        self._force_close = False
        self._closed = False

        application = owner.get_application()
        if application is not None:
            self.window = Gtk.ApplicationWindow(application=application)
        else:
            self.window = Gtk.Window()
        self.window.set_title("Quick terminal — Mochi")
        self.window.add_css_class("mochi-quick-terminal")
        header = Gtk.HeaderBar()
        title = Gtk.Label(label="🌱 Quick terminal")
        title.add_css_class("mochi-quick-terminal-title")
        header.set_title_widget(title)
        self.window.set_titlebar(header)

        self.terminal = vte.Terminal()
        self.terminal.set_scrollback_lines(self.SCROLLBACK_LINES)
        self.terminal.set_size(self.COLUMNS, self.ROWS)
        self.terminal.set_hexpand(True)
        self.terminal.set_vexpand(True)
        self.window.set_child(self.terminal)

        self.terminal.connect("child-exited", self._on_child_exited)
        self.window.connect("close-request", self._on_close_request)
        self.window.connect("map", self._on_map)

        shortcuts = Gtk.ShortcutController()
        for trigger, callback in (
            ("<Control><Shift>c", self._copy),
            ("<Control><Shift>v", self._paste),
        ):
            shortcuts.add_shortcut(
                Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(trigger),
                    Gtk.CallbackAction.new(callback),
                )
            )
        self.window.add_controller(shortcuts)

        # Owned settings watches, disconnected in _finish_close (Rule 4).
        self._settings = Gtk.Settings.get_default()
        self._settings_handlers: list[int] = []
        if self._settings is not None:
            for name in ("gtk-application-prefer-dark-theme", "gtk-theme-name"):
                if self._settings.find_property(name) is not None:
                    self._settings_handlers.append(
                        self._settings.connect(f"notify::{name}", self._on_theme_changed)
                    )
        self._apply_palette()
        self._install_css(owner.get_display())
        self._spawn(environ, shell)

    # -- Shell -----------------------------------------------------------------

    def _spawn(self, environ: dict[str, str] | None, shell: str | None) -> None:
        shell = shell or login_shell()
        environment = terminal_child_environment(environ)
        home = environment.get("HOME") or os.path.expanduser("~")
        self.terminal.spawn_async(
            self._vte.PtyFlags.DEFAULT,
            home,
            shell_argv(shell),
            [f"{key}={value}" for key, value in environment.items()],
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            self._on_spawned,
            None,
        )

    def _on_spawned(self, _terminal, pid: int, error, *_user_data) -> None:
        if error is not None or pid is None or pid <= 0:
            self._logger.warning("[quick-terminal] could not start a shell: %s", error)
            self.terminal.feed(
                b"\r\nMochi couldn't start your shell. Close this window and try again.\r\n"
            )
            return
        self._shell_pid = pid

    @property
    def busy(self) -> bool:
        """Something other than the idle shell owns the terminal."""
        pty = self.terminal.get_pty()
        fd = pty.get_fd() if pty is not None else None
        return foreground_job_running(fd, self._shell_pid)

    def _on_child_exited(self, _terminal, status: int) -> None:
        self._logger.debug(
            "[quick-terminal] shell exited code=%s", exit_code_from_wait_status(status)
        )
        self._shell_pid = None
        self._force_close = True
        self.window.close()

    # -- Closing ---------------------------------------------------------------

    def _on_close_request(self, _window) -> bool:
        if self._force_close or not self.busy:
            # GTK4 emits "destroy" only on dispose, which Python references
            # can delay indefinitely, so clean up here, then let GTK close.
            self._finish_close()
            return False
        self.confirm_close(self._close_now)
        return True

    def confirm_close(self, on_confirmed: Callable[[], None], *, quitting: bool = False) -> None:
        """Ask before stopping a running command. Safe to call twice."""
        if self._confirming:
            return
        self._confirming = True
        dialog = Gtk.AlertDialog()
        dialog.set_message("Something's still running")
        dialog.set_detail(
            "Quit Mochi anyway? The terminal and its running command will be stopped."
            if quitting
            else "Close the terminal anyway? The running command will be stopped."
        )
        dialog.set_buttons(["Keep open", "Close anyway"])
        dialog.set_default_button(0)
        dialog.set_cancel_button(0)
        dialog.set_modal(True)

        def finished(source, result) -> None:
            self._confirming = False
            try:
                choice = source.choose_finish(result)
            except GLib.Error:
                choice = 0
            if choice == 1:
                on_confirmed()

        dialog.choose(self.window, None, finished)

    def _close_now(self) -> None:
        self._force_close = True
        self.window.close()

    def destroy(self) -> None:
        """Close without asking (Mochi shutdown). The shell gets SIGHUP."""
        self._force_close = True
        if not self._closed:
            self._finish_close()
            self.window.destroy()

    def _finish_close(self) -> None:
        """Release everything this window owns. Idempotent."""
        if self._closed:
            return
        self._closed = True
        self._position_serial += 1
        if self._settings is not None:
            for handler in self._settings_handlers:
                self._settings.disconnect(handler)
        self._settings_handlers = []
        callback, self._on_closed = self._on_closed, None
        if callback is not None:
            callback()

    # -- Clipboard and colours ------------------------------------------------------

    def _copy(self, *_args) -> bool:
        self.terminal.copy_clipboard_format(self._vte.Format.TEXT)
        return True

    def _paste(self, *_args) -> bool:
        self.terminal.paste_clipboard()
        return True

    def _on_theme_changed(self, *_args) -> None:
        # CSS recomputes after the setting changes; read the colour after that.
        GLib.idle_add(self._apply_palette)

    def _apply_palette(self) -> bool:
        if self._closed:
            return GLib.SOURCE_REMOVE
        foreground = self.window.get_color()
        fg, bg = palette_for_foreground(foreground.red, foreground.green, foreground.blue)
        self.terminal.set_colors(_rgba(fg), _rgba(bg), None)
        self.terminal.set_color_cursor(_rgba(CURSOR_COLOR))
        return GLib.SOURCE_REMOVE

    # -- Placement (same approach as FocusWindow) --------------------------------------

    def present(self) -> None:
        self._position_serial += 1
        serial = self._position_serial
        self.window.present()
        GLib.idle_add(self._position_if_current, serial)
        GLib.timeout_add(24, self._position_if_current, serial)

    def _on_map(self, _window) -> None:
        GLib.idle_add(self._position_if_current, self._position_serial)

    def _position_if_current(self, serial: int) -> bool:
        if serial != self._position_serial or not self.window.get_visible():
            return GLib.SOURCE_REMOVE
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            return GLib.SOURCE_REMOVE  # pure Wayland: the compositor places it
        owner_x, owner_y = owner_position
        scale = _window_coordinate_scale(self._owner)
        owner_width = max(1, self._owner.get_width())
        owner_height = max(1, self._owner.get_height())
        width = self.window.get_width()
        height = self.window.get_height()
        if width <= 1:
            width = self.DEFAULT_WIDTH
        if height <= 1:
            height = self.DEFAULT_HEIGHT
        monitors = self._owner.get_display().get_monitors()
        geometries = [monitors.get_item(index).get_geometry() for index in range(monitors.get_n_items())]
        x, y = _focus_window_position_for_anchor(
            owner_x + round(owner_width * scale / 2),
            owner_y + round(owner_height * scale / 2),
            owner_y,
            owner_height,
            width,
            height,
            geometries,
            coordinate_scale=scale,
            anchor_width=owner_width,
        )
        move_window(self.window, x, y)
        return GLib.SOURCE_REMOVE

    @classmethod
    def _install_css(cls, display: Gdk.Display | None) -> None:
        if display is None or hash(display) in cls._css_displays:
            return
        provider = Gtk.CssProvider()
        provider.load_from_string(QUICK_TERMINAL_CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        cls._css_displays.add(hash(display))
```

- [ ] **Step 4: Run them and see them pass**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_quick_terminal_window.py 2>&1 | tail -3
```

Expected: `14 passed` with VTE installed, or `13 passed, 1 skipped` without it.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/presence/quick_terminal_window.py tests/test_quick_terminal_window.py
git commit -m "feat: add the Quick Terminal window"
```

---

### Task 4: Menu row, lifecycle and wiring

**Files:**
- Create: `src/mochi/presence/quick_terminal_controls.py`
- Create: `tests/test_quick_terminal_controls.py`
- Modify: `src/mochi/presence/click_dialogue.py`

**Interfaces:**
- Consumes: Task 3; `_register_context_menu_row`, `_close_context_menu_then`, `_play_idle_beat`, `_curiosity_suppression`, the cooperative `_quit_application` (`integration.py:626` → `buddy_menu.py:636`) and `shutdown_presence`.
- Produces: `QuickTerminalMixin` with `_open_quick_terminal() -> bool`, `_quick_terminal`, and overrides of `_build_context_menu`, `_quit_application`, `shutdown_presence`.

**Acceptance Criteria:**
- The row `quick-terminal` is registered after `focus`; it is disabled with "Needs vte291-gtk4" when `load_vte()` is `None`.
- At most one window; reopening presents it.
- Quitting with a busy terminal asks first; quitting with an idle one quits at once.
- `QuickTerminalMixin` sits between `QuickStartMixin` and `FocusSessionMixin` in both buddy classes.
- `tests/test_context_menu_layout.py` and the full suite pass.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quick_terminal_controls.py`:

```python
"""QuickTerminalMixin: the menu row, one window at a time, quit and shutdown."""

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from mochi.presence import quick_terminal_controls as module
from mochi.presence.quick_terminal_controls import QuickTerminalMixin


class FakeWindow:
    instances: list["FakeWindow"] = []

    def __init__(self, *, owner, vte, on_closed, logger=None) -> None:
        self.on_closed = on_closed
        self.presented = 0
        self.busy = False
        self.confirm = None
        self.destroyed = 0
        FakeWindow.instances.append(self)

    def present(self):
        self.presented += 1

    def confirm_close(self, on_confirmed, *, quitting=False):
        self.confirm = (on_confirmed, quitting)

    def destroy(self):
        self.destroyed += 1


class _Base:
    def __init__(self, *args, **kwargs) -> None:
        self._window = object()
        self._logger = None
        self.rows: list[tuple] = []
        self.beats: list[str] = []
        self.calls: list[str] = []
        self.suppression = None

    def _build_context_menu(self):
        return "popover"

    def _register_context_menu_row(self, row_id, widget, *, after=None, before=None):
        self.rows.append((row_id, widget, after))

    def _close_context_menu_then(self, action):
        action()

    def _play_idle_beat(self, name):
        self.beats.append(name)
        return True

    def _curiosity_suppression(self):
        return self.suppression

    def _quit_application(self):
        self.calls.append("quit")

    def shutdown_presence(self):
        self.calls.append("shutdown")


class Harness(QuickTerminalMixin, _Base):
    pass


@pytest.fixture
def buddy(monkeypatch):
    FakeWindow.instances = []
    monkeypatch.setattr(module, "QuickTerminalWindow", FakeWindow)
    monkeypatch.setattr(module, "load_vte", lambda: object())
    return Harness()


def _labels(widget) -> list[str]:
    found = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            found.append(child.get_label())
        found.extend(_labels(child))
        child = child.get_next_sibling()
    return found


def test_row_sits_after_focus_and_is_enabled_with_vte(buddy):
    assert buddy._build_context_menu() == "popover"
    row_id, widget, after = buddy.rows[0]
    assert (row_id, after) == ("quick-terminal", "focus")
    assert widget.get_sensitive() is True
    assert _labels(widget) == ["Quick terminal"]


def test_row_is_disabled_with_a_hint_without_vte(buddy, monkeypatch):
    monkeypatch.setattr(module, "load_vte", lambda: None)
    buddy._build_context_menu()
    _, widget, _ = buddy.rows[0]
    assert widget.get_sensitive() is False
    assert _labels(widget) == ["Quick terminal", "Needs vte291-gtk4"]


def test_clicking_the_row_opens_one_window_and_reopening_presents_it(buddy):
    buddy._open_quick_terminal_from_menu()
    buddy._open_quick_terminal_from_menu()
    assert len(FakeWindow.instances) == 1
    assert FakeWindow.instances[0].presented == 2


def test_opening_waves_unless_mochi_is_busy(buddy):
    buddy._open_quick_terminal()
    assert buddy.beats == ["wave"]
    FakeWindow.instances[0].on_closed()
    buddy.suppression = "dragging"
    buddy._open_quick_terminal()
    assert buddy.beats == ["wave"]


def test_no_vte_means_no_window(buddy, monkeypatch):
    monkeypatch.setattr(module, "load_vte", lambda: None)
    assert buddy._open_quick_terminal() is False
    assert FakeWindow.instances == []


def test_closing_the_window_forgets_it(buddy):
    buddy._open_quick_terminal()
    FakeWindow.instances[0].on_closed()
    assert buddy._quick_terminal is None
    buddy._open_quick_terminal()
    assert len(FakeWindow.instances) == 2


def test_quit_with_an_idle_terminal_quits_right_away(buddy):
    buddy._open_quick_terminal()
    buddy._quit_application()
    assert buddy.calls == ["quit"]


def test_quit_with_a_running_command_asks_first(buddy):
    buddy._open_quick_terminal()
    terminal = FakeWindow.instances[0]
    terminal.busy = True
    buddy._quit_application()
    assert buddy.calls == []
    on_confirmed, quitting = terminal.confirm
    assert quitting is True
    on_confirmed()
    assert terminal.destroyed == 1
    assert buddy.calls == ["quit"]


def test_shutdown_destroys_the_window_once(buddy):
    buddy._open_quick_terminal()
    terminal = FakeWindow.instances[0]
    buddy.shutdown_presence()
    buddy.shutdown_presence()
    assert terminal.destroyed == 1
    assert buddy.calls == ["shutdown", "shutdown"]


def test_hooks_tolerate_objects_built_without_init():
    buddy = object.__new__(Harness)
    buddy.calls = []
    buddy.shutdown_presence()
    buddy._quit_application()
    assert buddy.calls == ["shutdown", "quit"]


def test_mixin_sits_between_quick_start_and_focus():
    from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
    from mochi.presence.focus_session import FocusSessionMixin
    from mochi.quick_start import QuickStartMixin

    for buddy_type in (PresenceBuddy, PresenceX11Buddy):
        mro = buddy_type.__mro__
        assert mro.index(QuickStartMixin) + 1 == mro.index(QuickTerminalMixin)
        assert mro.index(QuickTerminalMixin) + 1 == mro.index(FocusSessionMixin)
```

- [ ] **Step 2: Run them and see them fail**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_quick_terminal_controls.py 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'mochi.presence.quick_terminal_controls'`.

- [ ] **Step 3: Implement the mixin**

Create `src/mochi/presence/quick_terminal_controls.py`:

```python
"""Quick Terminal: open a small real terminal from Mochi's context menu.

The only way in is the menu row: no app action, D-Bus method, CLI flag or
agent event can open the terminal or send it text. Opening is direct
interaction, so quiet mode never blocks it.

Owns at most one QuickTerminalWindow and tears it down on shutdown (Manual
Rule 4). Quitting Mochi while a command runs asks first.
"""

from __future__ import annotations

from gi.repository import Gtk

from .quick_terminal_window import QuickTerminalWindow, load_vte


class QuickTerminalMixin:
    QUICK_TERMINAL_BEAT = "wave"

    def __init__(self, *args, **kwargs) -> None:
        self._quick_terminal: QuickTerminalWindow | None = None
        self._quick_terminal_row: Gtk.Button | None = None
        super().__init__(*args, **kwargs)

    # -- Menu ------------------------------------------------------------------

    def _build_context_menu(self):
        popover = super()._build_context_menu()
        row = self._make_quick_terminal_row()
        # Pocket -> Bond -> Feed -> Focus -> Quick terminal -> Sleep
        self._register_context_menu_row("quick-terminal", row, after="focus")
        return popover

    def _make_quick_terminal_row(self) -> Gtk.Button:
        available = load_vte() is not None
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("utilities-terminal-symbolic")
        icon.add_css_class("mochi-menu-icon")
        row.append(icon)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text.set_hexpand(True)
        label = Gtk.Label(label="Quick terminal")
        label.set_xalign(0)
        text.append(label)
        if available:
            button.set_tooltip_text("Open a small terminal next to Mochi")
        else:
            hint = Gtk.Label(label="Needs vte291-gtk4")
            hint.set_xalign(0)
            hint.add_css_class("mochi-menu-value")
            text.append(hint)
            button.set_sensitive(False)
            button.set_tooltip_text("Install the vte291-gtk4 package to use the quick terminal")
        row.append(text)
        button.set_child(row)
        button.connect("clicked", self._open_quick_terminal_from_menu)
        self._quick_terminal_row = button
        return button

    def _open_quick_terminal_from_menu(self, _button=None) -> None:
        self._close_context_menu_then(self._open_quick_terminal)

    # -- Window lifecycle ---------------------------------------------------------

    def _open_quick_terminal(self) -> bool:
        terminal = getattr(self, "_quick_terminal", None)
        if terminal is not None:
            terminal.present()  # one at a time
            return True
        vte = load_vte()
        window = getattr(self, "_window", None)
        if vte is None or window is None:
            return False
        self._quick_terminal = QuickTerminalWindow(
            owner=window,
            vte=vte,
            on_closed=self._on_quick_terminal_closed,
            logger=getattr(self, "_logger", None),
        )
        self._quick_terminal.present()
        suppression = getattr(self, "_curiosity_suppression", None)
        if not callable(suppression) or suppression() is None:
            self._play_idle_beat(self.QUICK_TERMINAL_BEAT)
        return True

    def _on_quick_terminal_closed(self) -> None:
        self._quick_terminal = None

    def _quit_application(self) -> None:
        terminal = getattr(self, "_quick_terminal", None)
        if terminal is not None and terminal.busy:
            terminal.present()
            terminal.confirm_close(lambda: self._quit_after_terminal(terminal), quitting=True)
            return
        super()._quit_application()

    def _quit_after_terminal(self, terminal: QuickTerminalWindow) -> None:
        terminal.destroy()
        super()._quit_application()

    def shutdown_presence(self) -> None:
        terminal = getattr(self, "_quick_terminal", None)
        self._quick_terminal = None
        if terminal is not None:
            terminal.destroy()
        super().shutdown_presence()
```

- [ ] **Step 4: Wire it into both buddies**

```diff
--- a/src/mochi/presence/click_dialogue.py
+++ b/src/mochi/presence/click_dialogue.py
@@ -25,6 +25,7 @@
 from .music_dance import MusicDanceMixin
 from .nameplate_controls import NameplateMixin
 from .phrases import bond_dialogue_lines
+from .quick_terminal_controls import QuickTerminalMixin
 from .terminal_cowork import TerminalCoworkMixin
 from .update_controls import UpdateControlsMixin

@@ -186,6 +187,7 @@
     IdleLookMixin,
     UpdateControlsMixin,
     QuickStartMixin,
+    QuickTerminalMixin,
     FocusSessionMixin,
     FedoraModeMixin,
     AgentCoworkMixin,
@@ -208,6 +210,7 @@
     IdleLookMixin,
     UpdateControlsMixin,
     QuickStartMixin,
+    QuickTerminalMixin,
     FocusSessionMixin,
     FedoraModeMixin,
     AgentCoworkMixin,
```

- [ ] **Step 5: Run the new tests, the neighbours, and the full suite**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_quick_terminal_controls.py tests/test_context_menu_layout.py tests/test_focus_session_mixin.py 2>&1 | tail -3
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: all pass; in the planning run the full suite reached 1394.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/presence/quick_terminal_controls.py src/mochi/presence/click_dialogue.py tests/test_quick_terminal_controls.py
git commit -m "feat: open a quick terminal from Mochi's menu"
```

---

### Task 5: Installer and CI package (owner may decline)

**Files:**
- Modify: `install.sh`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: new Fedora installs get `vte291-gtk4`; CI runs the real-VTE test instead of skipping it.

**Acceptance Criteria:**
- `bash -n install.sh` passes; `tests/test_installer.py` passes unchanged.
- Both changes are listed in the PR body so the owner can drop either one. Without them, the feature still works wherever VTE is already installed.

- [ ] **Step 1: Add the Fedora package**

```diff
--- a/install.sh
+++ b/install.sh
@@ -326,6 +326,7 @@
         python3-cairo
         gtk4
         gtk4-layer-shell
+        vte291-gtk4
         gstreamer1
         gstreamer1-plugins-base
         libX11
```

- [ ] **Step 2: Add the CI package**

```diff
--- a/.github/workflows/tests.yml
+++ b/.github/workflows/tests.yml
@@ -28,6 +28,7 @@
             python3-gi \
             python3-cairo \
             gir1.2-gtk-4.0 \
+            gir1.2-vte-3.91 \
             gsettings-desktop-schemas \
             libx11-6 \
             dbus \
```

- [ ] **Step 3: Verify and commit**

```bash
bash -n install.sh && echo "install.sh ok"
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_installer.py 2>&1 | tail -1
git add install.sh .github/workflows/tests.yml
git commit -m "chore: install VTE for Quick Terminal on Fedora and in CI"
```

---

### Task 6: Documentation and QA watchlist

**Files:**
- Modify: `CHANGELOG.md`, `README.md`, `docs/ambisense.md`, `docs/CODEBASE_MANUAL.md`, `REGRESSION_WATCHLIST.md`

**Interfaces:**
- Consumes: shipped behavior from Tasks 2–5.
- Produces: user and contributor docs.

**Acceptance Criteria:**
- CHANGELOG Unreleased → Added has one plain-language entry.
- README lists *Quick terminal* in the controls and names `vte291-gtk4` as optional.
- `docs/ambisense.md` says Mochi hosts but never reads the quick terminal.
- CODEBASE_MANUAL §6 layer list includes `QuickTerminalMixin`.
- REGRESSION_WATCHLIST has the spec's **Quick Terminal** section verbatim.
- `git diff --check` is clean.

- [ ] **Step 1: CHANGELOG**

Under `## Unreleased` → `### Added`:

```markdown
- A quick terminal: choose "Quick terminal" in Mochi's menu to open a small,
  real terminal right next to Mochi. It closes when you type `exit`, and it
  asks before closing (or quitting Mochi) while a command is still running.
  Mochi never reads what you type. It needs the `vte291-gtk4` package, which
  the installer now adds on Fedora.
```

- [ ] **Step 2: README, ambisense.md, manual, watchlist**

Make the changes listed in the acceptance criteria. Copy the watchlist items from the spec's Documentation section.

- [ ] **Step 3: Commit**

```bash
git diff --check && git add CHANGELOG.md README.md docs/ambisense.md docs/CODEBASE_MANUAL.md REGRESSION_WATCHLIST.md
git commit -m "docs: document Quick Terminal and add its QA checklist"
```

---

### Task 7: Final verification, push and draft PR

**Files:** none.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: the pushed branch and a draft PR against `main`.

**Acceptance Criteria:**
- Full suite, `compileall`, `bash -n install.sh` and `git diff --check` pass locally.
- A headless smoke of the real app opens the terminal from the menu path, sees a shell, and shuts down cleanly.
- The PR body follows `.github/pull_request_template.md`, lists the owner's manual QA, and calls out Task 5 as optional.

- [ ] **Step 1: Run CI's checks locally**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
python3.12 -m compileall -q src tests && echo "compileall ok"
bash -n install.sh && echo "install.sh ok"
git diff --check origin/main...HEAD && echo "whitespace ok"
```

- [ ] **Step 2: Review the diff adversarially**

```bash
git diff origin/main...HEAD -- src install.sh .github
```

Check specifically:
- the only caller of `QuickTerminalWindow` is `_open_quick_terminal`, and the only caller of that is the menu row;
- `spawn_async` receives `shell_argv(shell)` and nothing else as argv;
- no `.get_text`, no `markup=`, and no logging of terminal data;
- every `Gtk.Settings` handler is disconnected in `_finish_close`.

- [ ] **Step 3: Smoke the real app headless (not committed)**

Start Mochi under `xvfb-run` and `dbus-run-session` with isolated XDG directories, as the curiosity plan's Task 7 did. Call `buddy._open_quick_terminal()`, wait for `buddy._quick_terminal._shell_pid`, feed `exit\n`, and confirm `buddy._quick_terminal is None`. Then shut down and confirm there is no traceback.

- [ ] **Step 4: Push and open a draft PR**

```bash
git push -u origin claude/quick-terminal
```

PR body sections: Summary, Scope, Verification (actual counts), Runtime / lifecycle notes (one window, cleanup on close, quit confirmation, no external entry point), Environment tested (headless only), Notes (owner QA list; Task 5 is optional).

---

## Stress Test Results: Implementation Plan

### Resolved Decisions

- **Prototype before plan:** every task's code was run against a clean copy of `main` while writing this plan, including a real VTE session.
- **Cleanup timing** (found while prototyping): with GTK 4's `destroy` signal tied to dispose, cleanup runs on the allowed close and in `destroy()`. Tests cover shell exit, idle close, busy close and repeated `destroy()`.
- **Test fixture realism** (found while prototyping): GTK ignores `close()` on an unrealized window, so the fixture presents the window first, as real use does.
- **Mixin placement:** between `QuickStartMixin` and `FocusSessionMixin`, so the `focus` row exists before this mixin registers after it; a test pins it.
- **CI coverage:** the real-VTE test skips without VTE; Task 5 adds the CI package so it runs there.

### Changes Made

- The window module moved to `presence/` so it can reuse the Focus window's placement helper.
- The source test looks for calls (`.get_text`, `markup=`) rather than words, so docstrings can describe the rule.

### Deferred / Parking Lot

- A terminal-coworking scene while the quick terminal is focused.
- A keyboard shortcut.
- Launching the user's terminal as a fallback when VTE is missing.

### Confidence Assessment

- **High** for Tasks 2–5: all code was run, including against real VTE.
- **Medium** for live behavior on GNOME: XWayland rendering, dialog stacking, and Fedora packaging need owner QA.
