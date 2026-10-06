# Pocket Hover Tray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use beads-superpowers:subagent-driven-development (recommended) or beads-superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent <epic-id>`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.

**Goal:** Resting the pointer on Mochi for 2 s opens a small Pocket tray, with a filling "peek" bar on the way. From the tray you can open, copy, show in folder, view text, or drag an item into another app. The context menu's `Pocket · N` opens the same tray with keyboard focus.

**Architecture:** Five units, each tested on its own:

- A GTK-free `PocketHoverDwell` state machine owns arming, peek, open, close and re-arm, and its three timers.
- A GTK `PocketTray` window owns the peek and tray views, the rows, drag sources, clipboard writes and inline feedback.
- `PocketController.begin_offer()` plays a short mouth animation through the shared `EXCITED` transition path.
- New guard tables in `behavior.py` decide which states may arm the dwell and which may play the offer.
- `PocketBuddyMixin` composes everything by extending the pointer handlers through `super()`.

No new `MochiState`, no new art, no new dependency.

**Tech Stack:** Python 3.11+, GTK 4 / PyGObject (`Gtk.DragSource`, `Gdk.ContentProvider`, `Gdk.FileList`, `Gdk.Clipboard`), GLib timers, Cairo-free, pytest under Xvfb.

**Spec:** `docs/superpowers/specs/2026-10-06-pocket-hover-tray-design.md`

## Global Constraints

- **No new runtime dependencies.** `pyproject.toml` keeps `dependencies = []`.
- **No network, no telemetry.** The clipboard is written only on an explicit click and never read.
- **No speech.** Feedback goes through the existing `_show_pocket_feedback` (nameplate) and inline row labels only. Never call `set_markup` with item text.
- **Rule 1.** Behavior transitions only through the injected `transition` callable (`Buddy._transition_to`). The offer claims `MochiState.EXCITED`; there is no new state.
- **Rule 3.** The arm and offer state tables live only in `behavior.py`.
- **Rule 4.** Every GLib source and tick callback has one owner and is removed in `close()`, `destroy()` or `shutdown()`.
- **Launching.** URIs come only from `pocket_actions.launch_uri_for` and `folder_uri_for`, and go through `Gio.AppInfo.launch_default_for_uri`. No shell.
- **Drag-out.** Offers `Gdk.DragAction.COPY` only. In-process drags are refused by `PocketDropAdapter`.
- **Constants (exact values):**
  - `POCKET_HOVER_DELAY_CHOICES_MS = (0, 1500, 2000, 3000)`
  - `DEFAULT_POCKET_HOVER_DELAY_MS = 2000`
  - `POCKET_PEEK_DELAY_MS = 600`
  - `POCKET_TRAY_CLOSE_GRACE_MS = 450`
  - `TRAY_WIDTH = 360`
  - `TRAY_GAP_PX = 8`
  - `TRAY_MAX_LIST_HEIGHT = 480`
  - `TRAY_FEEDBACK_MS = 1500`
  - `PEEK_WIDTH = 150`
  - config key `pocket_hover_delay_ms`
- **Copy (exact strings):**
  - `"Open by resting on Mochi"`
  - `"Manage Pocket…"`
  - `"Click to open, or drag it out"`
  - `"Nothing in here yet. Drag a file, link, image, or text onto Mochi."`
  - `"Couldn't open it. It's still here."`
  - `"Copied"`
  - dropdown labels `("Off", "1.5 s", "2 s", "3 s")`
- **Test command.** CI installs `python3-pytest python3-gi python3-cairo gir1.2-gtk-4.0 gsettings-desktop-schemas libx11-6 xvfb` and runs `xvfb-run -a python3 -m pytest -q`. In a fresh cloud container, install those with `apt-get` first, then run:
  - `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider <paths>`
- **Baseline** on `main` @ `4713426` (2026-10-06): **1363 passed, 6 skipped**.
- **Commits.** Commits end with the attribution trailer the executing session is configured with. `bd` is not installed in this container; track tasks with the checkboxes below.
- **Branch.** Work on the branch the executing session is assigned. Do not touch the updater, `src/mochi_launcher.py`, or GDK backend selection.

## File Map

| File | Responsibility | Task |
|---|---|---|
| `src/mochi/behavior.py` | `POCKET_HOVER_ARM_STATES`, `can_arm_pocket_hover`, `POCKET_OFFER_STATES`, `can_start_pocket_offer` | 1 |
| `src/mochi/sprites.py` | `pocket_offer` = `pocket_grab` frames 4–8, one-shot | 1 |
| `src/mochi/pocket_controller.py` | `begin_offer()` | 1 |
| `tests/test_pocket_controller.py`, `tests/test_sprites.py` | Guard tables, offer, animation shape | 1 |
| `src/mochi/pocket_hover.py` (new) | `PocketHoverDwell`, delay constants, `normalize_hover_delay_ms` | 2 |
| `tests/test_pocket_hover.py` (new) | Dwell rules with a fake clock | 2 |
| `src/mochi/pocket_actions.py` (new) | `launch_uri_for`, `folder_uri_for` | 3 |
| `src/mochi/pocket_window.py` | Use `pocket_actions` (no behavior change) | 3 |
| `tests/test_pocket_actions.py` (new) | URI rules | 3 |
| `src/mochi/x11.py` | `request_no_focus_on_map` | 4 |
| `src/mochi/pocket_tray.py` (new) | Placement, row models, content providers, `PocketTray` | 4 |
| `tests/test_pocket_tray.py` (new) | Tray behavior under Xvfb | 4 |
| `src/mochi/config.py` | `load/save_pocket_hover_delay_ms` | 5 |
| `src/mochi/pocket_window.py` | "Open by resting on Mochi" dropdown | 5 |
| `tests/test_config.py`, `tests/test_pocket_window.py` | Setting persistence and UI | 5 |
| `src/mochi/pocket_integration.py` | Compose dwell + tray + offer + menu + setting + teardown | 6 |
| `src/mochi/pocket_drop.py` | Refuse in-process drags | 6 |
| `tests/test_pocket_integration.py`, `tests/test_pocket_drop.py` | Wiring and guard | 6 |
| `CHANGELOG.md`, `README.md`, `REGRESSION_WATCHLIST.md`, `docs/CODEBASE_MANUAL.md` | User and maintainer docs | 7 |

---

### Task 1: Guard tables, `pocket_offer`, and `begin_offer()`

**Files:**
- Modify: `src/mochi/behavior.py` (after `can_start_pocket_receive`, around line 64)
- Modify: `src/mochi/sprites.py` (after `ANIMATIONS["pocket_finish"]`, around line 142)
- Modify: `src/mochi/pocket_controller.py`
- Test: `tests/test_pocket_controller.py`, `tests/test_sprites.py`

**Interfaces:**
- Consumes: `POCKET_RECEIVE_STATES` and `can_start_pocket_receive` (existing).
- Produces:
  - `behavior.POCKET_HOVER_ARM_STATES: frozenset[MochiState]`
  - `behavior.can_arm_pocket_hover(state: MochiState) -> bool`
  - `behavior.POCKET_OFFER_STATES: frozenset[MochiState]`
  - `behavior.can_start_pocket_offer(state: MochiState) -> bool`
  - `ANIMATIONS["pocket_offer"]`
  - `PocketController.begin_offer() -> bool`

**Acceptance Criteria:**
- Arm-allowed states are exactly `IDLE`, `BLINKING`, `IDLE_EMOTE`, `HEART`, `COMPUTER`, `TYPING`, `WATCHING`, `DANCING`, `SEARCHING`, `SLEEPING`, `WAKING`.
- Offer-allowed states are exactly `POCKET_RECEIVE_STATES ∪ {HEART}`.
- `begin_offer()` from `HEART` records `cancel-ambient`, `transition:EXCITED`, `mark-interaction`, `play:pocket_offer:idle` in that order and writes nothing.
- `begin_offer()` returns `False` with no side effects for protected states, while `busy`, and while a drag-in hover is active.
- A rejected `EXCITED` transition returns `False` and plays nothing.
- `pocket_offer` is frames 4, 5, 6, 7, 8 at 120 ms, not looping, `next_state == "idle"`.
- `can_transition()` is unchanged.

- [ ] **Step 1: Write the failing guard and offer tests**

Change the import at the top of `tests/test_pocket_controller.py`:

```python
from mochi.behavior import (
    can_arm_pocket_hover,
    can_start_pocket_offer,
    can_start_pocket_receive,
    can_transition,
)
```

Append to `tests/test_pocket_controller.py`:

```python
HOVER_ARM_STATES = {
    MochiState.IDLE,
    MochiState.BLINKING,
    MochiState.IDLE_EMOTE,
    MochiState.HEART,
    MochiState.COMPUTER,
    MochiState.TYPING,
    MochiState.WATCHING,
    MochiState.DANCING,
    MochiState.SEARCHING,
    MochiState.SLEEPING,
    MochiState.WAKING,
}


@pytest.mark.parametrize("state", tuple(MochiState))
def test_hover_tray_arms_only_from_calm_ambient_or_sleep_states(
    state: MochiState,
) -> None:
    assert can_arm_pocket_hover(state) is (state in HOVER_ARM_STATES)


@pytest.mark.parametrize("state", tuple(MochiState))
def test_offer_may_replace_receive_states_and_the_hover_heart(
    state: MochiState,
) -> None:
    expected = can_start_pocket_receive(state) or state is MochiState.HEART
    assert can_start_pocket_offer(state) is expected


def test_offer_cancels_the_hover_heart_before_claiming_excited() -> None:
    store = _Store()
    interaction = _Interaction(MochiState.HEART)
    controller = _controller(store, interaction)

    assert controller.begin_offer() is True

    assert interaction.events == [
        "cancel-ambient",
        "transition:EXCITED",
        "mark-interaction",
        "play:pocket_offer:idle",
    ]
    assert interaction.state is MochiState.EXCITED
    assert store.events == []
    assert interaction.feedback == []


def test_offer_cancels_a_walk_instead_of_an_emote() -> None:
    interaction = _Interaction(MochiState.WALKING)
    controller = _controller(_Store(), interaction)

    assert controller.begin_offer() is True

    assert interaction.events[0] == "cancel-walk"
    assert "cancel-ambient" not in interaction.events


@pytest.mark.parametrize(
    "state",
    (
        MochiState.SLEEPING,
        MochiState.WAKING,
        MochiState.PICKUP,
        MochiState.DRAGGED,
        MochiState.DROPPING,
        MochiState.FEDORA,
        MochiState.EATING,
        MochiState.EXCITED,
        MochiState.BOUNCING,
        MochiState.SQUISHING,
    ),
)
def test_offer_never_claims_protected_or_direct_owned_states(
    state: MochiState,
) -> None:
    interaction = _Interaction(state)
    controller = _controller(_Store(), interaction)

    assert controller.begin_offer() is False

    assert interaction.events == []
    assert interaction.state is state


def test_offer_is_skipped_while_a_drag_in_owns_pocket() -> None:
    interaction = _Interaction(MochiState.IDLE)
    controller = _controller(_Store(), interaction)
    assert controller.begin_hover() is True
    interaction.events.clear()

    assert controller.begin_offer() is False
    assert interaction.events == []


def test_rejected_offer_transition_plays_nothing() -> None:
    interaction = _Interaction(MochiState.IDLE)

    def reject(state: MochiState) -> bool:
        interaction.events.append(f"transition:{state.name}")
        return False

    interaction.transition = reject
    controller = _controller(_Store(), interaction)

    assert controller.begin_offer() is False
    assert interaction.events == ["cancel-ambient", "transition:EXCITED"]
```

In `tests/test_sprites.py`, add this method to the same `TestCase` class that holds `test_pocket_finish_closes_without_restarting_the_full_animation`:

```python
    def test_pocket_offer_opens_and_closes_the_mouth_once(self) -> None:
        offer = ANIMATIONS["pocket_offer"]

        self.assertEqual(
            tuple(frame.sprite for frame in offer.frames),
            tuple(
                f"pocket_grab/mochi_pocket_grab_{index:04}.png"
                for index in (4, 5, 6, 7, 8)
            ),
        )
        self.assertEqual(offer.frame_duration_ms, 120)
        self.assertFalse(offer.looping)
        self.assertEqual(offer.next_state, "idle")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_controller.py tests/test_sprites.py`

Expected: collection error `ImportError: cannot import name 'can_arm_pocket_hover'`. After Step 3 the sprite test still fails with `KeyError: 'pocket_offer'` until Step 4.

- [ ] **Step 3: Add the guard tables to `src/mochi/behavior.py`**

Insert directly after `can_start_pocket_receive()`:

```python
# Resting the pointer on Mochi may open the Pocket tray from calm, ambient,
# and sleep-adjacent states. Hover already wakes a sleeping Mochi, so the tray
# never waits for the wake animation. Movement, held, Fedora, another direct
# reaction, and an in-progress Pocket receive keep ownership.
POCKET_HOVER_ARM_STATES = frozenset(
    (
        MochiState.IDLE,
        MochiState.BLINKING,
        MochiState.IDLE_EMOTE,
        MochiState.HEART,
        MochiState.COMPUTER,
        MochiState.TYPING,
        MochiState.WATCHING,
        MochiState.DANCING,
        MochiState.SEARCHING,
        MochiState.SLEEPING,
        MochiState.WAKING,
    )
)

# The tray's mouth animation may interrupt everything Pocket receive may, plus
# the hover heart, which is usually still playing when a 2 s dwell completes.
POCKET_OFFER_STATES = POCKET_RECEIVE_STATES | {MochiState.HEART}


def can_arm_pocket_hover(state: MochiState) -> bool:
    """Return whether resting on Mochi may start counting toward the tray."""
    return state in POCKET_HOVER_ARM_STATES


def can_start_pocket_offer(state: MochiState) -> bool:
    """Return whether the tray-opening mouth animation may claim presentation."""
    return state in POCKET_OFFER_STATES
```

- [ ] **Step 4: Add `pocket_offer` to `src/mochi/sprites.py`**

Insert directly after the `ANIMATIONS["pocket_finish"] = replace(...)` block:

```python
# The Pocket tray comes out of Mochi's mouth: open, then close, once.
ANIMATIONS["pocket_offer"] = replace(
    ANIMATIONS["pocket_grab"],
    name="pocket_offer",
    frames=tuple(pocket_grab_frames[index - 1] for index in (4, 5, 6, 7, 8)),
    looping=False,
    next_state="idle",
)
```

- [ ] **Step 5: Add `begin_offer()` to `src/mochi/pocket_controller.py`**

Change the behavior import:

```python
from mochi.behavior import can_start_pocket_offer, can_start_pocket_receive
```

Add this method directly after `end_hover()`:

```python
    def begin_offer(self) -> bool:
        """Play the short mouth-open reaction as the Pocket tray comes out.

        Presentation only: the caller opens the tray whether or not this
        succeeds, and nothing is written.
        """
        if self._busy or self._hover_active:
            return False
        state = self._current_state()
        if not can_start_pocket_offer(state):
            return False
        if state is MochiState.WALKING:
            self._cancel_walk()
        else:
            self._cancel_ambient()
        if not self._transition(MochiState.EXCITED):
            self._logger.warning(
                "Pocket offer presentation was rejected from %s",
                self._current_state().name,
            )
            return False
        self._mark_interaction()
        self._play_animation("pocket_offer", "idle")
        return True
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_controller.py tests/test_sprites.py tests/test_behavior*.py`

Expected: all pass (the `tests/test_behavior*.py` glob may match nothing; that is fine).

- [ ] **Step 7: Commit**

```bash
git add src/mochi/behavior.py src/mochi/sprites.py src/mochi/pocket_controller.py tests/test_pocket_controller.py tests/test_sprites.py
git commit -m "feat(pocket): offer animation and hover-tray state guards"
```

---

### Task 2: `PocketHoverDwell`

**Files:**
- Create: `src/mochi/pocket_hover.py`
- Test: `tests/test_pocket_hover.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces (`mochi.pocket_hover`):
  - `POCKET_HOVER_DELAY_CHOICES_MS`, `DEFAULT_POCKET_HOVER_DELAY_MS`, `POCKET_PEEK_DELAY_MS`, `POCKET_TRAY_CLOSE_GRACE_MS`
  - `normalize_hover_delay_ms(value: object) -> int`
  - `DwellPhase` with `IDLE`, `ARMED`, `PEEK`, `OPEN`
  - `PocketHoverDwell(*, delay_ms, can_arm, show_peek, hide_peek, open_tray, close_tray, timeout_add=None, source_remove=None)`, where:
    - `delay_ms: Callable[[], int]`
    - `can_arm: Callable[[], bool]`
    - `show_peek: Callable[[int], None]` receives the remaining fill in ms
    - `hide_peek: Callable[[], None]`
    - `open_tray: Callable[[bool], bool]` receives `focus` and returns whether the tray opened
    - `close_tray: Callable[[], None]`
  - Properties: `phase -> DwellPhase`, `pinned -> bool`.
  - Methods, all returning `None` except `open_pinned() -> bool`:
    - `pointer_entered()`, `pointer_moved()`, `pointer_left()`
    - `tray_entered()`, `tray_left()`
    - `interrupt()`
    - `drag_started()`, `drag_finished(delivered: bool)`
    - `open_pinned()`, `close()`, `shutdown()`

**Acceptance Criteria:**
- Enter alone never arms; the first motion arms.
- The peek is due at `min(600, delay)` with fill `delay − 600`; the tray opens at `delay`.
- Leaving, Off, `can_arm` false at any due point, and interrupt all reset silently (hiding a visible peek).
- Repeated motion never restarts the dwell.
- Re-arm rule: after open or close with the pointer on Mochi, nothing arms until `pointer_left()`.
- A hover tray closes 450 ms after the pointer leaves both Mochi and the tray; entering either cancels that.
- A drag suppresses the grace close. A delivered drag closes; a cancelled drag reschedules the grace close.
- A pinned (menu) tray ignores pointer and tray leave, and closes only through `close()` or `interrupt()`.
- A failed open hides the peek and waits for leave.
- `shutdown()` leaves no pending source.
- `normalize_hover_delay_ms` accepts only `0, 1500, 2000, 3000` ints (not bools); anything else gives `2000`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pocket_hover.py`:

```python
"""Pocket hover dwell rules, driven by a deterministic clock."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mochi.pocket_hover import (
    DEFAULT_POCKET_HOVER_DELAY_MS,
    DwellPhase,
    PocketHoverDwell,
    normalize_hover_delay_ms,
)


class _Clock:
    """Stand-in for GLib.timeout_add/source_remove with manual time."""

    def __init__(self) -> None:
        self.now = 0
        self._next_id = 1
        self.pending: dict[int, tuple[int, Callable[[], bool]]] = {}

    def timeout_add(self, delay_ms: int, callback: Callable[[], bool]) -> int:
        source_id = self._next_id
        self._next_id += 1
        self.pending[source_id] = (self.now + delay_ms, callback)
        return source_id

    def source_remove(self, source_id: int) -> bool:
        assert source_id in self.pending, f"removed unknown source {source_id}"
        del self.pending[source_id]
        return True

    def advance(self, delta_ms: int) -> None:
        target = self.now + delta_ms
        while True:
            due = sorted(
                (when, source_id)
                for source_id, (when, _callback) in self.pending.items()
                if when <= target
            )
            if not due:
                break
            when, source_id = due[0]
            _when, callback = self.pending.pop(source_id)
            self.now = when
            assert callback() is False, "dwell timers are one-shot"
        self.now = target


class _Harness:
    def __init__(
        self,
        *,
        delay_ms: int = 2000,
        can_arm: bool = True,
        open_ok: bool = True,
    ) -> None:
        self.clock = _Clock()
        self.delay = delay_ms
        self.allowed = can_arm
        self.open_ok = open_ok
        self.events: list[str] = []
        self.dwell = PocketHoverDwell(
            delay_ms=lambda: self.delay,
            can_arm=lambda: self.allowed,
            show_peek=lambda fill_ms: self.events.append(f"peek:{fill_ms}"),
            hide_peek=lambda: self.events.append("hide-peek"),
            open_tray=self._open,
            close_tray=lambda: self.events.append("close"),
            timeout_add=self.clock.timeout_add,
            source_remove=self.clock.source_remove,
        )

    def _open(self, focus: bool) -> bool:
        self.events.append("open:focus" if focus else "open:hover")
        return self.open_ok

    def rest(self) -> None:
        self.dwell.pointer_entered()
        self.dwell.pointer_moved()

    def open_by_hover(self) -> None:
        self.rest()
        self.clock.advance(self.delay)
        assert self.dwell.phase is DwellPhase.OPEN
        self.events.clear()


def test_enter_without_motion_never_arms() -> None:
    harness = _Harness()
    harness.dwell.pointer_entered()

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.dwell.phase is DwellPhase.IDLE


def test_motion_peeks_at_600_ms_then_opens_at_the_dwell() -> None:
    harness = _Harness()
    harness.rest()

    harness.clock.advance(599)
    assert harness.events == []
    harness.clock.advance(1)
    assert harness.events == ["peek:1400"]
    assert harness.dwell.phase is DwellPhase.PEEK
    harness.clock.advance(1399)
    assert harness.events == ["peek:1400"]
    harness.clock.advance(1)

    assert harness.events == ["peek:1400", "open:hover"]
    assert harness.dwell.phase is DwellPhase.OPEN
    assert harness.dwell.pinned is False
    assert harness.clock.pending == {}


@pytest.mark.parametrize(("delay", "fill"), ((1500, 900), (3000, 2400)))
def test_peek_fills_for_the_rest_of_the_chosen_dwell(delay: int, fill: int) -> None:
    harness = _Harness(delay_ms=delay)
    harness.rest()

    harness.clock.advance(delay)

    assert harness.events == [f"peek:{fill}", "open:hover"]


def test_leaving_during_the_peek_hides_it_and_resets() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(1000)

    harness.dwell.pointer_left()
    harness.clock.advance(5000)

    assert harness.events == ["peek:1400", "hide-peek"]
    assert harness.dwell.phase is DwellPhase.IDLE
    assert harness.clock.pending == {}


def test_leaving_before_the_peek_resets_silently() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(300)

    harness.dwell.pointer_left()
    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.clock.pending == {}


def test_off_never_arms() -> None:
    harness = _Harness(delay_ms=0)
    harness.rest()

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.clock.pending == {}


def test_blocked_motion_never_arms() -> None:
    harness = _Harness(can_arm=False)
    harness.rest()

    harness.clock.advance(5000)

    assert harness.events == []


def test_condition_lost_before_the_peek_resets_without_showing_it() -> None:
    harness = _Harness()
    harness.rest()
    harness.allowed = False

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.dwell.phase is DwellPhase.IDLE
    assert harness.clock.pending == {}


def test_condition_lost_during_the_peek_hides_it_at_the_open_point() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(600)
    harness.allowed = False

    harness.clock.advance(1400)

    assert harness.events == ["peek:1400", "hide-peek"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_setting_turned_off_mid_dwell_cancels_at_the_next_due_point() -> None:
    harness = _Harness()
    harness.rest()
    harness.delay = 0

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.clock.pending == {}


def test_repeated_motion_does_not_restart_the_dwell() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(1000)
    for _ in range(3):
        harness.dwell.pointer_moved()

    harness.clock.advance(1000)

    assert harness.events == ["peek:1400", "open:hover"]


def test_no_reopen_loop_until_the_pointer_leaves() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.close()
    assert harness.events == ["close"]

    harness.dwell.pointer_moved()
    harness.clock.advance(5000)
    assert harness.events == ["close"]

    harness.dwell.pointer_left()
    harness.rest()
    harness.clock.advance(2000)
    assert harness.events == ["close", "peek:1400", "open:hover"]


def test_leaving_mochi_and_the_tray_closes_after_the_grace() -> None:
    harness = _Harness()
    harness.open_by_hover()

    harness.dwell.pointer_left()
    harness.clock.advance(449)
    assert harness.events == []
    harness.clock.advance(1)

    assert harness.events == ["close"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_crossing_into_the_tray_keeps_it_open() -> None:
    harness = _Harness()
    harness.open_by_hover()

    harness.dwell.pointer_left()
    harness.clock.advance(200)
    harness.dwell.tray_entered()
    harness.clock.advance(1000)
    assert harness.events == []

    harness.dwell.tray_left()
    harness.clock.advance(450)
    assert harness.events == ["close"]


def test_returning_to_mochi_cancels_the_grace_close() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.pointer_left()
    harness.clock.advance(200)

    harness.dwell.pointer_entered()
    harness.clock.advance(1000)

    assert harness.events == []
    assert harness.dwell.phase is DwellPhase.OPEN


def test_press_resets_arming_and_waits_for_leave() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(1000)

    harness.dwell.interrupt()
    harness.dwell.pointer_moved()
    harness.clock.advance(3000)
    assert harness.events == ["peek:1400", "hide-peek"]

    harness.dwell.pointer_left()
    harness.rest()
    harness.clock.advance(2000)
    assert harness.events[-1] == "open:hover"


def test_press_closes_a_hover_tray() -> None:
    harness = _Harness()
    harness.open_by_hover()

    harness.dwell.interrupt()

    assert harness.events == ["close"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_drag_out_suppresses_the_grace_close() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.pointer_left()
    harness.dwell.tray_entered()

    harness.dwell.drag_started()
    harness.dwell.tray_left()
    harness.clock.advance(2000)
    assert harness.events == []

    harness.dwell.drag_finished(False)
    harness.clock.advance(450)
    assert harness.events == ["close"]


def test_delivered_drag_closes_the_tray() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.drag_started()

    harness.dwell.drag_finished(True)

    assert harness.events == ["close"]


def test_menu_tray_ignores_pointer_leave() -> None:
    harness = _Harness()

    assert harness.dwell.open_pinned() is True
    assert harness.events == ["open:focus"]
    assert harness.dwell.pinned is True
    harness.dwell.pointer_entered()
    harness.dwell.pointer_left()
    harness.dwell.tray_left()
    harness.clock.advance(5000)
    assert harness.events == ["open:focus"]

    harness.dwell.close()
    assert harness.events == ["open:focus", "close"]
    assert harness.dwell.pinned is False


def test_failed_open_hides_the_peek_and_waits_for_leave() -> None:
    harness = _Harness(open_ok=False)
    harness.rest()

    harness.clock.advance(2000)
    harness.dwell.pointer_moved()
    harness.clock.advance(3000)

    assert harness.events == ["peek:1400", "open:hover", "hide-peek"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_shutdown_cancels_every_timer() -> None:
    harness = _Harness()
    harness.rest()
    harness.dwell.shutdown()
    assert harness.clock.pending == {}

    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.pointer_left()
    harness.dwell.shutdown()
    assert harness.clock.pending == {}
    assert harness.dwell.phase is DwellPhase.IDLE


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (0, 0),
        (1500, 1500),
        (2000, 2000),
        (3000, 3000),
        (2500, DEFAULT_POCKET_HOVER_DELAY_MS),
        (-1, DEFAULT_POCKET_HOVER_DELAY_MS),
        (True, DEFAULT_POCKET_HOVER_DELAY_MS),
        ("2000", DEFAULT_POCKET_HOVER_DELAY_MS),
        (None, DEFAULT_POCKET_HOVER_DELAY_MS),
    ),
)
def test_only_supported_delays_survive_normalization(raw, expected: int) -> None:
    assert normalize_hover_delay_ms(raw) == expected
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_hover.py`

Expected: `ModuleNotFoundError: No module named 'mochi.pocket_hover'`.

- [ ] **Step 3: Implement `src/mochi/pocket_hover.py`**

```python
"""GTK-free hover dwell that opens Mochi's Pocket tray.

Resting the pointer on Mochi arms a short dwell. A peek bar appears partway
through, and the tray opens when the dwell completes. Every collaborator is
injected, so the rules are testable without a display. This object owns its
three timers (peek, open, close) and cancels them in shutdown().
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto

POCKET_HOVER_DELAY_CHOICES_MS = (0, 1500, 2000, 3000)
DEFAULT_POCKET_HOVER_DELAY_MS = 2000
POCKET_PEEK_DELAY_MS = 600
POCKET_TRAY_CLOSE_GRACE_MS = 450

TimeoutAdd = Callable[[int, Callable[[], bool]], int]
SourceRemove = Callable[[int], object]


def normalize_hover_delay_ms(value: object) -> int:
    """Return a supported dwell in milliseconds; 0 means off."""
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_POCKET_HOVER_DELAY_MS
    if value not in POCKET_HOVER_DELAY_CHOICES_MS:
        return DEFAULT_POCKET_HOVER_DELAY_MS
    return value


class DwellPhase(Enum):
    IDLE = auto()
    ARMED = auto()
    PEEK = auto()
    OPEN = auto()


class PocketHoverDwell:
    """Arm, peek, open, and close the Pocket tray from pointer events."""

    def __init__(
        self,
        *,
        delay_ms: Callable[[], int],
        can_arm: Callable[[], bool],
        show_peek: Callable[[int], None],
        hide_peek: Callable[[], None],
        open_tray: Callable[[bool], bool],
        close_tray: Callable[[], None],
        timeout_add: TimeoutAdd | None = None,
        source_remove: SourceRemove | None = None,
    ) -> None:
        if timeout_add is None or source_remove is None:
            from gi.repository import GLib

            timeout_add = timeout_add or GLib.timeout_add
            source_remove = source_remove or GLib.source_remove
        self._delay_ms = delay_ms
        self._can_arm = can_arm
        self._show_peek = show_peek
        self._hide_peek = hide_peek
        self._open_tray = open_tray
        self._close_tray = close_tray
        self._timeout_add = timeout_add
        self._source_remove = source_remove
        self._sources: dict[str, int] = {}
        self._phase = DwellPhase.IDLE
        self._armed_delay_ms = 0
        self._pinned = False
        self._over_mochi = False
        self._over_tray = False
        self._needs_leave = False
        self._dragging = False

    @property
    def phase(self) -> DwellPhase:
        return self._phase

    @property
    def pinned(self) -> bool:
        return self._pinned

    def pointer_entered(self) -> None:
        self._over_mochi = True
        self._cancel("close")

    def pointer_moved(self) -> None:
        """Arm on real motion only: a window moving under a still pointer is not a reach."""
        self._over_mochi = True
        if self._phase is not DwellPhase.IDLE or self._needs_leave:
            return
        if not self._allowed():
            return
        self._armed_delay_ms = self._delay_ms()
        self._phase = DwellPhase.ARMED
        self._schedule(
            "peek",
            min(POCKET_PEEK_DELAY_MS, self._armed_delay_ms),
            self._on_peek_due,
        )
        self._schedule("open", self._armed_delay_ms, self._on_open_due)

    def pointer_left(self) -> None:
        self._over_mochi = False
        self._needs_leave = False
        if self._phase in (DwellPhase.ARMED, DwellPhase.PEEK):
            self._reset_arming()
        elif self._phase is DwellPhase.OPEN and not self._pinned:
            self._schedule_close()

    def tray_entered(self) -> None:
        self._over_tray = True
        self._cancel("close")

    def tray_left(self) -> None:
        self._over_tray = False
        if self._phase is DwellPhase.OPEN and not self._pinned:
            self._schedule_close()

    def interrupt(self) -> None:
        """A press, right-click, or drag on Mochi wins over the Pocket."""
        if self._phase in (DwellPhase.ARMED, DwellPhase.PEEK):
            self._reset_arming()
        elif self._phase is DwellPhase.OPEN:
            self.close()
        self._needs_leave = self._over_mochi

    def drag_started(self) -> None:
        self._dragging = True
        self._cancel("close")

    def drag_finished(self, delivered: bool) -> None:
        self._dragging = False
        if self._phase is not DwellPhase.OPEN:
            return
        if delivered:
            self.close()
        elif not self._pinned and not self._over_mochi and not self._over_tray:
            self._schedule_close()

    def open_pinned(self) -> bool:
        """Open the tray from the context menu, with keyboard focus."""
        if self._phase is DwellPhase.OPEN:
            return True
        self._reset_arming()
        if not self._open_tray(True):
            return False
        self._phase = DwellPhase.OPEN
        self._pinned = True
        self._needs_leave = self._over_mochi
        return True

    def close(self) -> None:
        """Close the tray after an action, Esc, focus loss, or an interrupt."""
        if self._phase is not DwellPhase.OPEN:
            return
        self._cancel("close")
        self._phase = DwellPhase.IDLE
        self._pinned = False
        self._over_tray = False
        self._dragging = False
        self._needs_leave = self._over_mochi
        self._close_tray()

    def shutdown(self) -> None:
        for name in tuple(self._sources):
            self._cancel(name)
        self._phase = DwellPhase.IDLE
        self._pinned = False
        self._dragging = False

    def _allowed(self) -> bool:
        return self._delay_ms() > 0 and self._can_arm()

    def _on_peek_due(self) -> bool:
        self._sources.pop("peek", None)
        if self._phase is not DwellPhase.ARMED:
            return False
        if not self._allowed():
            self._reset_arming()
            return False
        self._phase = DwellPhase.PEEK
        self._show_peek(max(0, self._armed_delay_ms - POCKET_PEEK_DELAY_MS))
        return False

    def _on_open_due(self) -> bool:
        self._sources.pop("open", None)
        if self._phase not in (DwellPhase.ARMED, DwellPhase.PEEK):
            return False
        if not self._allowed():
            self._reset_arming()
            return False
        peeking = self._phase is DwellPhase.PEEK
        self._cancel("peek")
        self._phase = DwellPhase.IDLE
        self._needs_leave = self._over_mochi
        # The tray replaces a visible peek in place; hide it only on failure.
        if not self._open_tray(False):
            if peeking:
                self._hide_peek()
            return False
        self._phase = DwellPhase.OPEN
        self._pinned = False
        return False

    def _on_close_due(self) -> bool:
        self._sources.pop("close", None)
        if (
            self._phase is DwellPhase.OPEN
            and not self._pinned
            and not self._dragging
            and not self._over_mochi
            and not self._over_tray
        ):
            self.close()
        return False

    def _reset_arming(self) -> None:
        self._cancel("peek")
        self._cancel("open")
        peeking = self._phase is DwellPhase.PEEK
        self._phase = DwellPhase.IDLE
        if peeking:
            self._hide_peek()

    def _schedule_close(self) -> None:
        self._schedule("close", POCKET_TRAY_CLOSE_GRACE_MS, self._on_close_due)

    def _schedule(
        self,
        name: str,
        delay_ms: int,
        callback: Callable[[], bool],
    ) -> None:
        self._cancel(name)
        self._sources[name] = self._timeout_add(delay_ms, callback)

    def _cancel(self, name: str) -> None:
        source_id = self._sources.pop(name, None)
        if source_id is not None:
            self._source_remove(source_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_hover.py`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/pocket_hover.py tests/test_pocket_hover.py
git commit -m "feat(pocket): hover dwell state machine for the Pocket tray"
```

---

### Task 3: One rule for what Pocket launches

**Files:**
- Create: `src/mochi/pocket_actions.py`
- Modify: `src/mochi/pocket_window.py` (`open_item`, `open_containing_folder`)
- Test: `tests/test_pocket_actions.py`

**Interfaces:**
- Consumes: `PocketItem` and `PocketItemKind` (existing).
- Produces:
  - `pocket_actions.launch_uri_for(item: PocketItem) -> str`, which raises `ValueError` for text;
  - `pocket_actions.folder_uri_for(item: PocketItem) -> str`, which raises `ValueError` for anything but `LOCAL_FILE`.

**Acceptance Criteria:**
- Files and saved images launch as `Path.as_uri()`; URLs as their stored, validated value; text raises.
- `folder_uri_for` returns the parent folder URI for local files only.
- `tests/test_pocket_window.py` passes unchanged: the window's behavior is identical.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pocket_actions.py`:

```python
"""The only URIs Pocket hands to the desktop."""

from __future__ import annotations

from pathlib import Path

import pytest

from mochi.pocket import (
    make_local_file_item,
    make_saved_image_item,
    make_text_item,
    make_url_item,
)
from mochi.pocket_actions import folder_uri_for, launch_uri_for


def test_files_and_saved_images_launch_as_file_uris(tmp_path: Path) -> None:
    document = tmp_path / "notes v2.txt"
    document.write_text("hello")
    image = tmp_path / "drop.png"
    image.write_bytes(b"png")

    assert launch_uri_for(make_local_file_item(document)) == document.as_uri()
    assert launch_uri_for(make_saved_image_item(image)) == image.as_uri()


def test_urls_launch_their_validated_value() -> None:
    item = make_url_item("https://docs.gtk.org/gtk4/class.DragSource.html")

    uri = launch_uri_for(item)

    assert uri == item.value
    assert uri.startswith("https://")


def test_text_is_never_launched() -> None:
    with pytest.raises(ValueError):
        launch_uri_for(make_text_item("rm -rf ~"))


def test_folder_uri_is_the_parent_of_a_local_file(tmp_path: Path) -> None:
    document = tmp_path / "report.pdf"
    document.write_bytes(b"%PDF")

    assert folder_uri_for(make_local_file_item(document)) == tmp_path.as_uri()


def test_only_local_files_have_a_containing_folder(tmp_path: Path) -> None:
    image = tmp_path / "drop.png"
    image.write_bytes(b"png")
    for item in (
        make_url_item("https://example.org/"),
        make_text_item("hello"),
        make_saved_image_item(image),
    ):
        with pytest.raises(ValueError):
            folder_uri_for(item)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_actions.py`

Expected: `ModuleNotFoundError: No module named 'mochi.pocket_actions'`.

- [ ] **Step 3: Implement `src/mochi/pocket_actions.py`**

```python
"""GTK-free rules for what Pocket hands to the desktop."""

from __future__ import annotations

from pathlib import Path

from mochi.pocket import PocketItem, PocketItemKind


def launch_uri_for(item: PocketItem) -> str:
    """Return the only URI Pocket may launch for this item.

    URL items were validated as HTTP(S) when they entered the Pocket. Files
    and saved images launch as file URIs. Text is never launched.
    """
    if item.kind is PocketItemKind.URL:
        return item.value
    if item.kind is PocketItemKind.TEXT:
        raise ValueError("Pocket text is viewed or copied, never launched")
    return Path(item.value).as_uri()


def folder_uri_for(item: PocketItem) -> str:
    """Return the containing folder of a local Pocket file."""
    if item.kind is not PocketItemKind.LOCAL_FILE:
        raise ValueError("Only local Pocket files have a containing folder")
    return Path(item.value).parent.as_uri()
```

- [ ] **Step 4: Point `PocketWindow` at the shared rule**

In `src/mochi/pocket_window.py`, add the import:

```python
from mochi.pocket_actions import folder_uri_for, launch_uri_for
```

In `open_item()`, replace:

```python
        uri = item.value if item.kind is PocketItemKind.URL else Path(item.value).as_uri()
```

with:

```python
        uri = launch_uri_for(item)
```

In `open_containing_folder()`, replace:

```python
        folder_uri = Path(item.value).parent.as_uri()
```

with:

```python
        folder_uri = folder_uri_for(item)
```

- [ ] **Step 5: Run the new and existing Pocket window tests**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_actions.py tests/test_pocket_window.py`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/pocket_actions.py src/mochi/pocket_window.py tests/test_pocket_actions.py
git commit -m "refactor(pocket): share the launch-URI rule between window and tray"
```

---

### Task 4: `PocketTray` and the no-focus map request

**Files:**
- Modify: `src/mochi/x11.py` (add `request_no_focus_on_map` after `request_keep_above`)
- Create: `src/mochi/pocket_tray.py`
- Test: `tests/test_pocket_tray.py`

**Interfaces:**
- Consumes:
  - `launch_uri_for` and `folder_uri_for` (Task 3);
  - `pocket_window.row_model`, `PocketTextWindow` and `_launch_default`;
  - `menu_window._distance_to_geometry` and `_window_coordinate_scale`;
  - `x11.get_window_position`, `move_window` and `request_keep_above`;
  - a dwell-shaped collaborator with `tray_entered()`, `tray_left()`, `drag_started()`, `drag_finished(delivered)` and `close()`. In production this is `PocketHoverDwell` from Task 2.
- Produces:
  - `x11.request_no_focus_on_map(window: Gtk.Window) -> bool`
  - `pocket_tray.tray_position_for_anchor(owner_x, owner_y, owner_width, owner_height, tray_width, tray_height, geometries, *, gap=8, padding=12, coordinate_scale=1.0) -> tuple[int, int]`
  - `pocket_tray.peek_fill_fraction(elapsed_ms: float, fill_ms: int) -> float`
  - `pocket_tray.TrayRowModel`, `pocket_tray.tray_row_model(item) -> TrayRowModel`
  - `pocket_tray.drag_content_for(item) -> Gdk.ContentProvider | None`
  - `pocket_tray.clipboard_content_for(item, *, load_texture=...) -> Gdk.ContentProvider`
  - `pocket_tray.PocketTray(*, owner, controller, dwell, on_manage, show_feedback, launcher=_launch_default, clipboard=None, load_texture=Gdk.Texture.new_from_filename, logger=None)`, with:
    - methods `show_peek(count, fill_ms)`, `hide_peek()`, `open(*, focus)`, `refresh(*, force=False)`, `close()`, `destroy()`, `activate_primary(item_id) -> bool`, `activate_quick(item_id) -> bool`;
    - attributes `view: str | None` (`"peek"`, `"tray"` or `None`), `rows: dict[str, TrayRowWidgets]`, `detail_windows`, `window`, `peek_label`, `count_label`, `empty_label`, `manage_button`.

**Acceptance Criteria:**
- Placement: centred above Mochi with an 8 px gap; flips below when above would cross the monitor's top padding; clamped 12 px inside the nearest monitor; scale-aware.
- Row models: primary and quick labels per kind as in the spec table; missing files are `available=False`.
- Providers:
  - local files and saved images drag as `GdkFileList`;
  - URLs drag as `text/uri-list` plus a string;
  - text drags as a string;
  - missing files have no drag;
  - text and URLs copy as a string; images copy as a texture; local files cannot be copied.
- `show_peek` maps without focus (`request_no_focus_on_map`) and shows `Pocket · N`. `hide_peek` hides it and removes the tick callback.
- `open(focus=False)` uses the no-focus path. `open(focus=True)` presents and focuses the first row, or `Manage Pocket…` when empty.
- Primary actions: files, URLs and images launch and then `dwell.close()`; text copies, shows "Copied" feedback, then `dwell.close()`.
- Quick actions: show in folder launches the folder; copy actions set the clipboard and show an inline "Copied" for 1.5 s without closing; View all opens a `PocketTextWindow`.
- Failures (`GLib.Error`, `OSError`, `ValueError`) show "Couldn't open it. It's still here." on the row and never close the tray.
- Missing rows are not activatable and have no quick button and no drag source.
- Esc, the window close request, and focus loss after activation (unless dragging) call `dwell.close()`.
- Drag: begin calls `dwell.drag_started()`; end calls `dwell.drag_finished(delivered)`, where `delivered` is false when `drag-cancel` was seen.
- `close()` and `destroy()` leave no feedback, position, or tick sources. `destroy()` also destroys detail windows and the window.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pocket_tray.py`:

```python
"""Pocket tray placement, rows, actions, and lifecycle under Xvfb."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, GObject, Gtk  # noqa: E402

from mochi.pocket import (  # noqa: E402
    make_local_file_item,
    make_saved_image_item,
    make_text_item,
    make_url_item,
)
from mochi.pocket_tray import (  # noqa: E402
    LAUNCH_FAILED_TEXT,
    PocketTray,
    clipboard_content_for,
    drag_content_for,
    peek_fill_fraction,
    tray_position_for_anchor,
    tray_row_model,
)
from mochi.x11 import request_no_focus_on_map  # noqa: E402


def _monitor(x: int, y: int, width: int = 1920, height: int = 1080):
    return SimpleNamespace(x=x, y=y, width=width, height=height)


def _tiny_texture(_path: str) -> Gdk.Texture:
    return Gdk.MemoryTexture.new(
        1, 1, Gdk.MemoryFormat.R8G8B8A8, GLib.Bytes.new(bytes(4)), 4
    )


def _mime_types(formats: Gdk.ContentFormats) -> list[str]:
    return list(formats.union_serialize_mime_types().get_mime_types())


class _Dwell:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def tray_entered(self) -> None:
        self.calls.append("tray-entered")

    def tray_left(self) -> None:
        self.calls.append("tray-left")

    def drag_started(self) -> None:
        self.calls.append("drag-started")

    def drag_finished(self, delivered: bool) -> None:
        self.calls.append(f"drag-finished:{delivered}")

    def close(self) -> None:
        self.calls.append("close")


class _Clipboard:
    def __init__(self) -> None:
        self.contents: list[Gdk.ContentProvider] = []

    def set_content(self, provider: Gdk.ContentProvider) -> bool:
        self.contents.append(provider)
        return True


@pytest.fixture
def make_tray(monkeypatch):
    created: list[PocketTray] = []
    no_focus_calls: list[Gtk.Window] = []
    monkeypatch.setattr(
        "mochi.pocket_tray.request_no_focus_on_map",
        lambda window: no_focus_calls.append(window) or True,
    )

    def build(items=(), **overrides):
        dwell = _Dwell()
        launched: list[str] = []
        feedback: list[str] = []
        clipboard = _Clipboard()
        kwargs = dict(
            owner=Gtk.Window(),
            controller=SimpleNamespace(items=tuple(items)),
            dwell=dwell,
            on_manage=Mock(),
            show_feedback=feedback.append,
            launcher=launched.append,
            clipboard=clipboard,
            load_texture=_tiny_texture,
        )
        kwargs.update(overrides)
        tray = PocketTray(**kwargs)
        created.append(tray)
        return SimpleNamespace(
            tray=tray,
            dwell=dwell,
            launched=launched,
            feedback=feedback,
            clipboard=clipboard,
            no_focus_calls=no_focus_calls,
            on_manage=kwargs["on_manage"],
        )

    yield build
    for tray in created:
        owner = tray._owner
        tray.destroy()
        owner.destroy()


def _file(tmp_path: Path, name: str = "invoice-september.pdf"):
    path = tmp_path / name
    path.write_bytes(b"data")
    return path, make_local_file_item(path)


# Placement -----------------------------------------------------------------


def test_tray_sits_centred_above_mochi() -> None:
    assert tray_position_for_anchor(
        900, 900, 112, 112, 360, 300, [_monitor(0, 0)]
    ) == (776, 592)


def test_tray_flips_below_mochi_near_the_top_edge() -> None:
    assert tray_position_for_anchor(
        900, 50, 112, 112, 360, 300, [_monitor(0, 0)]
    ) == (776, 170)


def test_tray_is_clamped_inside_the_monitor() -> None:
    left = tray_position_for_anchor(0, 900, 112, 112, 360, 300, [_monitor(0, 0)])
    right = tray_position_for_anchor(1880, 900, 112, 112, 360, 300, [_monitor(0, 0)])

    assert left == (12, 592)
    assert right == (1548, 592)


def test_tray_uses_device_pixels_on_scaled_displays() -> None:
    assert tray_position_for_anchor(
        1800, 1800, 224, 224, 360, 300, [_monitor(0, 0)], coordinate_scale=2.0
    ) == (1552, 1184)


def test_tray_stays_on_mochis_monitor() -> None:
    monitors = [_monitor(0, 0), _monitor(1920, 0)]

    assert tray_position_for_anchor(
        2000, 900, 112, 112, 360, 300, monitors
    ) == (1932, 592)


def test_peek_fill_is_clamped_progress() -> None:
    assert peek_fill_fraction(0, 1400) == 0.0
    assert peek_fill_fraction(700, 1400) == pytest.approx(0.5)
    assert peek_fill_fraction(5000, 1400) == 1.0
    assert peek_fill_fraction(10, 0) == 1.0


# Rows and providers ---------------------------------------------------------


def test_row_models_name_the_action_for_each_kind(tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    image_path = tmp_path / "drop.png"
    image_path.write_bytes(b"png")

    file_row = tray_row_model(document)
    url_row = tray_row_model(make_url_item("https://example.org/"))
    text_row = tray_row_model(make_text_item("Ask Sam about the venue deposit"))
    image_row = tray_row_model(make_saved_image_item(image_path))

    assert (file_row.primary_label, file_row.quick_label) == ("Open", "Show in folder")
    assert (url_row.primary_label, url_row.quick_label) == ("Open", "Copy link")
    assert (text_row.primary_label, text_row.quick_label) == ("Copy", "View all")
    assert (image_row.primary_label, image_row.quick_label) == ("Open", "Copy image")
    assert all(
        row.available for row in (file_row, url_row, text_row, image_row)
    )


def test_missing_file_row_is_unavailable(tmp_path: Path) -> None:
    path, document = _file(tmp_path)
    path.unlink()

    assert tray_row_model(document).available is False
    assert drag_content_for(document) is None


def test_drag_offers_files_urls_and_text_in_native_formats(tmp_path: Path) -> None:
    _path, document = _file(tmp_path)

    file_formats = drag_content_for(document).ref_formats()
    url_formats = drag_content_for(make_url_item("https://example.org/")).ref_formats()
    text_formats = drag_content_for(make_text_item("hello")).ref_formats()

    assert file_formats.contain_gtype(Gdk.FileList)
    assert url_formats.contain_mime_type("text/uri-list")
    assert url_formats.contain_gtype(GObject.TYPE_STRING)
    assert text_formats.contain_gtype(GObject.TYPE_STRING)
    # What another application can actually receive:
    assert "text/uri-list" in _mime_types(file_formats)
    assert "text/plain;charset=utf-8" in _mime_types(text_formats)


def test_clipboard_copies_text_links_and_images_but_not_files(tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    image_path = tmp_path / "drop.png"
    image_path.write_bytes(b"png")

    text = clipboard_content_for(make_text_item("hello"))
    link = clipboard_content_for(make_url_item("https://example.org/"))
    image = clipboard_content_for(
        make_saved_image_item(image_path), load_texture=_tiny_texture
    )

    assert text.ref_formats().contain_gtype(GObject.TYPE_STRING)
    assert link.ref_formats().contain_gtype(GObject.TYPE_STRING)
    assert image.ref_formats().contain_gtype(Gdk.Texture)
    # A bare GdkMemoryTexture value has no serializers; other apps could not paste it.
    assert "image/png" in _mime_types(image.ref_formats())
    with pytest.raises(ValueError):
        clipboard_content_for(document)


# Views --------------------------------------------------------------------


def test_peek_maps_without_focus_and_shows_the_count(make_tray) -> None:
    built = make_tray()

    built.tray.show_peek(3, 1400)

    assert built.tray.view == "peek"
    assert built.tray.peek_label.get_text() == "Pocket · 3"
    assert built.no_focus_calls == [built.tray.window]
    assert built.tray.window.get_visible()

    built.tray.hide_peek()
    assert built.tray.view is None
    assert not built.tray.window.get_visible()
    assert built.tray._fill_tick_id is None


def test_hover_open_lists_items_newest_first_without_focus(make_tray, tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    items = (make_text_item("newest"), make_url_item("https://example.org/"), document)
    built = make_tray(items)

    built.tray.open(focus=False)

    assert built.tray.view == "tray"
    assert built.tray.count_label.get_text() == "3 of 10"
    assert [
        built.tray._list.get_row_at_index(index) for index in range(3)
    ] == [built.tray.rows[item.id].row for item in items]
    assert built.no_focus_calls == [built.tray.window]
    assert not built.tray.empty_label.get_visible()


def test_menu_open_presents_normally_and_shows_the_empty_state(make_tray) -> None:
    built = make_tray(())

    built.tray.open(focus=True)

    assert built.no_focus_calls == []
    assert built.tray.empty_label.get_visible()
    assert built.tray.count_label.get_text() == "0 of 10"


def test_refresh_only_rebuilds_an_open_tray(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.refresh()
    assert built.tray.rows == {}

    built.tray.open(focus=False)
    built.tray._controller = SimpleNamespace(
        items=(make_text_item("two"), make_text_item("one"))
    )
    built.tray.refresh()
    assert len(built.tray.rows) == 2


# Actions ------------------------------------------------------------------


def test_primary_opens_files_and_links_then_closes(make_tray, tmp_path: Path) -> None:
    path, document = _file(tmp_path)
    link = make_url_item("https://example.org/")
    built = make_tray((document, link))
    built.tray.open(focus=False)

    assert built.tray.activate_primary(document.id) is True
    assert built.tray.activate_primary(link.id) is True

    assert built.launched == [path.as_uri(), link.value]
    assert built.dwell.calls == ["close", "close"]


def test_primary_copies_text_and_says_so(make_tray) -> None:
    note = make_text_item("Ask Sam about the venue deposit")
    built = make_tray((note,))
    built.tray.open(focus=False)

    assert built.tray.activate_primary(note.id) is True

    assert len(built.clipboard.contents) == 1
    assert built.feedback == ["Copied"]
    assert built.dwell.calls == ["close"]
    assert built.launched == []


def test_launch_failure_keeps_the_tray_and_the_item(make_tray, tmp_path: Path) -> None:
    _path, document = _file(tmp_path)

    def failing(_uri: str) -> None:
        raise OSError("no handler")

    built = make_tray((document,), launcher=failing)
    built.tray.open(focus=False)

    assert built.tray.activate_primary(document.id) is False

    status = built.tray.rows[document.id].status
    assert status.get_visible()
    assert status.get_text() == LAUNCH_FAILED_TEXT
    assert built.dwell.calls == []


def test_quick_actions_stay_open_and_confirm_in_place(make_tray, tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    link = make_url_item("https://example.org/")
    built = make_tray((document, link))
    built.tray.open(focus=False)

    assert built.tray.activate_quick(document.id) is True
    assert built.tray.activate_quick(link.id) is True

    assert built.launched == [tmp_path.as_uri()]
    assert len(built.clipboard.contents) == 1
    assert built.tray.rows[link.id].status.get_text() == "Copied"
    assert link.id in built.tray._feedback_sources
    assert built.dwell.calls == []

    built.tray.close()
    assert built.tray._feedback_sources == {}


def test_view_all_opens_the_read_only_text_window(make_tray) -> None:
    note = make_text_item("line one\nline two")
    built = make_tray((note,))
    built.tray.open(focus=False)

    assert built.tray.activate_quick(note.id) is True

    assert len(built.tray.detail_windows) == 1


def test_unreadable_image_copy_shows_the_row_error(make_tray, tmp_path: Path) -> None:
    image_path = tmp_path / "drop.png"
    image_path.write_bytes(b"not really a png")
    image = make_saved_image_item(image_path)

    def failing(_path: str):
        raise OSError("cannot decode")

    built = make_tray((image,), load_texture=failing)
    built.tray.open(focus=False)

    assert built.tray.activate_quick(image.id) is False
    assert built.tray.rows[image.id].status.get_text() == LAUNCH_FAILED_TEXT


def test_missing_rows_cannot_be_grabbed(make_tray, tmp_path: Path) -> None:
    path, document = _file(tmp_path)
    path.unlink()
    built = make_tray((document,))
    built.tray.open(focus=False)

    widgets = built.tray.rows[document.id]
    assert widgets.row.get_activatable() is False
    assert widgets.quick_button is None
    assert widgets.drag_source is None
    assert built.tray.activate_primary(document.id) is False
    assert built.launched == []


def test_manage_hands_off_to_the_pocket_window(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.open(focus=False)

    built.tray.manage_button.emit("clicked")

    built.on_manage.assert_called_once_with()


# Closing, focus, and drag ---------------------------------------------------


def test_escape_closes_through_the_dwell(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.open(focus=False)

    assert built.tray._on_key_pressed(None, Gdk.KEY_a, 0, Gdk.ModifierType(0)) is False
    assert built.tray._on_key_pressed(
        None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0)
    ) is True
    assert built.dwell.calls == ["close"]


def test_focus_loss_after_activation_closes_unless_dragging(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.open(focus=False)
    inactive = SimpleNamespace(is_active=lambda: False, get_visible=lambda: True)

    built.tray._was_active = True
    built.tray._dragging = True
    built.tray._on_active_changed(inactive, None)
    assert built.dwell.calls == []

    built.tray._dragging = False
    built.tray._on_active_changed(inactive, None)
    assert built.dwell.calls == ["close"]


def test_drag_reports_delivery_to_the_dwell(make_tray) -> None:
    note = make_text_item("one")
    built = make_tray((note,))
    built.tray.open(focus=False)
    source = SimpleNamespace(set_icon=Mock())
    row = built.tray.rows[note.id].row

    built.tray._on_drag_begin(source, row)
    built.tray._on_drag_end(source, None, False)
    built.tray._on_drag_begin(source, row)
    assert built.tray._on_drag_cancel(source, None, None) is False
    built.tray._on_drag_end(source, None, False)

    assert built.dwell.calls == [
        "drag-started",
        "drag-finished:True",
        "drag-started",
        "drag-finished:False",
    ]


def test_destroy_releases_detail_windows_and_sources(make_tray) -> None:
    note = make_text_item("one")
    built = make_tray((note,))
    built.tray.show_peek(1, 1400)
    built.tray.open(focus=False)
    built.tray.activate_quick(note.id)
    detail = built.tray.detail_windows[0]

    built.tray.destroy()

    # gtk_window_destroy() removes the window from the toplevel list at once;
    # the "destroy" signal itself waits for the last reference to drop.
    assert detail not in list(Gtk.Window.get_toplevels())
    assert built.tray.detail_windows == []
    assert built.tray._position_sources == set()
    assert built.tray._fill_tick_id is None


def test_no_focus_request_needs_an_x11_surface() -> None:
    assert request_no_focus_on_map(SimpleNamespace(get_surface=lambda: None)) is False

    window = Gtk.Window()
    window.realize()
    try:
        assert request_no_focus_on_map(window) is True
    finally:
        window.destroy()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_tray.py`

Expected: `ImportError` for `request_no_focus_on_map`, then `ModuleNotFoundError: No module named 'mochi.pocket_tray'` once Step 3 is in.

- [ ] **Step 3: Add `request_no_focus_on_map` to `src/mochi/x11.py`**

Insert directly after `request_keep_above()`:

```python
def request_no_focus_on_map(window: Gtk.Window) -> bool:
    """Ask the X11 window manager not to focus this window when it maps.

    EWMH: a _NET_WM_USER_TIME of 0 means "do not give this window focus on
    map". Pocket's hover tray uses it so resting on Mochi never steals typing.
    Call it after realize() and before the window is shown.
    """
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return False
    surface.set_user_time(0)
    return True
```

- [ ] **Step 4: Implement `src/mochi/pocket_tray.py`**

```python
"""Hover and menu tray for taking things back out of Mochi's Pocket."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from mochi.menu_window import _distance_to_geometry, _window_coordinate_scale
from mochi.pocket import (
    DEFAULT_CAPACITY,
    PocketItem,
    PocketItemKind,
    item_is_available,
)
from mochi.pocket_actions import folder_uri_for, launch_uri_for
from mochi.pocket_hover import PocketHoverDwell
from mochi.pocket_window import PocketTextWindow, _launch_default, row_model
from mochi.x11 import (
    get_window_position,
    move_window,
    request_keep_above,
    request_no_focus_on_map,
)

TRAY_WIDTH = 360
TRAY_GAP_PX = 8
TRAY_MAX_LIST_HEIGHT = 480
TRAY_FEEDBACK_MS = 1500
PEEK_WIDTH = 150
EMPTY_TRAY_TEXT = "Nothing in here yet. Drag a file, link, image, or text onto Mochi."
LAUNCH_FAILED_TEXT = "Couldn't open it. It's still here."

POCKET_TRAY_CSS = """
window.mochi-pocket-tray {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}
.mochi-tray-peek { padding: 8px 12px 10px; }
.mochi-tray-card { padding: 6px; }
.mochi-tray-header { padding: 6px 8px 4px; }
.mochi-tray-title { font-weight: 700; }
.mochi-tray-dim { color: alpha(@theme_fg_color, 0.68); font-size: smaller; }
.mochi-tray-empty { padding: 12px 8px; }
list.mochi-tray-list { background: none; }
row.mochi-tray-row { border-radius: 10px; padding: 4px 4px 4px 8px; min-height: 48px; }
row.mochi-tray-row .mochi-tray-verb { opacity: 0; }
row.mochi-tray-row:hover .mochi-tray-verb,
row.mochi-tray-row:focus-within .mochi-tray-verb { opacity: 1; }
.mochi-tray-verb {
    background-color: #79c98b;
    color: #102417;
    border-radius: 999px;
    padding: 2px 9px;
    font-weight: 700;
    font-size: smaller;
}
.mochi-tray-chip {
    min-width: 36px;
    min-height: 36px;
    border-radius: 9px;
    background-color: alpha(#79c98b, 0.18);
}
row.mochi-tray-missing { opacity: 0.6; }
button.mochi-tray-quick { min-width: 44px; min-height: 44px; }
.mochi-tray-error { color: #c01c28; }
/* Shorthand: the theme paints progress with a background-image that would
   cover a background-color alone. */
progressbar.mochi-tray-fill > trough > progress { background: #79c98b; }
"""

# Primary verb, quick-action label, quick-action icon.
_ROW_ACTIONS = {
    PocketItemKind.LOCAL_FILE: ("Open", "Show in folder", "folder-open-symbolic"),
    PocketItemKind.URL: ("Open", "Copy link", "edit-copy-symbolic"),
    PocketItemKind.TEXT: ("Copy", "View all", "view-reveal-symbolic"),
    PocketItemKind.SAVED_IMAGE: ("Open", "Copy image", "edit-copy-symbolic"),
}


def tray_position_for_anchor(
    owner_x: int,
    owner_y: int,
    owner_width: int,
    owner_height: int,
    tray_width: int,
    tray_height: int,
    geometries: list,
    *,
    gap: int = TRAY_GAP_PX,
    padding: int = 12,
    coordinate_scale: float = 1.0,
) -> tuple[int, int]:
    """Centre the tray above Mochi, or below him when there is no room above.

    ``owner_*`` and the returned coordinates are X11 device pixels. Tray sizes,
    monitor geometries, gap, and padding are GTK application pixels, matching
    ``menu_position_for_anchor``.
    """
    scale = coordinate_scale if coordinate_scale > 0 else 1.0
    width = max(1, round(tray_width * scale))
    height = max(1, round(tray_height * scale))
    device_gap = round(gap * scale)
    x = owner_x + owner_width // 2 - width // 2
    above = owner_y - device_gap - height
    below = owner_y + owner_height + device_gap
    if not geometries:
        return (x, above if above >= 0 else below)

    centre_x = (owner_x + owner_width / 2) / scale
    centre_y = (owner_y + owner_height / 2) / scale
    monitor = min(
        geometries,
        key=lambda geometry: _distance_to_geometry(centre_x, centre_y, geometry),
    )
    left = round((monitor.x + padding) * scale)
    top = round((monitor.y + padding) * scale)
    right = round((monitor.x + monitor.width - padding) * scale)
    bottom = round((monitor.y + monitor.height - padding) * scale)

    y = above if above >= top else below
    x = max(left, min(x, max(left, right - width)))
    y = max(top, min(y, max(top, bottom - height)))
    return (x, y)


def peek_fill_fraction(elapsed_ms: float, fill_ms: int) -> float:
    """Return the peek bar's progress, clamped to 0..1."""
    if fill_ms <= 0:
        return 1.0
    return max(0.0, min(1.0, elapsed_ms / fill_ms))


@dataclass(frozen=True)
class TrayRowModel:
    item_id: str
    title: str
    subtitle: str
    icon_name: str
    available: bool
    primary_label: str
    quick_label: str
    quick_icon: str


@dataclass
class TrayRowWidgets:
    model: TrayRowModel
    row: Gtk.ListBoxRow
    status: Gtk.Label
    quick_button: Gtk.Button | None
    drag_source: Gtk.DragSource | None


def tray_row_model(item: PocketItem) -> TrayRowModel:
    """Describe a tray row; titles and subtitles match the Pocket window."""
    base = row_model(item)
    primary, quick, quick_icon = _ROW_ACTIONS[item.kind]
    return TrayRowModel(
        item_id=item.id,
        title=base.title,
        subtitle=base.subtitle,
        icon_name=base.icon_name,
        available=base.available,
        primary_label=primary,
        quick_label=quick,
        quick_icon=quick_icon,
    )


def drag_content_for(item: PocketItem) -> Gdk.ContentProvider | None:
    """Return what dragging this item out offers, or None for a missing file."""
    if not item_is_available(item):
        return None
    if item.kind in (PocketItemKind.LOCAL_FILE, PocketItemKind.SAVED_IMAGE):
        files = Gdk.FileList.new_from_list([Gio.File.new_for_path(item.value)])
        return Gdk.ContentProvider.new_for_value(GObject.Value(Gdk.FileList, files))
    if item.kind is PocketItemKind.URL:
        uri_list = GLib.Bytes.new(f"{item.value}\r\n".encode("utf-8"))
        return Gdk.ContentProvider.new_union(
            [
                Gdk.ContentProvider.new_for_bytes("text/uri-list", uri_list),
                Gdk.ContentProvider.new_for_value(item.value),
            ]
        )
    return Gdk.ContentProvider.new_for_value(item.value)


def clipboard_content_for(
    item: PocketItem,
    *,
    load_texture: Callable[[str], Gdk.Texture] = Gdk.Texture.new_from_filename,
) -> Gdk.ContentProvider:
    """Return what Copy puts on the clipboard. Local files are opened, not copied."""
    if item.kind in (PocketItemKind.TEXT, PocketItemKind.URL):
        return Gdk.ContentProvider.new_for_value(item.value)
    if item.kind is PocketItemKind.SAVED_IMAGE:
        # Type the value as Gdk.Texture: GTK finds clipboard serializers by
        # exact type, and a bare GdkMemoryTexture would offer nothing to paste.
        texture = GObject.Value(Gdk.Texture, load_texture(item.value))
        return Gdk.ContentProvider.new_for_value(texture)
    raise ValueError("Local Pocket files are opened or dragged, not copied")


class PocketTray:
    """One small window: a filling peek bar that becomes the Pocket tray.

    The dwell decides when it opens and closes. The tray owns every source it
    creates (positioning, fill tick, inline feedback) and the text windows it
    opened, and releases them in close() and destroy().
    """

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        controller,
        dwell: PocketHoverDwell,
        on_manage: Callable[[], None],
        show_feedback: Callable[[str], None],
        launcher: Callable[[str], None] = _launch_default,
        clipboard: Gdk.Clipboard | None = None,
        load_texture: Callable[[str], Gdk.Texture] = Gdk.Texture.new_from_filename,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._controller = controller
        self._dwell = dwell
        self._on_manage = on_manage
        self._show_feedback = show_feedback
        self._launcher = launcher
        self._clipboard = clipboard
        self._load_texture = load_texture
        self._logger = logger or logging.getLogger(__name__)
        self.view: str | None = None
        self.rows: dict[str, TrayRowWidgets] = {}
        self.detail_windows: list[PocketTextWindow] = []
        self._was_active = False
        self._dragging = False
        self._drag_cancelled = False
        self._fill_ms = 0
        self._fill_started_us: int | None = None
        self._fill_tick_id: int | None = None
        self._feedback_sources: dict[str, int] = {}
        self._position_sources: set[int] = set()

        self.window = Gtk.Window()
        self.window.set_title("Mochi's Pocket")
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_transient_for(owner)
        self.window.add_css_class("mochi-pocket-tray")
        self.window.connect("map", self._on_map)
        self.window.connect("close-request", self._on_close_request)
        self.window.connect("notify::is-active", self._on_active_changed)
        self._install_css()

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(keys)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", lambda *_args: self._dwell.tray_entered())
        motion.connect("leave", lambda *_args: self._dwell.tray_left())
        self.window.add_controller(motion)

        self._stack = Gtk.Stack()
        self._stack.set_hhomogeneous(False)
        self._stack.set_vhomogeneous(False)
        self._stack.set_interpolate_size(False)
        self._stack.add_named(self._build_peek(), "peek")
        self._stack.add_named(self._build_tray(), "tray")
        self.window.set_child(self._stack)

    # Public surface ---------------------------------------------------------

    def show_peek(self, count: int, fill_ms: int) -> None:
        self.peek_label.set_text(f"Pocket · {count}")
        self.peek_bar.set_fraction(0.0)
        self._fill_ms = max(0, int(fill_ms))
        self._fill_started_us = None
        self._stack.set_visible_child_name("peek")
        self.view = "peek"
        self._present(focus=False)
        self._start_fill()

    def hide_peek(self) -> None:
        if self.view == "peek":
            self._hide()

    def open(self, *, focus: bool) -> None:
        self._stop_fill()
        self.refresh(force=True)
        self._stack.set_visible_child_name("tray")
        self.view = "tray"
        self._was_active = False
        self._present(focus=focus)
        if focus:
            first = self._list.get_row_at_index(0)
            (first or self.manage_button).grab_focus()

    def refresh(self, *, force: bool = False) -> None:
        if self.view != "tray" and not force:
            return
        self._cancel_all_feedback()
        self._list.remove_all()
        self.rows.clear()
        items = tuple(self._controller.items)
        for item in items:
            widgets = self._make_row(item)
            self.rows[item.id] = widgets
            self._list.append(widgets.row)
        self.count_label.set_text(f"{len(items)} of {DEFAULT_CAPACITY}")
        self.empty_label.set_visible(not items)
        self._scroll.set_visible(bool(items))
        if self.window.get_visible():
            self._schedule_position()

    def close(self) -> None:
        """Hide the tray. The dwell owns open/closed state and calls this."""
        self._hide()

    def destroy(self) -> None:
        self._hide()
        details = tuple(self.detail_windows)
        self.detail_windows.clear()
        for detail in details:
            detail.destroy()
        self.window.destroy()

    def activate_primary(self, item_id: str) -> bool:
        item = self._item(item_id)
        if item is None or not item_is_available(item):
            return False
        try:
            if item.kind is PocketItemKind.TEXT:
                self._copy(item)
            else:
                self._launcher(launch_uri_for(item))
        except (GLib.Error, OSError, ValueError) as error:
            self._logger.warning("Pocket tray action failed: %s", error)
            self._show_row_status(item_id, LAUNCH_FAILED_TEXT, error=True)
            return False
        if item.kind is PocketItemKind.TEXT:
            self._show_feedback("Copied")
        self._dwell.close()
        return True

    def activate_quick(self, item_id: str) -> bool:
        item = self._item(item_id)
        if item is None or not item_is_available(item):
            return False
        try:
            if item.kind is PocketItemKind.LOCAL_FILE:
                self._launcher(folder_uri_for(item))
            elif item.kind is PocketItemKind.TEXT:
                self._open_text_detail(item)
            else:
                self._copy(item)
                self._show_row_status(
                    item_id, "Copied", error=False, timeout_ms=TRAY_FEEDBACK_MS
                )
        except (GLib.Error, OSError, ValueError) as error:
            self._logger.warning("Pocket tray quick action failed: %s", error)
            self._show_row_status(item_id, LAUNCH_FAILED_TEXT, error=True)
            return False
        return True

    # Construction -----------------------------------------------------------

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(POCKET_TRAY_CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.window.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_peek(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("mochi-tray-peek")
        box.set_size_request(PEEK_WIDTH, -1)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        line.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        self.peek_label = Gtk.Label(label="Pocket")
        self.peek_label.add_css_class("mochi-tray-title")
        line.append(self.peek_label)
        box.append(line)
        self.peek_bar = Gtk.ProgressBar()
        self.peek_bar.add_css_class("mochi-tray-fill")
        box.append(self.peek_bar)
        return box

    def _build_tray(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("mochi-tray-card")
        card.set_size_request(TRAY_WIDTH, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("mochi-tray-header")
        title = Gtk.Label(label="Pocket")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("mochi-tray-title")
        header.append(title)
        self.count_label = Gtk.Label()
        self.count_label.add_css_class("mochi-tray-dim")
        header.append(self.count_label)
        card.append(header)

        self.empty_label = Gtk.Label(label=EMPTY_TRAY_TEXT)
        self.empty_label.set_wrap(True)
        self.empty_label.set_max_width_chars(36)
        self.empty_label.add_css_class("mochi-tray-dim")
        self.empty_label.add_css_class("mochi-tray-empty")
        card.append(self.empty_label)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.set_activate_on_single_click(True)
        self._list.add_css_class("mochi-tray-list")
        self._list.update_property([Gtk.AccessibleProperty.LABEL], ["Pocket items"])
        self._list.connect("row-activated", self._on_row_activated)
        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroll.set_propagate_natural_height(True)
        self._scroll.set_max_content_height(TRAY_MAX_LIST_HEIGHT)
        self._scroll.set_child(self._list)
        card.append(self._scroll)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.manage_button = Gtk.Button(label="Manage Pocket…")
        self.manage_button.add_css_class("flat")
        self.manage_button.connect("clicked", lambda _button: self._on_manage())
        footer.append(self.manage_button)
        hint = Gtk.Label(label="Click to open, or drag it out")
        hint.set_xalign(1)
        hint.set_hexpand(True)
        hint.add_css_class("mochi-tray-dim")
        footer.append(hint)
        card.append(footer)
        return card

    def _make_row(self, item: PocketItem) -> TrayRowWidgets:
        model = tray_row_model(item)
        row = Gtk.ListBoxRow()
        row.add_css_class("mochi-tray-row")
        row.set_activatable(model.available)
        if model.available:
            accessible = f"{model.primary_label} {model.title}"
        else:
            row.add_css_class("mochi-tray-missing")
            accessible = f"{model.title}, moved or deleted"
        row.update_property([Gtk.AccessibleProperty.LABEL], [accessible])

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        chip = Gtk.Image.new_from_icon_name(model.icon_name)
        chip.add_css_class("mochi-tray-chip")
        content.append(chip)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label=model.title)
        title.set_xalign(0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.add_css_class("mochi-tray-title")
        labels.append(title)
        subtitle = Gtk.Label(label=model.subtitle)
        subtitle.set_xalign(0)
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.add_css_class("mochi-tray-dim")
        labels.append(subtitle)
        status = Gtk.Label()
        status.set_xalign(0)
        status.set_visible(False)
        labels.append(status)
        content.append(labels)

        quick_button: Gtk.Button | None = None
        drag_source: Gtk.DragSource | None = None
        if model.available:
            verb = Gtk.Label(label=model.primary_label)
            verb.set_valign(Gtk.Align.CENTER)
            verb.add_css_class("mochi-tray-verb")
            content.append(verb)

            quick_button = Gtk.Button.new_from_icon_name(model.quick_icon)
            quick_button.add_css_class("flat")
            quick_button.add_css_class("mochi-tray-quick")
            quick_button.set_valign(Gtk.Align.CENTER)
            quick_button.set_tooltip_text(model.quick_label)
            quick_button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{model.quick_label}: {model.title}"],
            )
            quick_button.connect(
                "clicked",
                lambda _button, item_id=item.id: self.activate_quick(item_id),
            )
            content.append(quick_button)

            drag_source = Gtk.DragSource()
            drag_source.set_actions(Gdk.DragAction.COPY)
            drag_source.connect(
                "prepare",
                lambda _source, _x, _y, item_id=item.id: self._prepare_drag(item_id),
            )
            drag_source.connect(
                "drag-begin",
                lambda source, _drag, row=row: self._on_drag_begin(source, row),
            )
            drag_source.connect("drag-cancel", self._on_drag_cancel)
            drag_source.connect("drag-end", self._on_drag_end)
            row.add_controller(drag_source)

        row.set_child(content)
        return TrayRowWidgets(model, row, status, quick_button, drag_source)

    # Actions ----------------------------------------------------------------

    def _item(self, item_id: str) -> PocketItem | None:
        return next(
            (item for item in self._controller.items if item.id == item_id),
            None,
        )

    def _copy(self, item: PocketItem) -> None:
        clipboard = self._clipboard or self.window.get_clipboard()
        clipboard.set_content(
            clipboard_content_for(item, load_texture=self._load_texture)
        )

    def _open_text_detail(self, item: PocketItem) -> None:
        detail = PocketTextWindow(
            item,
            parent=self._owner,
            on_close=self._on_detail_window_closed,
        )
        self.detail_windows.append(detail)
        detail.present()

    def _on_detail_window_closed(self, detail: PocketTextWindow) -> None:
        if detail in self.detail_windows:
            self.detail_windows.remove(detail)

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        item_id = next(
            (key for key, widgets in self.rows.items() if widgets.row is row),
            None,
        )
        if item_id is not None:
            self.activate_primary(item_id)

    def _show_row_status(
        self,
        item_id: str,
        message: str,
        *,
        error: bool,
        timeout_ms: int | None = None,
    ) -> None:
        widgets = self.rows.get(item_id)
        if widgets is None:
            return
        self._cancel_feedback(item_id)
        widgets.status.set_text(message)
        if error:
            widgets.status.add_css_class("mochi-tray-error")
        else:
            widgets.status.remove_css_class("mochi-tray-error")
        widgets.status.set_visible(True)
        if timeout_ms is not None:
            self._feedback_sources[item_id] = GLib.timeout_add(
                timeout_ms, self._clear_row_status, item_id
            )

    def _clear_row_status(self, item_id: str) -> bool:
        self._feedback_sources.pop(item_id, None)
        widgets = self.rows.get(item_id)
        if widgets is not None:
            widgets.status.set_visible(False)
            widgets.status.set_text("")
        return GLib.SOURCE_REMOVE

    def _cancel_feedback(self, item_id: str) -> None:
        source_id = self._feedback_sources.pop(item_id, None)
        if source_id is not None:
            GLib.source_remove(source_id)

    def _cancel_all_feedback(self) -> None:
        for item_id in tuple(self._feedback_sources):
            self._cancel_feedback(item_id)

    # Drag out ---------------------------------------------------------------

    def _prepare_drag(self, item_id: str) -> Gdk.ContentProvider | None:
        item = self._item(item_id)
        return drag_content_for(item) if item is not None else None

    def _on_drag_begin(self, source, row: Gtk.ListBoxRow) -> None:
        self._dragging = True
        self._drag_cancelled = False
        source.set_icon(Gtk.WidgetPaintable.new(row), 0, 0)
        self._dwell.drag_started()

    def _on_drag_cancel(self, _source, _drag, _reason) -> bool:
        self._drag_cancelled = True
        return False

    def _on_drag_end(self, _source, _drag, _delete_data) -> None:
        delivered = not self._drag_cancelled
        self._dragging = False
        self._drag_cancelled = False
        self._dwell.drag_finished(delivered)

    # Window lifecycle -------------------------------------------------------

    def _present(self, *, focus: bool) -> None:
        if focus:
            self.window.present()
        elif not self.window.get_visible():
            self.window.realize()
            request_no_focus_on_map(self.window)
            self.window.set_visible(True)
        self._schedule_position()

    def _hide(self) -> None:
        self._stop_fill()
        self._cancel_position()
        self._cancel_all_feedback()
        self.view = None
        self._was_active = False
        if self.window.get_visible():
            self.window.set_visible(False)

    def _on_map(self, _window: Gtk.Window) -> None:
        request_keep_above(self.window)
        self._schedule_position()

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self._dwell.close()
        return True

    def _on_key_pressed(self, _controller, keyval: int, _keycode: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._dwell.close()
            return True
        return False

    def _on_active_changed(self, window, _pspec) -> None:
        if window.is_active():
            self._was_active = True
            return
        if self._was_active and not self._dragging and window.get_visible():
            self._dwell.close()

    def _start_fill(self) -> None:
        self._stop_fill()
        self._fill_tick_id = self.peek_bar.add_tick_callback(self._on_fill_tick)

    def _on_fill_tick(self, _widget, frame_clock) -> bool:
        now_us = frame_clock.get_frame_time()
        if self._fill_started_us is None:
            self._fill_started_us = now_us
        fraction = peek_fill_fraction(
            (now_us - self._fill_started_us) / 1000, self._fill_ms
        )
        self.peek_bar.set_fraction(fraction)
        if fraction >= 1.0:
            self._fill_tick_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _stop_fill(self) -> None:
        tick_id = self._fill_tick_id
        self._fill_tick_id = None
        if tick_id is not None:
            self.peek_bar.remove_tick_callback(tick_id)

    def _schedule_position(self) -> None:
        # Mapping and size allocation can settle after present(). Position on
        # the next loop turn and again shortly after, like MenuWindow.
        self._cancel_position()
        for delay_ms in (0, 24):
            self._add_position_source(delay_ms)

    def _add_position_source(self, delay_ms: int) -> None:
        cell: list[int] = []

        def fire() -> bool:
            if cell:
                self._position_sources.discard(cell[0])
            self._position_now()
            return GLib.SOURCE_REMOVE

        source_id = GLib.timeout_add(delay_ms, fire)
        cell.append(source_id)
        self._position_sources.add(source_id)

    def _cancel_position(self) -> None:
        for source_id in tuple(self._position_sources):
            GLib.source_remove(source_id)
        self._position_sources.clear()

    def _position_now(self) -> None:
        if not self.window.get_visible():
            return
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            return
        scale = _window_coordinate_scale(self._owner)
        owner_x, owner_y = owner_position
        width = self.window.get_width()
        height = self.window.get_height()
        if width <= 1:
            width = TRAY_WIDTH if self.view == "tray" else PEEK_WIDTH
        if height <= 1:
            height = 48
        monitors = self._owner.get_display().get_monitors()
        geometries = [
            monitors.get_item(index).get_geometry()
            for index in range(monitors.get_n_items())
        ]
        x, y = tray_position_for_anchor(
            owner_x,
            owner_y,
            round(self._owner.get_width() * scale),
            round(self._owner.get_height() * scale),
            width,
            height,
            geometries,
            coordinate_scale=scale,
        )
        move_window(self.window, x, y)
```

- [ ] **Step 5: Run the tray tests**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_tray.py`

Expected: all pass.

- [ ] **Step 6: Re-read the diff adversarially**

Check each of these:

- no `set_markup` anywhere in `pocket_tray.py`;
- every `GLib.timeout_add` and `add_tick_callback` is stored and removed in `_hide()`;
- `_on_drag_end` runs after `_on_drag_cancel` when a drag fails (GTK order: cancel, then end);
- the tray never calls `close_tray` directly; it always goes through `self._dwell.close()`.

- [ ] **Step 7: Commit**

```bash
git add src/mochi/x11.py src/mochi/pocket_tray.py tests/test_pocket_tray.py
git commit -m "feat(pocket): hover tray window with drag-out, copy, and peek bar"
```

---

### Task 5: The "Open by resting on Mochi" setting

**Files:**
- Modify: `src/mochi/config.py` (after `save_edge_roam`)
- Modify: `src/mochi/pocket_window.py` (constructor and new handler)
- Test: `tests/test_config.py`, `tests/test_pocket_window.py`

**Interfaces:**
- Consumes: `normalize_hover_delay_ms`, `POCKET_HOVER_DELAY_CHOICES_MS` and `DEFAULT_POCKET_HOVER_DELAY_MS` (Task 2).
- Produces:
  - `ConfigStore.load_pocket_hover_delay_ms() -> int`
  - `ConfigStore.save_pocket_hover_delay_ms(delay_ms: int) -> None`
  - `pocket_window.HOVER_DELAY_LABELS`
  - `PocketWindow(controller, *, launcher=..., hover_delay_ms=2000, on_hover_delay_changed=None)`
  - `PocketWindow.hover_delay_dropdown: Gtk.DropDown`

**Acceptance Criteria:**
- A missing key reads 2000. 0, 1500, 2000 and 3000 round-trip. Unsupported stored values read 2000, and saving one stores 2000.
- The dropdown shows the stored value (2500 shows "2 s").
- Choosing an option calls `on_hover_delay_changed` with milliseconds. Construction never calls it.
- The dropdown has an accessible label.

- [ ] **Step 1: Write the failing tests**

Add to `ConfigStoreTests` in `tests/test_config.py`:

```python
    def test_pocket_hover_delay_defaults_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertEqual(store.load_pocket_hover_delay_ms(), 2000)
            for delay in (0, 1500, 2000, 3000):
                store.save_pocket_hover_delay_ms(delay)
                self.assertEqual(store.load_pocket_hover_delay_ms(), delay)

    def test_unsupported_pocket_hover_delay_reads_as_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for raw in (2500, -1, True, "2000", None):
                path.write_text(json.dumps({"pocket_hover_delay_ms": raw}))
                self.assertEqual(ConfigStore(path).load_pocket_hover_delay_ms(), 2000)

    def test_saving_an_unsupported_delay_stores_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            ConfigStore(path).save_pocket_hover_delay_ms(2500)
            self.assertEqual(json.loads(path.read_text())["pocket_hover_delay_ms"], 2000)
```

Append to `tests/test_pocket_window.py`:

```python
def test_hover_setting_shows_the_stored_delay() -> None:
    assert PocketWindow(_Controller(), hover_delay_ms=3000).hover_delay_dropdown.get_selected() == 3
    assert PocketWindow(_Controller(), hover_delay_ms=0).hover_delay_dropdown.get_selected() == 0
    assert PocketWindow(_Controller(), hover_delay_ms=2500).hover_delay_dropdown.get_selected() == 2


def test_choosing_a_hover_delay_reports_milliseconds() -> None:
    changes: list[int] = []
    window = PocketWindow(_Controller(), on_hover_delay_changed=changes.append)
    assert changes == []

    window.hover_delay_dropdown.set_selected(0)
    window.hover_delay_dropdown.set_selected(1)

    assert changes == [0, 1500]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_config.py tests/test_pocket_window.py`

Expected: `AttributeError: 'ConfigStore' object has no attribute 'load_pocket_hover_delay_ms'` and `TypeError: ... unexpected keyword argument 'hover_delay_ms'`.

- [ ] **Step 3: Implement the config pair**

In `src/mochi/config.py`, add the import:

```python
from mochi.pocket_hover import DEFAULT_POCKET_HOVER_DELAY_MS, normalize_hover_delay_ms
```

Add after `save_edge_roam`:

```python
    def load_pocket_hover_delay_ms(self) -> int:
        """Return how long resting on Mochi takes to open Pocket; 0 is off."""
        try:
            value = self._load()["pocket_hover_delay_ms"]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return DEFAULT_POCKET_HOVER_DELAY_MS
        return normalize_hover_delay_ms(value)

    def save_pocket_hover_delay_ms(self, delay_ms: int) -> None:
        data = self._load_or_empty()
        data["pocket_hover_delay_ms"] = normalize_hover_delay_ms(delay_ms)
        self._save(data)
        self._logger.debug("Pocket hover delay: %s ms", data["pocket_hover_delay_ms"])
```

- [ ] **Step 4: Add the dropdown to `PocketWindow`**

In `src/mochi/pocket_window.py`, add:

```python
from mochi.pocket_hover import (
    DEFAULT_POCKET_HOVER_DELAY_MS,
    POCKET_HOVER_DELAY_CHOICES_MS,
    normalize_hover_delay_ms,
)

HOVER_DELAY_LABELS = ("Off", "1.5 s", "2 s", "3 s")
```

Change the constructor signature to:

```python
    def __init__(
        self,
        controller: PocketController,
        *,
        launcher: Callable[[str], None] = _launch_default,
        hover_delay_ms: int = DEFAULT_POCKET_HOVER_DELAY_MS,
        on_hover_delay_changed: Callable[[int], None] | None = None,
    ) -> None:
```

Store the callback next to `self._launcher = launcher`:

```python
        self._on_hover_delay_changed = on_hover_delay_changed
```

Directly after `card.append(subtitle)`, insert:

```python
        hover_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hover_label = Gtk.Label(label="Open by resting on Mochi")
        hover_label.set_xalign(0)
        hover_label.set_hexpand(True)
        hover_row.append(hover_label)
        self.hover_delay_dropdown = Gtk.DropDown.new_from_strings(
            list(HOVER_DELAY_LABELS)
        )
        self.hover_delay_dropdown.set_selected(
            POCKET_HOVER_DELAY_CHOICES_MS.index(
                normalize_hover_delay_ms(hover_delay_ms)
            )
        )
        self.hover_delay_dropdown.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Open Pocket by resting on Mochi"],
        )
        # Connect after the initial selection so construction never reports a change.
        self.hover_delay_dropdown.connect(
            "notify::selected", self._on_hover_delay_selected
        )
        hover_row.append(self.hover_delay_dropdown)
        card.append(hover_row)
```

Add the handler next to `_request_clear_all`:

```python
    def _on_hover_delay_selected(self, dropdown: Gtk.DropDown, _pspec) -> None:
        index = dropdown.get_selected()
        if not 0 <= index < len(POCKET_HOVER_DELAY_CHOICES_MS):
            return
        if self._on_hover_delay_changed is not None:
            self._on_hover_delay_changed(POCKET_HOVER_DELAY_CHOICES_MS[index])
```

- [ ] **Step 5: Run the tests**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_config.py tests/test_pocket_window.py`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/config.py src/mochi/pocket_window.py tests/test_config.py tests/test_pocket_window.py
git commit -m "feat(pocket): persist the hover-to-open delay and expose it in the Pocket window"
```

---

### Task 6: Wire it into Mochi

**Files:**
- Modify: `src/mochi/pocket_integration.py`
- Modify: `src/mochi/pocket_drop.py`
- Test: `tests/test_pocket_integration.py`, `tests/test_pocket_drop.py`

**Interfaces:**
- Consumes:
  - Task 1: `can_arm_pocket_hover` and `begin_offer`;
  - Task 2: `PocketHoverDwell` and the constants;
  - Task 4: `PocketTray`;
  - Task 5: the config pair and the new `PocketWindow` keywords;
  - from `Buddy`: `_on_enter`, `_on_leave`, `_on_motion`, `_on_pressed`, `_on_context_pressed`, `_press`, `_drag_started`, `_context_menu_open`, `_placement.layer_shell_enabled`, `_preview_mode`, `_config`, `_window`, and `state.presentation`.
- Produces:
  - `PocketBuddyMixin._pocket_dwell`, `_pocket_tray` and `_pocket_hover_delay_ms`;
  - `_pocket_hover_can_arm()`, `_open_pocket_from_menu()`, `_open_pocket_tray(focus)`, `_set_pocket_hover_delay(ms)`.

**Acceptance Criteria:**
- Enter, motion and leave reach both the base handler and the dwell.
- Press and right-click interrupt the dwell before the base handler runs.
- `_pocket_hover_can_arm()` is true in the ordinary case and false for each condition in the spec's arming list.
- `Pocket · N` defers to `_open_pocket_from_menu`, which opens the pinned tray. Preview or layer-shell mode opens the Pocket window instead.
- Opening the tray calls `begin_offer()` before `tray.open(focus=...)`, and opens even when the offer is refused.
- Item changes refresh an open tray. Shutdown runs `dwell.shutdown()` then `tray.destroy()`, then the existing teardown.
- The setting is loaded after `super().__init__`, normalized and saved on change, and passed into the Pocket window.
- `PocketDropAdapter` returns `Gdk.DragAction(0)` on enter and motion, and `False` on drop, for in-process drags, with no hover and no feedback.
- The full suite stays green.

- [ ] **Step 1: Write the failing integration tests**

In `tests/test_pocket_integration.py`, add these imports:

```python
from unittest.mock import Mock, call, patch

from mochi.state import MochiState, PresentationState
```

Update the existing tests whose harnesses now need the new attributes:

- In `test_pocket_menu_action_defers_window_until_menu_closes`, rename it to `test_pocket_menu_action_defers_the_tray_until_menu_closes`. Replace its body with:

```python
    harness = object.__new__(PocketBuddyMixin)
    harness._close_context_menu_then = Mock()

    harness._pocket_from_context_menu(None)

    harness._close_context_menu_then.assert_called_once_with(
        harness._open_pocket_from_menu
    )
```

- In `test_count_change_updates_menu_label_and_open_window` and `test_hidden_pocket_window_skips_row_rebuild_until_next_open`, add `harness._pocket_tray = None` after the harness is created.
- In `test_shutdown_detaches_drop_adapter_and_destroys_window`, add `harness._pocket_dwell = Mock()` and `harness._pocket_tray = None` before `shutdown_presence()`.

Then append:

```python
class _PointerBase:
    def _on_enter(self, controller, x, y):
        self.order.append("base-enter")

    def _on_leave(self, controller):
        self.order.append("base-leave")

    def _on_motion(self, controller, x, y):
        self.order.append("base-motion")

    def _on_pressed(self, gesture, presses, x, y):
        self.order.append("base-press")

    def _on_context_pressed(self, gesture, presses, x, y):
        self.order.append("base-context")


class _PointerHarness(PocketBuddyMixin, _PointerBase):
    pass


def _pointer_harness() -> _PointerHarness:
    harness = object.__new__(_PointerHarness)
    harness.order = []
    harness._pocket_dwell = Mock()
    for name in (
        "pointer_entered",
        "pointer_moved",
        "pointer_left",
        "interrupt",
    ):
        getattr(harness._pocket_dwell, name).side_effect = (
            lambda name=name: harness.order.append(name)
        )
    return harness


def test_pointer_events_reach_the_base_and_then_the_dwell() -> None:
    harness = _pointer_harness()

    harness._on_enter(None, 1.0, 2.0)
    harness._on_motion(None, 2.0, 3.0)
    harness._on_leave(None)

    assert harness.order == [
        "base-enter",
        "pointer_entered",
        "base-motion",
        "pointer_moved",
        "base-leave",
        "pointer_left",
    ]


def test_press_and_right_click_interrupt_before_the_base_runs() -> None:
    harness = _pointer_harness()

    harness._on_pressed(None, 1, 4.0, 5.0)
    harness._on_context_pressed(None, 1, 4.0, 5.0)

    assert harness.order == [
        "interrupt",
        "base-press",
        "interrupt",
        "base-context",
    ]


def _arm_harness() -> PocketBuddyMixin:
    harness = object.__new__(PocketBuddyMixin)
    harness._preview_mode = False
    harness._placement = SimpleNamespace(layer_shell_enabled=False)
    harness._pocket_controller = SimpleNamespace(count=2, busy=False, hover_active=False)
    harness._context_menu_open = False
    harness._press = None
    harness._drag_started = False
    harness.state = SimpleNamespace(
        current=MochiState.IDLE, presentation=PresentationState.NORMAL
    )
    harness._pocket_window = None
    return harness


def test_hover_can_arm_in_the_ordinary_case() -> None:
    assert _arm_harness()._pocket_hover_can_arm() is True


@pytest.mark.parametrize(
    "block",
    (
        lambda h: setattr(h, "_preview_mode", True),
        lambda h: setattr(h._placement, "layer_shell_enabled", True),
        lambda h: setattr(h._pocket_controller, "count", 0),
        lambda h: setattr(h._pocket_controller, "busy", True),
        lambda h: setattr(h._pocket_controller, "hover_active", True),
        lambda h: setattr(h, "_context_menu_open", True),
        lambda h: setattr(h, "_press", (3.0, 4.0)),
        lambda h: setattr(h, "_drag_started", True),
        lambda h: setattr(h.state, "presentation", PresentationState.LEVEL_UP),
        lambda h: setattr(
            h, "_pocket_window", SimpleNamespace(get_visible=lambda: True)
        ),
        lambda h: setattr(h.state, "current", MochiState.WALKING),
        lambda h: setattr(h.state, "current", MochiState.FEDORA),
        lambda h: setattr(h.state, "current", MochiState.DRAGGED),
    ),
    ids=(
        "preview",
        "layer-shell",
        "empty",
        "receiving",
        "drag-in",
        "menu",
        "press",
        "drag",
        "level-up",
        "window-open",
        "walking",
        "fedora",
        "dragged",
    ),
)
def test_hover_never_arms_when_something_else_owns_mochi(block) -> None:
    harness = _arm_harness()
    block(harness)

    assert harness._pocket_hover_can_arm() is False


def test_menu_opens_a_focused_tray_on_the_x11_path() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._preview_mode = False
    harness._placement = SimpleNamespace(layer_shell_enabled=False)
    harness._pocket_dwell = Mock()
    harness._show_pocket_window = Mock()

    harness._open_pocket_from_menu()

    harness._pocket_dwell.open_pinned.assert_called_once_with()
    harness._show_pocket_window.assert_not_called()


@pytest.mark.parametrize(("preview", "layer_shell"), ((True, False), (False, True)))
def test_menu_keeps_the_window_path_without_x11_placement(
    preview: bool, layer_shell: bool
) -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._preview_mode = preview
    harness._placement = SimpleNamespace(layer_shell_enabled=layer_shell)
    harness._pocket_dwell = Mock()
    harness._show_pocket_window = Mock()

    harness._open_pocket_from_menu()

    harness._show_pocket_window.assert_called_once_with()
    harness._pocket_dwell.open_pinned.assert_not_called()


def test_opening_the_tray_offers_first_and_opens_even_if_refused() -> None:
    harness = object.__new__(PocketBuddyMixin)
    order: list[str] = []
    harness._pocket_controller = Mock()
    harness._pocket_controller.begin_offer.side_effect = (
        lambda: order.append("offer") or False
    )
    harness._pocket_tray = Mock()
    harness._pocket_tray.open.side_effect = (
        lambda *, focus: order.append(f"open:{focus}")
    )

    assert harness._open_pocket_tray(False) is True
    assert order == ["offer", "open:False"]


def test_peek_shows_the_live_count() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_tray = Mock()
    harness._pocket_controller = SimpleNamespace(count=4)

    harness._show_pocket_peek(1400)

    harness._pocket_tray.show_peek.assert_called_once_with(4, 1400)


def test_hide_and_close_are_safe_before_the_tray_exists() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_tray = None

    harness._hide_pocket_peek()
    harness._close_pocket_tray()


def test_manage_closes_the_tray_then_opens_the_window() -> None:
    harness = object.__new__(PocketBuddyMixin)
    order: list[str] = []
    harness._pocket_dwell = Mock()
    harness._pocket_dwell.close.side_effect = lambda: order.append("close")
    harness._show_pocket_window = Mock(side_effect=lambda: order.append("window"))

    harness._manage_pocket_from_tray()

    assert order == ["close", "window"]


def test_count_change_refreshes_an_open_tray() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_label = Mock()
    harness._pocket_window = None
    harness._pocket_tray = Mock()

    harness._on_pocket_changed((object(),))

    harness._pocket_tray.refresh.assert_called_once_with()


def test_shutdown_stops_the_dwell_before_destroying_the_tray() -> None:
    harness = object.__new__(_ShutdownHarness)
    order: list[str] = []
    harness._pocket_dwell = Mock()
    harness._pocket_dwell.shutdown.side_effect = lambda: order.append("dwell")
    tray = Mock()
    tray.destroy.side_effect = lambda: order.append("tray")
    harness._pocket_tray = tray
    harness._pocket_drop = Mock()
    harness._pocket_window = Mock()
    harness.base_shutdown = False

    harness.shutdown_presence()

    assert order == ["dwell", "tray"]
    assert harness._pocket_tray is None
    assert harness.base_shutdown is True


def test_hover_delay_change_is_normalized_and_saved() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._config = Mock()
    harness._pocket_hover_delay_ms = 2000

    harness._set_pocket_hover_delay(3000)
    harness._set_pocket_hover_delay(2500)

    assert harness._pocket_hover_delay_ms == 2000
    assert harness._config.save_pocket_hover_delay_ms.call_args_list == [
        call(3000),
        call(2000),
    ]


def test_pocket_window_receives_the_current_hover_delay() -> None:
    harness = object.__new__(PocketBuddyMixin)
    harness._pocket_window = None
    harness._pocket_controller = Mock()
    harness._pocket_hover_delay_ms = 1500
    harness._window = Mock()

    with patch("mochi.pocket_integration.PocketWindow") as window_class:
        harness._show_pocket_window()

    window_class.assert_called_once_with(
        harness._pocket_controller,
        hover_delay_ms=1500,
        on_hover_delay_changed=harness._set_pocket_hover_delay,
    )
```

Append to `tests/test_pocket_drop.py`:

```python
class _Drop:
    def __init__(self, drag) -> None:
        self._drag = drag

    def get_drag(self):
        return self._drag


class _OwnDragTarget(_Target):
    def get_current_drop(self):
        return _Drop(drag=object())


def test_drags_that_start_inside_mochi_are_refused_silently(tmp_path: Path) -> None:
    from gi.repository import Gdk

    controller = _Controller()
    adapter = PocketDropAdapter(
        _Widget(), controller, target_factory=_OwnDragTarget
    )
    file_target = adapter.targets[0]
    document = tmp_path / "report.pdf"
    document.write_bytes(b"%PDF")

    assert file_target.callbacks["enter"](file_target, 1.0, 2.0) == Gdk.DragAction(0)
    assert file_target.callbacks["motion"](file_target, 1.0, 2.0) == Gdk.DragAction(0)
    assert file_target.callbacks["drop"](file_target, [_File(str(document))], 1.0, 2.0) is False

    assert controller.hover_starts == 0
    assert controller.received == []
    assert controller.rejections == 0
    assert controller.busy_rejections == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_integration.py tests/test_pocket_drop.py`

Expected: failures for the missing methods (`_open_pocket_from_menu`, `_pocket_hover_can_arm`, and so on) and for the drop guard.

- [ ] **Step 3: Replace `src/mochi/pocket_integration.py`**

Write the whole file. It keeps every existing behavior (glow, menu row, feedback, window) and adds the dwell and tray:

```python
"""Thin Buddy composition layer for the Pocket subsystem."""

from __future__ import annotations

from collections.abc import Sequence
import math
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from mochi.behavior import can_arm_pocket_hover
from mochi.pocket import PocketItem
from mochi.pocket_controller import PocketController
from mochi.pocket_drop import PocketDropAdapter
from mochi.pocket_hover import (
    DEFAULT_POCKET_HOVER_DELAY_MS,
    PocketHoverDwell,
    normalize_hover_delay_ms,
)
from mochi.pocket_store import PocketStore
from mochi.pocket_tray import PocketTray
from mochi.pocket_window import PocketWindow
from mochi.sprites import ANIMATIONS
from mochi.state import PresentationState


POCKET_GLOW_PERIOD_SECONDS = 1.15


def _pocket_glow_pulse(elapsed_seconds: float) -> float:
    """Return a smooth 0..1 breathing pulse for Pocket hover feedback."""
    elapsed = max(0.0, float(elapsed_seconds))
    phase = (elapsed % POCKET_GLOW_PERIOD_SECONDS) / POCKET_GLOW_PERIOD_SECONDS
    return 0.5 - 0.5 * math.cos(phase * math.tau)


class PocketBuddyMixin:
    """Compose Pocket services without moving their logic into Buddy."""

    def __init__(self, *args, **kwargs) -> None:
        self._pocket_label: Gtk.Label | None = None
        self._pocket_window: PocketWindow | None = None
        self._pocket_drop: PocketDropAdapter | None = None
        self._pocket_tray: PocketTray | None = None
        self._pocket_hover_delay_ms = DEFAULT_POCKET_HOVER_DELAY_MS
        store = getattr(self, "_pocket_store_override", None) or PocketStore()
        self._pocket_controller = PocketController(
            store,
            current_state=lambda: self.state.current,
            cancel_walk=self._cancel_walk,
            cancel_ambient=self._cancel_active_emote,
            transition=self._transition_to,
            play_animation=lambda name, after: self._play_animation(
                name, after=after
            ),
            mark_interaction=self._mark_interaction,
            resume_ambient=self._maybe_resume_ambient_activity,
            show_feedback=self._show_pocket_feedback,
            on_changed=self._on_pocket_changed,
        )
        self._pocket_dwell = PocketHoverDwell(
            delay_ms=lambda: self._pocket_hover_delay_ms,
            can_arm=self._pocket_hover_can_arm,
            show_peek=self._show_pocket_peek,
            hide_peek=self._hide_pocket_peek,
            open_tray=self._open_pocket_tray,
            close_tray=self._close_pocket_tray,
        )
        super().__init__(*args, **kwargs)
        self._pocket_hover_delay_ms = self._config.load_pocket_hover_delay_ms()
        if not self._preview_mode:
            self._pocket_drop = PocketDropAdapter(self, self._pocket_controller)

    def _draw(self, area, context, width: int, height: int) -> None:
        """Add a breathing Pocket acceptance glow behind the Buddy render."""
        if self._pocket_controller.hover_active:
            now = time.monotonic()
            started_at = getattr(self, "_pocket_glow_started_at", None)
            if started_at is None or now < started_at:
                started_at = now
                self._pocket_glow_started_at = now

            frame = self.player.frame
            if frame is None:
                frame = ANIMATIONS["default"].frames[0]
            self.atlas.draw_glow(
                context,
                frame,
                width,
                height,
                pulse=_pocket_glow_pulse(now - started_at),
            )
        else:
            self._pocket_glow_started_at = None
        super()._draw(area, context, width, height)

    # Pointer: always run the existing handler, then feed the dwell. Presses
    # interrupt first so a click or right-click wins before anything else runs.

    def _on_enter(self, controller, x: float, y: float) -> None:
        super()._on_enter(controller, x, y)
        self._pocket_dwell.pointer_entered()

    def _on_leave(self, controller) -> None:
        super()._on_leave(controller)
        self._pocket_dwell.pointer_left()

    def _on_motion(self, controller, x: float, y: float) -> None:
        super()._on_motion(controller, x, y)
        self._pocket_dwell.pointer_moved()

    def _on_pressed(self, gesture, presses: int, x: float, y: float) -> None:
        self._pocket_dwell.interrupt()
        super()._on_pressed(gesture, presses, x, y)

    def _on_context_pressed(self, gesture, presses: int, x: float, y: float) -> None:
        self._pocket_dwell.interrupt()
        super()._on_context_pressed(gesture, presses, x, y)

    def _pocket_hover_can_arm(self) -> bool:
        controller = self._pocket_controller
        window = self._pocket_window
        return (
            not self._preview_mode
            and not self._placement.layer_shell_enabled
            and controller.count > 0
            and not controller.busy
            and not controller.hover_active
            and not self._context_menu_open
            and self._press is None
            and not self._drag_started
            and self.state.presentation is PresentationState.NORMAL
            and not (window is not None and window.get_visible())
            and can_arm_pocket_hover(self.state.current)
        )

    # Tray -------------------------------------------------------------------

    def _ensure_pocket_tray(self) -> PocketTray:
        if self._pocket_tray is None:
            self._pocket_tray = PocketTray(
                owner=self._window,
                controller=self._pocket_controller,
                dwell=self._pocket_dwell,
                on_manage=self._manage_pocket_from_tray,
                show_feedback=self._show_pocket_feedback,
            )
        return self._pocket_tray

    def _show_pocket_peek(self, fill_ms: int) -> None:
        self._ensure_pocket_tray().show_peek(self._pocket_controller.count, fill_ms)

    def _hide_pocket_peek(self) -> None:
        if self._pocket_tray is not None:
            self._pocket_tray.hide_peek()

    def _open_pocket_tray(self, focus: bool) -> bool:
        tray = self._ensure_pocket_tray()
        # Presentation only: the tray opens even when Mochi is waking or busy.
        self._pocket_controller.begin_offer()
        tray.open(focus=focus)
        return True

    def _close_pocket_tray(self) -> None:
        if self._pocket_tray is not None:
            self._pocket_tray.close()

    def _manage_pocket_from_tray(self) -> None:
        self._pocket_dwell.close()
        self._show_pocket_window()

    # Context menu -------------------------------------------------------------

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        button, self._pocket_label = self._make_menu_button(
            f"Pocket · {self._pocket_controller.count}",
            "folder-download-symbolic",
            self._pocket_from_context_menu,
        )
        self._register_context_menu_row(
            "pocket",
            button,
            before="sleep",
        )
        return menu

    def _pocket_from_context_menu(self, _button: Gtk.Button) -> None:
        self._close_context_menu_then(self._open_pocket_from_menu)

    def _open_pocket_from_menu(self) -> None:
        if self._preview_mode or self._placement.layer_shell_enabled:
            # No X11 root coordinates to anchor a tray: keep the window path.
            self._show_pocket_window()
            return
        self._pocket_dwell.open_pinned()

    # Window and setting -------------------------------------------------------

    def _show_pocket_window(self) -> None:
        if self._pocket_window is None:
            self._pocket_window = PocketWindow(
                self._pocket_controller,
                hover_delay_ms=self._pocket_hover_delay_ms,
                on_hover_delay_changed=self._set_pocket_hover_delay,
            )
            self._pocket_window.set_transient_for(self._window)
        else:
            self._pocket_window.refresh()
        self._pocket_window.present()

    def _set_pocket_hover_delay(self, delay_ms: int) -> None:
        self._pocket_hover_delay_ms = normalize_hover_delay_ms(delay_ms)
        self._config.save_pocket_hover_delay_ms(self._pocket_hover_delay_ms)

    def _on_pocket_changed(self, items: Sequence[PocketItem]) -> None:
        if self._pocket_label is not None:
            self._pocket_label.set_text(f"Pocket · {len(items)}")
        if (
            self._pocket_window is not None
            and self._pocket_window.get_visible()
        ):
            self._pocket_window.refresh()
        if self._pocket_tray is not None:
            self._pocket_tray.refresh()

    def _show_pocket_feedback(self, message: str) -> None:
        show_feedback = getattr(self, "show_nameplate_feedback", None)
        if callable(show_feedback):
            show_feedback(message)
        else:
            self._logger.info("Pocket: %s", message)

    def shutdown_presence(self) -> None:
        # Stop the dwell first so no timer can call into a destroyed tray.
        self._pocket_dwell.shutdown()
        if self._pocket_tray is not None:
            self._pocket_tray.destroy()
            self._pocket_tray = None
        if self._pocket_drop is not None:
            self._pocket_drop.detach()
            self._pocket_drop = None
        if self._pocket_window is not None:
            self._pocket_window.destroy()
            self._pocket_window = None
        super().shutdown_presence()
```

Before saving, diff your copy against `git show HEAD:src/mochi/pocket_integration.py`. Every pre-existing line must still be present, apart from the changed `_pocket_from_context_menu` target and the `PocketWindow(...)` constructor call.

- [ ] **Step 4: Refuse in-process drags in `src/mochi/pocket_drop.py`**

Replace the `drop` connection in `_install_target` with:

```python
        target.connect(
            "drop",
            lambda target, value, _x, _y: (
                False if self._is_own_drag(target) else self._on_drop(value, receive)
            ),
        )
```

Replace `_on_enter` and `_on_motion` with:

```python
    def _on_enter(self, target, _x: float, _y: float) -> Gdk.DragAction:
        if self._is_own_drag(target):
            return Gdk.DragAction(0)
        return self._drag_action()

    def _on_motion(self, target, _x: float, _y: float) -> Gdk.DragAction:
        if self._is_own_drag(target):
            return Gdk.DragAction(0)
        return self._drag_action()

    @staticmethod
    def _is_own_drag(target) -> bool:
        """A drag out of Mochi's own Pocket tray must never re-enter it."""
        get_drop = getattr(target, "get_current_drop", None)
        drop = get_drop() if callable(get_drop) else None
        get_drag = getattr(drop, "get_drag", None)
        return callable(get_drag) and get_drag() is not None
```

- [ ] **Step 5: Run the integration, drop, and every Pocket test**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_pocket_integration.py tests/test_pocket_drop.py tests/test_pocket*.py`

Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider`

Expected: the baseline 1363 plus the new tests pass, with 6 skipped. Report the actual summary line. No existing test constructs `PocketBuddyMixin` through `__init__` (checked 2026-10-06: they all use `object.__new__`), so the new `self._config.load_pocket_hover_delay_ms()` call has no test double to update.

- [ ] **Step 7: Commit**

```bash
git add src/mochi/pocket_integration.py src/mochi/pocket_drop.py tests/test_pocket_integration.py tests/test_pocket_drop.py
git commit -m "feat(pocket): rest on Mochi to open the Pocket tray"
```

---

### Task 7: Documentation, full verification, and the manual QA handoff

**Files:**
- Modify: `CHANGELOG.md` (Unreleased)
- Modify: `README.md` ("What's new lately" and Controls)
- Modify: `REGRESSION_WATCHLIST.md` (`## Pocket`)
- Modify: `docs/CODEBASE_MANUAL.md` (§11 `## Hover/motion`)

**Interfaces:**
- Consumes: the shipped behavior from Tasks 1–6.
- Produces: user and maintainer documentation only.

**Acceptance Criteria:**
- CHANGELOG Unreleased has the Added and Changed entries below, and keeps every existing entry.
- The README Controls table has the new row, and "What's new lately" has the new bullet first.
- REGRESSION_WATCHLIST `## Pocket` has the new checklist lines.
- CODEBASE_MANUAL §11 has the Pocket dwell paragraph.
- The full suite passes, and the final report lists the manual QA steps as unverified.

- [ ] **Step 1: CHANGELOG**

Under `## Unreleased` → `### Added`, after the Agent Companion entry, add:

```markdown
- Rest your pointer on Mochi for two seconds and a small tray pops out of his
  mouth with everything in his Pocket. Click a row to open it (text copies
  instead), use the little button beside it to copy a link or show a file in
  its folder, or drag it straight into another app. Move away and it tucks
  itself back in. A bar fills while you wait, so passing over him never opens
  anything. Change the wait, or turn it off, with **Open by resting on Mochi**
  in the Pocket window.
```

Add a `### Changed` section after `### Added` (still under Unreleased):

```markdown
### Changed

- **Pocket · N** in the right-click menu now opens the same tray, with
  keyboard focus (arrow keys, Enter, Esc). **Manage Pocket…** at the bottom of
  the tray opens the full Pocket window for removing and clearing.
```

- [ ] **Step 2: README**

Add as the first bullet under `## What's new lately`:

```markdown
-  **Pocket tray** — rest your pointer on Mochi for two seconds and the things
  he's holding pop out in a little tray. Click to open, or drag them straight
  into another app.
```

In the `## Controls` table, add after the `Drag` row:

```markdown
| Rest the pointer on Mochi (2 s) | Open the Pocket tray when he's holding something |
```

- [ ] **Step 3: REGRESSION_WATCHLIST**

Append to `## Pocket`:

```markdown
- [ ] Passing over Mochi without stopping never shows the peek bar or the tray
- [ ] Resting on Mochi shows the peek at about 0.6 s and opens the tray at the chosen dwell, with the mouth animation when he is free
- [ ] Leaving before the dwell ends hides the peek and changes nothing
- [ ] The hover tray does not take keyboard focus from the app being typed in
- [ ] Moving from Mochi into the tray keeps it open; leaving both closes it after about half a second
- [ ] Closing the tray while still resting on Mochi does not reopen it until the pointer leaves
- [ ] Mochi walking under a resting pointer never opens the tray
- [ ] Hovering a sleeping Mochi wakes him (existing behavior) and the tray still opens
- [ ] Each kind: click, quick action, and drag into Files, a browser, and a text editor
- [ ] Dragging a tray item back onto Mochi is refused without a reaction
- [ ] `Pocket · N` opens the focused tray; arrows, Enter, Tab, and Esc work; clicking elsewhere closes it
- [ ] `Manage Pocket…` opens the Pocket window; Open by resting on Mochi persists across restarts, and Off disables the dwell
- [ ] The tray flips below Mochi near the top edge and stays on Mochi's monitor
- [ ] Native Wayland layer-shell mode keeps `Pocket · N` → Pocket window
```

- [ ] **Step 4: CODEBASE_MANUAL §11**

Under `## Hover/motion`, after "Hover behavior must remain independent from click/drag/right-click hit testing.", add:

```markdown
PocketBuddyMixin extends _on_enter, _on_leave, _on_motion, _on_pressed, and _on_context_pressed to drive PocketHoverDwell (pocket_hover.py). It always calls super(), never changes the hover heart, and arms only on pointer motion, so Mochi walking under a resting pointer never opens the Pocket tray. The arm and offer state tables live in behavior.py (can_arm_pocket_hover, can_start_pocket_offer).
```

- [ ] **Step 5: Full verification**

Run each of these:

- `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider`
- `git diff --check main...HEAD`
- `python3 -m compileall -q src` (catches syntax errors for the CI compile step)

Then confirm by reading `pyproject.toml` that the package data patterns and package discovery cover `src/mochi/*.py`. All four new modules (`pocket_hover`, `pocket_actions`, `pocket_tray`, plus the tests) are plain modules in existing packages, so no packaging change is expected.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md README.md REGRESSION_WATCHLIST.md docs/CODEBASE_MANUAL.md
git commit -m "docs(pocket): hover tray changelog, controls, watchlist, and manual"
```

- [ ] **Step 7: Final report**

Follow `AGENTS.md` → "Final report" and include:

- summary;
- files changed;
- tests added;
- the exact test command and its summary line;
- **unverified:** all 15 manual Fedora/GNOME steps from the spec, listed verbatim for the maintainer, with focus-steal (step 4) and cross-app drag (step 9) called out as the highest risk;
- risks considered (focus on map, the XWayland DnD bridge, the `EXCITED` overlap during the offer);
- follow-ups noticed but not done.

## Spec Coverage

| Spec requirement | Task |
|---|---|
| Arm on motion, not enter; arm-state table; all arm conditions | 1, 2, 6 |
| Peek at 600 ms with fill; open at dwell; configurable delay | 2, 4, 5 |
| Silent cancels (leave, press, right-click, condition loss, Off) | 2, 6 |
| Re-arm rule | 2 |
| Sleeping/waking arm without animation; hover wake unchanged | 1, 6 |
| Offer animation via `EXCITED`, cancelling `HEART` | 1 |
| Tray placement above, flip, clamp, nearest monitor | 4 |
| Rows from `row_model`; per-kind primary, quick, drag | 4 |
| Feedback: close on primary, inline Copied, inline error | 4 |
| Drag never closed mid-drag; delivered closes; cancelled stays | 2, 4 |
| Refuse dragging a tray item back onto Mochi | 6 |
| Grace close 450 ms; pinned tray ignores pointer leave | 2 |
| No-focus hover map; focused menu open; keys | 4 |
| `Pocket · N` opens the tray; layer-shell fallback | 6 |
| Setting: Off / 1.5 / 2 / 3 s, persisted, normalized | 5, 6 |
| Shared launch rule for window and tray | 3 |
| Teardown order and owned sources | 2, 4, 6 |
| Docs: CHANGELOG, README, watchlist, manual | 7 |
| Manual Fedora/GNOME QA, reported separately | 7 |
