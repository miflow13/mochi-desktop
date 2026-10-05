# Active Window Curiosity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use beads-superpowers:subagent-driven-development (recommended) or beads-superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent <epic-id>`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.

**Goal:** Mochi notices window switches and settled browser tabs. When standing idle he plays a one-pass magnifying-glass `investigate` beat; when busy he shows a tiny overlay cue. Habituation keeps it calm, and no window title or app identity ever reaches Mochi.

**Architecture:** Revive PR #133 by merging its branch, then layer on three things:
- A payload-free `BrowserTabChanged` pulse from the GNOME extension. It covers browser windows only, uses a digest for change detection, and is gated on recent user input.
- A generalized idle-look lifecycle (`_play_idle_beat`), so the investigate beat reuses the existing interruption and resume handling.
- A rewritten `ActiveWindowCuriosityMixin` with a debounce/settle trigger, a beat → cue → drop ladder, habituation and a suspend-aware clock.

Behavior state (`MochiState`) is never touched.

**Tech Stack:** Python 3.11+, GTK4/PyGObject, Cairo, GLib timers, GNOME Shell extension (GJS ESM), D-Bus, pytest.

**Spec:** `docs/superpowers/specs/2026-10-05-active-window-curiosity-design.md`

## Global Constraints

- No window title, URL, application ID or content leaves GNOME Shell. `BrowserTabChanged` carries **no payload**.
- The extension keeps only a SHA-256 digest of the normalized focused-browser title, in memory. It never logs, stores or sends the title.
- Only browser-classified windows have their titles observed.
- All tab logic stays inside `gnome-extension/mochi-typing@miflow13/extension.js`, with **no new JS module**: `scripts/install-typing-extension.sh:53` copies files by name.
- Curiosity never changes `MochiState` or `PresentationState`.
- The investigate beat runs only through `IdleLookMixin._play_idle_beat`. `_idle_look_active` stays the single "a standing-idle beat owns presentation" flag.
- All curiosity timing uses `_curiosity_now()`, which is `CLOCK_BOOTTIME` with a `time.monotonic()` fallback.
- Constants (exact values):
  - `CURIOSITY_DEBOUNCE_MS = 180`
  - `CURIOSITY_TAB_SETTLE_MS = 1500`
  - `CURIOSITY_BEAT_COOLDOWN_SECONDS = 120.0`
  - `CURIOSITY_BEAT_COOLDOWN_CAP_SECONDS = 600.0`
  - `CURIOSITY_CUE_COOLDOWN_SECONDS = 20.0`
  - `CURIOSITY_CUE_COOLDOWN_CAP_SECONDS = 120.0`
  - `CURIOSITY_HABITUATION_FACTOR = 1.5`
  - `CURIOSITY_HABITUATION_RESET_SECONDS = 300.0`
  - `CURIOSITY_CUE_DURATION_SECONDS = 1.8`
  - `CURIOSITY_LEAN_PX = 4.0`
  - `CURIOSITY_BUBBLE_MIN_SIZE_PX = 80`
  - `CURIOSITY_BEAT_ANIMATION = "investigate"`
  - `TAB_INPUT_WINDOW_MS = 2000`
- The lean is rounded to whole device pixels. Below 80 px there is no bubble, only the lean.
- **Test command.** In this container the default `python3` is 3.11 and has no `gi`; GTK bindings exist for 3.12. Always run:
  - `PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider <paths>`
  - CI runs `xvfb-run -a python3 -m pytest -q`.
- Baseline on `main` @ `515cf14`: **1044 passed, 3 skipped**.
- Commits end with the session attribution trailer:

  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
  ```

- Work on branch `claude/optimistic-volta-9jc07e` only.

## File Map

| File | Responsibility | Task |
|---|---|---|
| `CHANGELOG.md` | Merge conflict resolution, then the final entry | 1, 6 |
| `src/mochi/sprites.py` | `investigate` = one-pass `searching` | 2 |
| `src/mochi/presence/idle_look.py` | One lifecycle for standing-idle beats (`_play_idle_beat`) | 2 |
| `tests/test_idle_beats.py` (new) | Beat lifecycle tests | 2 |
| `tests/test_sprites.py` | `investigate` shape test | 2 |
| `src/mochi/presence/signals.py` | `BrowserTabChanged` subscription + `on_tab_changed` | 3 |
| `src/mochi/presence/integration.py` | Wire `on_tab_changed`, base no-op hook | 3 |
| `tests/test_presence_engine.py`, `tests/test_helper_lifecycle.py`, `tests/test_helper_dbus_integration.py` | Signal tests and subscription counts | 3 |
| `src/mochi/presence/curiosity.py` | Triggers, ladder, habituation, clock, cue rendering | 4 |
| `tests/test_active_window_curiosity.py` | Rewritten curiosity tests | 4 |
| `gnome-extension/mochi-typing@miflow13/extension.js` | Browser title tracking, input gate, `BrowserTabChanged` | 5 |
| `tests/test_gnome_shortcuts.py` | Extension source-contract tests + installer guard | 5 |
| `gnome-extension/mochi-typing@miflow13/README.md`, `docs/ambisense.md`, `REGRESSION_WATCHLIST.md` | Signal, privacy and QA docs | 6 |
| `docs/CODEBASE_MANUAL.md` | §6 real layer order + why curiosity is a mixin + idle-beat ownership | 6 |

`src/mochi/presence/click_dialogue.py` already gains `ActiveWindowCuriosityMixin` before `IdleLookMixin` from the PR #133 merge in Task 1; Task 4 verifies it.

---

### Task 1: Merge PR #133 and establish a green baseline

**Files:**
- Modify: `CHANGELOG.md` (conflict resolution only)
- Merge: `origin/feat/active-window-curiosity` (brings `src/mochi/presence/curiosity.py`, `tests/test_active_window_curiosity.py`, and PR #133's edits to `signals.py`, `integration.py`, `click_dialogue.py`, `extension.js`, the extension README and four test files)

**Interfaces:**
- Consumes: nothing.
- Produces: everything PR #133 added on top of `main`:
  - the `AppFocusChanged` extension signal, `extension.js` `_emitAppFocus(category)` and `_updateAppCategory()` returning the category;
  - `AppCategorySignalAdapter(on_focus_changed=...)` with `FOCUS_SIGNAL_NAME = "AppFocusChanged"`;
  - `integration.py` `_on_presence_app_focus_changed(category)`;
  - `ActiveWindowCuriosityMixin` in both buddy class lists, immediately before `IdleLookMixin`.

**Acceptance Criteria:**
- A merge commit whose only manual change is the `CHANGELOG.md` conflict resolution.
- `CHANGELOG.md` keeps every `main` entry, and Unreleased gains an `### Added` section containing PR #133's line.
- The full suite passes on the merge commit. A trial merge on 2026-10-05 gave **1059 passed, 3 skipped**: 1044 plus PR #133's 15 tests.
- `git diff --check` is clean.

- [ ] **Step 1: Fetch and start the merge**

```bash
cd /home/user/mochi-desktop
git fetch origin feat/active-window-curiosity main
git merge --no-ff --no-commit origin/feat/active-window-curiosity
git status --short
```

Expected: `UU CHANGELOG.md`, with other files staged as `M`/`A` and no other conflicts.

- [ ] **Step 2: Resolve `CHANGELOG.md`**

Open `CHANGELOG.md`, remove the conflict markers, and keep **all** of `main`'s Unreleased content (`### Changed`, `### Fixed`). Insert this section directly under `## Unreleased`, before `### Changed`:

```markdown
### Added

- Added a subtle Active Window Curiosity cue that notices privacy-reduced app-focus changes without interrupting Mochi's current behavior.

```

Then check that no markers remain and the file is staged:

```bash
grep -n '^<<<<<<<\|^=======\|^>>>>>>>' CHANGELOG.md || echo "no markers"
git add CHANGELOG.md
git diff --cached --check && echo clean
```

Expected: `no markers`, then `clean`.

- [ ] **Step 3: Run the full suite on the merged tree**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -5
```

Expected: `1059 passed, 3 skipped` (verified by a trial merge on 2026-10-05). If anything fails, do **not** fold a fix into the merge. Commit the merge first (Step 4), then fix the drift in a separate commit `fix: adapt active window curiosity to current main`, re-running this command until it is green.

- [ ] **Step 4: Commit the merge**

```bash
git commit -F - <<'EOF'
Merge PR #133 (active window curiosity) into current main

Brings feat/active-window-curiosity forward 492 commits. The only manual
change is resolving CHANGELOG.md: main's Unreleased entries are kept and
PR #133's line moves under a new Added section.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
EOF
git log --oneline -3
```

---

### Task 2: Investigate beat through a shared idle-beat lifecycle

**Files:**
- Modify: `src/mochi/sprites.py`, after the line `ANIMATIONS["excited"] = replace(ANIMATIONS["bounce"], name="excited")`
- Modify: `src/mochi/presence/idle_look.py`
- Create: `tests/test_idle_beats.py`
- Modify: `tests/test_sprites.py`

**Interfaces:**
- Consumes: `ANIMATIONS["searching"]`, which has 20 frames at 120 ms each, `looping=True`.
- Produces:
  - `ANIMATIONS["investigate"]`: an `Animation` with `name="investigate"`, `looping=False`, and the same frames as `searching`.
  - `IdleLookMixin._play_idle_beat(self, name: str) -> bool`. It returns `False` without side effects unless `_can_start_idle_look()`; otherwise it saves the idle resume position, sets `_idle_look_active = True` and `_idle_beat_animation = name`, plays `ANIMATIONS[name]`, and returns `True`.
  - `IdleLookMixin._idle_beat_animation: str | None`.
  - `_play_idle_look()` keeps its signature and delegates to `_play_idle_beat(self.IDLE_LOOK_ANIMATION)`.

**Acceptance Criteria:**
- `ANIMATIONS["investigate"].looping is False`, and its frames equal `ANIMATIONS["searching"].frames`.
- Finishing an `investigate` beat resumes idle at the saved frame and elapsed time, clears `_idle_look_active` and `_idle_beat_animation`, and resumes ambient activity.
- Starting typing, or calling `_play_animation` with any other name, during the beat restores idle first.
- `_play_idle_beat` refuses when Mochi is not in the standing-idle visual.
- The existing `tests/test_nameplate_mood.py::NameplateMoodTransitionTests::test_idle_look_restores_the_installed_sad_idle_animation` passes unchanged.

- [ ] **Step 1: Write the failing sprite test**

Append to the test class in `tests/test_sprites.py` that contains `test_dance_is_an_eight_frame_loop`. Match the class's indentation (one level inside the class):

```python
    def test_investigate_is_a_one_pass_searching_beat(self) -> None:
        investigate = ANIMATIONS["investigate"]
        self.assertEqual(investigate.name, "investigate")
        self.assertFalse(investigate.looping)
        self.assertEqual(investigate.frames, ANIMATIONS["searching"].frames)
        # The file-activity loop keeps its own looping definition.
        self.assertTrue(ANIMATIONS["searching"].looping)
```

- [ ] **Step 2: Write the failing beat tests**

Create `tests/test_idle_beats.py`:

```python
"""Standing-idle beats share one lifecycle: the timed look and the investigate beat."""

from __future__ import annotations

from unittest.mock import Mock

from mochi.animation import AnimationPlayer
from mochi.presence.idle_look import IdleLookMixin
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState, StateMachine


class _BeatBase:
    def __init__(self, *args, **kwargs) -> None:
        # Preview mode keeps IdleLookMixin from arming real GLib timers.
        self._preview_mode = True
        self._presence_shutting_down = False
        self._user_idle = False
        self.state = StateMachine()
        self.player = AnimationPlayer(on_finished=self._finish_reaction)
        self.player.play(ANIMATIONS["idle"], frame_index=2, elapsed_ms=40)
        self._current_animation = "idle"
        self._active_animation = ANIMATIONS["idle"]
        self._pending_animation = None
        self._logger = Mock()
        self.queue_draw = Mock()
        self.base_finished: list[str] = []
        self.base_played: list[str] = []
        self.ambient_resumes = 0

    def _is_idle_visual_active(self) -> bool:
        return (
            self.state.current is MochiState.IDLE
            and self._current_animation == "idle"
            and self.player.animation is not None
        )

    def _animation_for(self, name: str):
        return ANIMATIONS[name]

    def _finish_reaction(self, finished_animation) -> None:
        self.base_finished.append(finished_animation.name)

    def _play_animation(self, name: str, after: str | None = None) -> None:
        self.base_played.append(name)
        self._current_animation = name

    def _maybe_resume_ambient_activity(self) -> bool:
        self.ambient_resumes += 1
        return False

    def _start_typing_emote(self) -> bool:
        self.base_played.append("typing")
        return True

    def shutdown_presence(self) -> None:
        pass


class BeatHarness(IdleLookMixin, _BeatBase):
    pass


def _finish_current_animation(buddy: BeatHarness) -> None:
    buddy.player.tick(60_000)


def test_investigate_beat_plays_without_claiming_behavior_state() -> None:
    buddy = BeatHarness()

    assert buddy._play_idle_beat("investigate") is True

    assert buddy._idle_look_active is True
    assert buddy._idle_beat_animation == "investigate"
    assert buddy._current_animation == "investigate"
    assert buddy.player.animation is ANIMATIONS["investigate"]
    assert buddy.state.current is MochiState.IDLE


def test_investigate_beat_resumes_idle_where_it_left_off() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    _finish_current_animation(buddy)

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy._current_animation == "idle"
    assert buddy.player.animation is ANIMATIONS["idle"]
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)
    assert buddy.ambient_resumes == 1
    assert buddy.base_finished == []


def test_beat_refuses_when_not_standing_idle() -> None:
    buddy = BeatHarness()
    buddy.state.transition_to(MochiState.TYPING)

    assert buddy._play_idle_beat("investigate") is False

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.player.animation is ANIMATIONS["idle"]


def test_typing_during_beat_restores_idle_before_typing() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    assert buddy._start_typing_emote() is True

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.base_played == ["typing"]
    assert buddy.ambient_resumes == 0


def test_other_animation_during_beat_restores_idle_first() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    buddy._play_animation("bounce")

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
    assert buddy.base_played == ["bounce"]


def test_timed_look_uses_the_same_lifecycle() -> None:
    buddy = BeatHarness()

    assert buddy._play_idle_look() is True
    assert buddy._idle_beat_animation == "look"
    _finish_current_animation(buddy)

    assert buddy._idle_look_active is False
    assert buddy._current_animation == "idle"
    assert (buddy.player.frame_index, buddy.player.elapsed_ms) == (2, 40)


def test_look_timer_firing_mid_beat_reschedules_instead_of_playing() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True
    buddy._schedule_idle_look = Mock()

    assert buddy._try_idle_look() is False  # GLib.SOURCE_REMOVE

    buddy._schedule_idle_look.assert_called_once_with()
    assert buddy._idle_beat_animation == "investigate"


def test_shutdown_clears_the_active_beat() -> None:
    buddy = BeatHarness()
    assert buddy._play_idle_beat("investigate") is True

    buddy.shutdown_presence()

    assert buddy._idle_look_active is False
    assert buddy._idle_beat_animation is None
```

- [ ] **Step 3: Run the new tests to see them fail**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_idle_beats.py tests/test_sprites.py
```

Expected: FAIL. You should see `KeyError: 'investigate'` and `AttributeError: ... '_play_idle_beat'`.

- [ ] **Step 4: Add the `investigate` animation**

In `src/mochi/sprites.py`, directly after `ANIMATIONS["excited"] = replace(ANIMATIONS["bounce"], name="excited")`:

```python
# Curiosity's standing-idle beat: one pass of the magnifying-glass art. The
# file-activity "searching" emote keeps its own looping definition.
ANIMATIONS["investigate"] = replace(
    ANIMATIONS["searching"], name="investigate", looping=False
)
```

- [ ] **Step 5: Generalize `idle_look.py`**

Make these edits in `src/mochi/presence/idle_look.py`.

5a. Add a module-level helper after the imports, before `class IdleLookMixin`:

```python
def _active_idle_beat(buddy) -> str:
    """Name of the beat that owns standing-idle presentation.

    Read with getattr: some tests call these methods unbound on harnesses that
    never ran ``IdleLookMixin.__init__``.
    """
    return getattr(buddy, "_idle_beat_animation", None) or buddy.IDLE_LOOK_ANIMATION
```

5b. Replace the class docstring:

```python
    """Own Mochi's short standing-idle beats.

    The timed glance-around (``look``) and curiosity's ``investigate`` beat both
    play while behavior state stays ``IDLE``. ``_idle_look_active`` is the single
    flag meaning "a standing-idle beat owns presentation"; ``_idle_beat_animation``
    names which beat. Any real state transition restores idle first.
    """
```

5c. In `__init__`, add `self._idle_beat_animation: str | None = None` directly after `self._idle_look_active = False`.

5d. Replace the whole `_play_idle_look` method with these two methods:

```python
    def _play_idle_look(self) -> bool:
        return self._play_idle_beat(self.IDLE_LOOK_ANIMATION)

    def _play_idle_beat(self, name: str) -> bool:
        """Play one standing-idle beat, then resume idle where it left off."""
        if not self._can_start_idle_look():
            return False
        self._idle_look_resume_position = (
            self.player.frame_index,
            self.player.elapsed_ms,
        )
        self._idle_look_active = True
        self._idle_beat_animation = name
        self._current_animation = name
        self._active_animation = ANIMATIONS[name]
        self._pending_animation = None
        self.player.play(self._active_animation)
        self._logger.debug("Animation: idle -> %s", name)
        self.queue_draw()
        return True
```

5e. In `_restore_idle_after_look`:
- Add `beat = _active_idle_beat(self)` as the method's first line.
- Add `self._idle_beat_animation = None` directly after `self._idle_look_active = False`.
- In the `self._logger.debug("Animation: %s -> idle (resumed%s)", ...)` call, replace the argument `self.IDLE_LOOK_ANIMATION` with `beat`.

5f. In `_finish_reaction`, replace `and self._current_animation == self.IDLE_LOOK_ANIMATION` with `and self._current_animation == _active_idle_beat(self)`.

5g. In `_play_animation`, replace `if self._idle_look_active and name != self.IDLE_LOOK_ANIMATION:` with `if self._idle_look_active and name != _active_idle_beat(self):`.

5h. In `shutdown_presence`, add `self._idle_beat_animation = None` directly after `self._idle_look_active = False`.

- [ ] **Step 6: Run the targeted tests to see them pass**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_idle_beats.py tests/test_sprites.py tests/test_nameplate_mood.py tests/test_focus_context_recovery.py
```

Expected: all passed.

- [ ] **Step 7: Run the full suite**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: 0 failed.

- [ ] **Step 8: Commit**

```bash
git add src/mochi/sprites.py src/mochi/presence/idle_look.py tests/test_idle_beats.py tests/test_sprites.py
git commit -F - <<'EOF'
feat: share the idle-look lifecycle with an investigate beat

Adds a one-pass "investigate" animation built from the searching art and
generalizes IdleLookMixin into one owner for standing-idle beats, so
curiosity can reuse its interruption and idle-resume handling without a
new flag or behavior state.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
EOF
```

---

### Task 3: Receive `BrowserTabChanged` in Mochi

**Files:**
- Modify: `src/mochi/presence/signals.py` (`AppCategorySignalAdapter`, as merged in Task 1)
- Modify: `src/mochi/presence/integration.py` (adapter construction and base hooks, as merged in Task 1)
- Modify: `tests/test_presence_engine.py`, `tests/test_helper_lifecycle.py`, `tests/test_helper_dbus_integration.py`

**Interfaces:**
- Consumes: Task 1's adapter, which has `FOCUS_SIGNAL_NAME` and `on_focus_changed`.
- Produces:
  - `AppCategorySignalAdapter.TAB_SIGNAL_NAME = "BrowserTabChanged"`;
  - the constructor kwarg `on_tab_changed: Callable[[], None] | None = None`;
  - the handler `_on_tab_signal(self, *_signal_args) -> None`;
  - `PresenceBuddyMixin._on_presence_browser_tab_changed(self) -> None`, a no-op base hook that Task 4 overrides.

**Acceptance Criteria:**
- A `BrowserTabChanged` D-Bus signal invokes `on_tab_changed()` exactly once and does not change `adapter.category`.
- With no `on_tab_changed`, the signal is ignored without error.
- The adapter subscribes to exactly `{"AppCategoryChanged", "AppFocusChanged", "BrowserTabChanged"}`.
- `integration.py` passes `on_tab_changed=self._on_presence_browser_tab_changed`.

- [ ] **Step 1: Write the failing adapter tests**

Append to `tests/test_presence_engine.py`:

```python
def test_browser_tab_signal_invokes_tab_callback_without_changing_category():
    from mochi.presence.signals import AppCategorySignalAdapter

    tabs = []
    adapter = AppCategorySignalAdapter(
        on_category_changed=lambda _category: None,
        on_tab_changed=lambda: tabs.append(True),
    )
    adapter.category = "browser"

    adapter._on_tab_signal(None, None, None, None, None, None)

    assert tabs == [True]
    assert adapter.category == "browser"


def test_browser_tab_signal_without_callback_is_ignored():
    from mochi.presence.signals import AppCategorySignalAdapter

    adapter = AppCategorySignalAdapter(on_category_changed=lambda _category: None)

    adapter._on_tab_signal(None, None, None, None, None, None)

    assert adapter.category == "unknown"
```

In `tests/test_helper_lifecycle.py`, inside `test_app_category_owner_replacement_clears_and_resyncs`, replace the subscription assertions that PR #133 added:

```python
    assert len(bus.subscriptions) == 2
    subscribed_signals = {args[2] for args in bus.subscriptions.values()}
    assert subscribed_signals == {"AppCategoryChanged", "AppFocusChanged"}
```

with:

```python
    assert len(bus.subscriptions) == 3
    subscribed_signals = {args[2] for args in bus.subscriptions.values()}
    assert subscribed_signals == {
        "AppCategoryChanged",
        "AppFocusChanged",
        "BrowserTabChanged",
    }
```

In `tests/test_helper_dbus_integration.py`, change the subscription-count list from `[2, 2, 2, 3, 1]` to `[2, 2, 3, 3, 1]`. This test is opt-in through an environment variable and skipped by default, but it must still be correct.

- [ ] **Step 2: Run them to see them fail**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_presence_engine.py tests/test_helper_lifecycle.py
```

Expected: FAIL with `TypeError: ... unexpected keyword argument 'on_tab_changed'`, `AttributeError: ... '_on_tab_signal'`, and the subscription count `2 != 3`.

- [ ] **Step 3: Extend the adapter**

In `src/mochi/presence/signals.py`, inside `class AppCategorySignalAdapter`:

3a. Below `FOCUS_SIGNAL_NAME = "AppFocusChanged"`, add:

```python
    TAB_SIGNAL_NAME = "BrowserTabChanged"
```

3b. In `__init__`, add the parameter `on_tab_changed: Callable[[], None] | None = None,` after `on_focus_changed`, and add the assignment `self._on_tab_changed = on_tab_changed` after `self._on_focus_changed = on_focus_changed`.

3c. In `start()`, add a third entry to the signal dict passed to `HelperConnection`:

```python
            {
                self.SIGNAL_NAME: self._on_category_signal,
                self.FOCUS_SIGNAL_NAME: self._on_focus_signal,
                self.TAB_SIGNAL_NAME: self._on_tab_signal,
            },
```

3d. Add this method directly after `_on_focus_signal`:

```python
    def _on_tab_signal(self, *_signal_args) -> None:
        """Forward a payload-free pulse: the focused browser settled on new content.

        The extension sends no title, URL, or identity, and only emits after
        real user input, so there is nothing to validate beyond delivery.
        """
        self._logger.debug("[presence] browser tab changed")
        if self._on_tab_changed is not None:
            self._on_tab_changed()
```

3e. Add this sentence to the end of the class docstring, after "...without affecting Mochi.":

```
    ``BrowserTabChanged`` is a payload-free pulse for a settled browser tab or
    page change; older extensions never emit it.
```

- [ ] **Step 4: Wire the integration hook**

In `src/mochi/presence/integration.py`:

4a. In the `AppCategorySignalAdapter(...)` construction, add `on_tab_changed=self._on_presence_browser_tab_changed,` after `on_focus_changed=self._on_presence_app_focus_changed,`.

4b. Add this method directly after `_on_presence_app_focus_changed`:

```python
    def _on_presence_browser_tab_changed(self) -> None:
        """Receive a payload-free tab/page pulse; curiosity overrides this hook."""
```

- [ ] **Step 5: Run the tests to see them pass**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_presence_engine.py tests/test_helper_lifecycle.py tests/test_helper_dbus_integration.py
```

Expected: all passed (the D-Bus integration test is skipped).

- [ ] **Step 6: Run the full suite**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: 0 failed.

- [ ] **Step 7: Commit**

```bash
git add src/mochi/presence/signals.py src/mochi/presence/integration.py tests/test_presence_engine.py tests/test_helper_lifecycle.py tests/test_helper_dbus_integration.py
git commit -F - <<'EOF'
feat: receive payload-free BrowserTabChanged pulses

The app-category adapter subscribes to a third AmbiSense signal and
forwards it through a new presence hook. The pulse carries no data;
older extensions simply never emit it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
EOF
```

---

### Task 4: Rewrite the curiosity mixin (ladder, habituation, clock, cue rendering)

**Files:**
- Rewrite: `src/mochi/presence/curiosity.py`
- Rewrite: `tests/test_active_window_curiosity.py`
- Verify only: `src/mochi/presence/click_dialogue.py`, where `ActiveWindowCuriosityMixin` is listed immediately before `IdleLookMixin` in both `PresenceBuddy` and `PresenceX11Buddy`

**Interfaces:**
- Consumes:
  - `_play_idle_beat(name) -> bool` (Task 2);
  - `_on_presence_app_focus_changed(category)` (Task 1);
  - `_on_presence_browser_tab_changed()` (Task 3);
  - from the buddy: `state` (`StateMachine`), `queue_draw()`, `_logger`, `_placement`, `_ambient_presence_engine.tuning`, `_preview_mode`, `_presence_shutting_down`, `_user_idle`, `_context_menu_open`, `_press`, `_drag_started`;
  - the chained base hooks `_draw`, `_tick`, `_on_pressed`, `shutdown_presence`.
- Produces:
  - `_boottime_seconds(clock=time) -> float` (module level);
  - `ActiveWindowCuriosityMixin._curiosity_now() -> float`;
  - `_habituated_cooldown(base, cap, streak) -> float` (classmethod);
  - `_react_to_curiosity(reason: str) -> str`, which returns one of `"beat"`, `"cue"`, `"drop"`;
  - `_curiosity_lean_offsets(progress, direction, scale) -> tuple[int, int]`.

**Acceptance Criteria:**
- **Clock:** `_boottime_seconds` uses `CLOCK_BOOTTIME` when present and falls back to `monotonic()` when it is missing or raises `OSError`.
- **Cooldowns:** `_habituated_cooldown` returns `min(base * 1.5**streak, cap)`.
- **Triggers:**
  - a category reclassification on its own never schedules curiosity (ported from PR #133);
  - a window pulse schedules a 180 ms debounce, but only for allowed categories;
  - tab pulses restart one 1.5 s settle;
  - the latest pulse replaces a pending one;
  - nothing is scheduled while shutting down or in preview.
- **Ladder:** idle gives a beat; busy (typing) gives a cue; inside the shared gap gives a drop; inside the beat cooldown but past the gap gives a cue; idle inside the gap after a cue gives a drop.
- **Habituation:** the gap grows with the streak, and an eligible trigger 300 s or more after the previous one resets it. Suppressed triggers leave the streak and last-trigger time untouched.
- **Suppression:** each of these gives a drop:
  - user idle, context menu open, press, drag, preview, shutdown;
  - presentation not `NORMAL`;
  - `SLEEPING` / `WAKING`;
  - quiet mode, or ambient reactions off.

  `WATCHING` gives a drop through the ladder.
- **Lifecycle:**
  - press, shutdown and expiry clear the cue;
  - a cue continues across cue-allowed states;
  - a direct press clears an active cue on the next tick;
  - behavior state never changes.
- **Rendering:**
  - lean offsets are ints;
  - `_draw` translates by ints;
  - the bubble is skipped below 80 px and drawn at 80 px and up;
  - a cue render differs from the baseline.
- **Production class lists:** both buddies list `ActiveWindowCuriosityMixin` immediately before `IdleLookMixin`.

- [ ] **Step 1: Replace the test file**

Overwrite `tests/test_active_window_curiosity.py` with:

```python
"""Regression coverage for active-window curiosity."""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cairo
import pytest

from mochi.presence import curiosity
from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
from mochi.presence.curiosity import ActiveWindowCuriosityMixin
from mochi.presence.idle_look import IdleLookMixin
from mochi.state import MochiState, PresentationState, StateMachine


class _CuriosityBase:
    def __init__(self) -> None:
        self._presence_app_category = "browser"
        self._preview_mode = False
        self._presence_shutting_down = False
        self._user_idle = False
        self._context_menu_open = False
        self._press = None
        self._drag_started = False
        self._ambient_presence_engine = SimpleNamespace(
            tuning=SimpleNamespace(ambient_reactions_enabled=True, quiet_mode=False)
        )
        self.state = StateMachine()
        self.queue_draw = Mock()
        self._logger = Mock()
        self._placement = None
        self.idle_visual = True
        self.beats: list[str] = []
        self.focus_events: list[str] = []
        self.tab_events = 0
        self.base_press_args = None
        self.base_shutdown_called = False

    def _play_idle_beat(self, name: str) -> bool:
        if not self.idle_visual:
            return False
        self.beats.append(name)
        return True

    def _on_presence_app_category_changed(self, category: str) -> None:
        self._presence_app_category = category

    def _on_presence_app_focus_changed(self, category: str) -> None:
        self.focus_events.append(category)

    def _on_presence_browser_tab_changed(self) -> None:
        self.tab_events += 1

    def _draw(self, _area, context, _width: int, _height: int) -> None:
        context.rectangle(48, 78, 16, 24)
        context.set_source_rgba(0.2, 0.6, 0.3, 1.0)
        context.fill()

    def _tick(self) -> bool:
        return True

    def _on_pressed(self, *args) -> None:
        self.base_press_args = args

    def shutdown_presence(self) -> None:
        self.base_shutdown_called = True


class CuriosityHarness(ActiveWindowCuriosityMixin, _CuriosityBase):
    pass


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now


@pytest.fixture
def clock(monkeypatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(
        ActiveWindowCuriosityMixin, "_curiosity_now", lambda _self: fake.now
    )
    return fake


def _busy(buddy: CuriosityHarness, state: MochiState = MochiState.TYPING) -> None:
    buddy.idle_visual = False
    buddy.state.transition_to(state)


# -- Clock and pacing ---------------------------------------------------------


def test_clock_prefers_boottime() -> None:
    calls = []
    fake = SimpleNamespace(
        CLOCK_BOOTTIME=7,
        clock_gettime=lambda clock_id: calls.append(clock_id) or 42.0,
        monotonic=lambda: 1.0,
    )

    assert curiosity._boottime_seconds(fake) == 42.0
    assert calls == [7]


def test_clock_falls_back_without_boottime() -> None:
    fake = SimpleNamespace(monotonic=lambda: 9.5)

    assert curiosity._boottime_seconds(fake) == 9.5


def test_clock_falls_back_when_boottime_errors() -> None:
    def broken(_clock_id):
        raise OSError("unsupported")

    fake = SimpleNamespace(CLOCK_BOOTTIME=7, clock_gettime=broken, monotonic=lambda: 3.0)

    assert curiosity._boottime_seconds(fake) == 3.0


def test_habituated_cooldown_grows_and_clamps() -> None:
    cooldown = ActiveWindowCuriosityMixin._habituated_cooldown

    assert cooldown(20.0, 120.0, 0) == 20.0
    assert cooldown(20.0, 120.0, 1) == 30.0
    assert cooldown(20.0, 120.0, 2) == 45.0
    assert cooldown(20.0, 120.0, 10) == 120.0
    assert cooldown(120.0, 600.0, 4) == 600.0


# -- Triggers -----------------------------------------------------------------


def test_window_focus_pulse_schedules_debounced_reaction() -> None:
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add", return_value=11) as timeout_add:
        buddy._on_presence_app_focus_changed("browser")

    assert buddy.focus_events == ["browser"]
    timeout_add.assert_called_once_with(
        buddy.CURIOSITY_DEBOUNCE_MS, buddy._fire_curiosity
    )
    assert buddy._curiosity_source_id == 11
    assert buddy._curiosity_pending_reason == "window:browser"


def test_unrecognized_focus_category_is_ignored() -> None:
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_app_focus_changed("spreadsheet")

    timeout_add.assert_not_called()
    assert buddy._curiosity_source_id is None


def test_category_reclassification_does_not_trigger_curiosity() -> None:
    # Ported from PR #133: categories can change while focus stays on the same
    # window (e.g. late identity), and only the focus/tab pulses mean attention moved.
    buddy = CuriosityHarness()

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_app_category_changed("terminal")

    assert buddy._presence_app_category == "terminal"
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None
    timeout_add.assert_not_called()


def test_tab_pulses_restart_one_settle_timer() -> None:
    buddy = CuriosityHarness()

    with patch.object(
        curiosity.GLib, "timeout_add", side_effect=[1, 2, 3]
    ) as timeout_add, patch.object(curiosity.GLib, "source_remove") as source_remove:
        for _ in range(3):
            buddy._on_presence_browser_tab_changed()

    assert buddy.tab_events == 3
    assert [call.args[0] for call in timeout_add.call_args_list] == [1500, 1500, 1500]
    assert [call.args[0] for call in source_remove.call_args_list] == [1, 2]
    assert buddy._curiosity_source_id == 3
    assert buddy._curiosity_pending_reason == "tab"


def test_window_pulse_replaces_pending_tab_settle() -> None:
    buddy = CuriosityHarness()

    with patch.object(
        curiosity.GLib, "timeout_add", side_effect=[5, 6]
    ) as timeout_add, patch.object(curiosity.GLib, "source_remove") as source_remove:
        buddy._on_presence_browser_tab_changed()
        buddy._on_presence_app_focus_changed("terminal")

    source_remove.assert_called_once_with(5)
    assert timeout_add.call_args_list[-1].args[0] == buddy.CURIOSITY_DEBOUNCE_MS
    assert buddy._curiosity_source_id == 6
    assert buddy._curiosity_pending_reason == "window:terminal"


def test_nothing_is_scheduled_while_shutting_down() -> None:
    buddy = CuriosityHarness()
    buddy._presence_shutting_down = True

    with patch.object(curiosity.GLib, "timeout_add") as timeout_add:
        buddy._on_presence_browser_tab_changed()

    timeout_add.assert_not_called()


def test_firing_runs_the_pending_reaction_once(clock) -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 9
    buddy._curiosity_pending_reason = "tab"

    assert buddy._fire_curiosity() == curiosity.GLib.SOURCE_REMOVE

    assert buddy.beats == ["investigate"]
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None


# -- Reaction ladder ----------------------------------------------------------


def test_idle_trigger_plays_investigate_beat(clock) -> None:
    buddy = CuriosityHarness()

    assert buddy._react_to_curiosity("tab") == "beat"

    assert buddy.beats == ["investigate"]
    assert buddy._curiosity_cue_active is False
    assert buddy.state.current is MochiState.IDLE


def test_busy_trigger_shows_cue_without_changing_state(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)

    assert buddy._react_to_curiosity("window:terminal") == "cue"

    assert buddy.beats == []
    assert buddy._curiosity_cue_active is True
    assert buddy.state.current is MochiState.TYPING
    buddy.queue_draw.assert_called_once_with()


def test_trigger_inside_reaction_gap_is_dropped(clock) -> None:
    buddy = CuriosityHarness()
    assert buddy._react_to_curiosity("tab") == "beat"

    clock.now += 10.0
    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy.beats == ["investigate"]


def test_trigger_inside_beat_cooldown_falls_back_to_cue(clock) -> None:
    buddy = CuriosityHarness()
    assert buddy._react_to_curiosity("tab") == "beat"

    clock.now += 31.0  # past the habituated 30 s gap, inside the 180 s beat cooldown
    assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy.beats == ["investigate"]


def test_idle_trigger_soon_after_a_cue_is_dropped_not_beat(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"

    buddy.idle_visual = True
    buddy.state.transition_to(MochiState.IDLE)
    clock.now += 25.0
    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy.beats == []


def test_habituation_lengthens_the_gap(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"  # streak 1, next gap 30 s
    clock.now += 30.0
    assert buddy._react_to_curiosity("tab") == "cue"  # streak 2, next gap 45 s
    clock.now += 44.0
    assert buddy._react_to_curiosity("tab") == "drop"
    clock.now += 1.0
    assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy._curiosity_streak == 3


def test_long_quiet_period_resets_habituation(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    for step in (0.0, 30.0, 45.0):
        clock.now += step
        assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy._curiosity_streak == 3

    clock.now += buddy.CURIOSITY_HABITUATION_RESET_SECONDS
    assert buddy._react_to_curiosity("tab") == "cue"
    assert buddy._curiosity_streak == 1


def test_suppressed_trigger_does_not_touch_habituation(clock) -> None:
    buddy = CuriosityHarness()
    buddy._ambient_presence_engine.tuning.quiet_mode = True

    assert buddy._react_to_curiosity("tab") == "drop"

    assert buddy._curiosity_last_trigger_at == -math.inf
    assert buddy._curiosity_streak == 0
    assert buddy.beats == []


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("_user_idle", True),
        ("_context_menu_open", True),
        ("_press", (12.0, 18.0)),
        ("_drag_started", True),
        ("_preview_mode", True),
        ("_presence_shutting_down", True),
    ],
)
def test_direct_and_lifecycle_suppression(clock, attribute, value) -> None:
    buddy = CuriosityHarness()
    setattr(buddy, attribute, value)

    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy.beats == []
    assert buddy._curiosity_cue_active is False


def test_special_presentation_suppresses(clock) -> None:
    buddy = CuriosityHarness()
    buddy.state.presentation = PresentationState.LEVEL_UP

    assert buddy._react_to_curiosity("tab") == "drop"


@pytest.mark.parametrize("state", [MochiState.SLEEPING, MochiState.WAKING])
def test_sleep_suppresses(clock, state) -> None:
    buddy = CuriosityHarness()
    _busy(buddy, state)

    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy._curiosity_last_trigger_at == -math.inf


def test_ambient_reactions_off_suppresses(clock) -> None:
    buddy = CuriosityHarness()
    buddy._ambient_presence_engine.tuning.ambient_reactions_enabled = False

    assert buddy._react_to_curiosity("tab") == "drop"


def test_watching_drops_through_the_ladder(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy, MochiState.WATCHING)

    assert buddy._react_to_curiosity("tab") == "drop"
    assert buddy._curiosity_cue_active is False
    assert buddy._curiosity_last_trigger_at == clock.now


# -- Lifecycle ----------------------------------------------------------------


def test_press_cancels_pending_and_clears_cue() -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 42
    buddy._curiosity_pending_reason = "tab"
    buddy._curiosity_cue_active = True

    with patch.object(curiosity.GLib, "source_remove") as source_remove:
        buddy._on_pressed("gesture", 1, 12.0, 18.0)

    source_remove.assert_called_once_with(42)
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_reason is None
    assert buddy._curiosity_cue_active is False
    assert buddy.base_press_args == ("gesture", 1, 12.0, 18.0)


def test_shutdown_cancels_pending_and_preserves_chain() -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 42
    buddy._curiosity_pending_reason = "window:terminal"
    buddy._curiosity_cue_active = True

    with patch.object(curiosity.GLib, "source_remove") as source_remove:
        buddy.shutdown_presence()

    source_remove.assert_called_once_with(42)
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_cue_active is False
    assert buddy.base_shutdown_called is True


def test_cue_expires_without_changing_state(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"

    clock.now += buddy.CURIOSITY_CUE_DURATION_SECONDS
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is False
    assert buddy.state.current is MochiState.TYPING


def test_cue_continues_across_cue_allowed_states(clock) -> None:
    buddy = CuriosityHarness()
    buddy.idle_visual = False  # IDLE state but not the idle visual: cue, not beat
    assert buddy._react_to_curiosity("window:vscode") == "cue"

    buddy.state.transition_to(MochiState.TYPING)
    buddy.queue_draw.reset_mock()
    clock.now += 0.7
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is True
    buddy.queue_draw.assert_called_once_with()


def test_direct_press_clears_active_cue_on_next_tick(clock) -> None:
    buddy = CuriosityHarness()
    _busy(buddy)
    assert buddy._react_to_curiosity("tab") == "cue"

    buddy._press = (1.0, 2.0)
    clock.now += 0.2
    assert buddy._tick() is True

    assert buddy._curiosity_cue_active is False


# -- Rendering ----------------------------------------------------------------


def _render(buddy: CuriosityHarness, size: int = 112) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    context = cairo.Context(surface)
    buddy._draw(None, context, size, size)
    surface.flush()
    return bytes(surface.get_data())


def test_cue_render_differs_from_baseline(clock) -> None:
    buddy = CuriosityHarness()
    baseline = _render(buddy)

    buddy._curiosity_cue_active = True
    buddy._curiosity_cue_started_at = clock.now - 0.6
    curious = _render(buddy)

    assert curious != baseline


def test_lean_offsets_are_whole_pixels() -> None:
    buddy = CuriosityHarness()

    for progress in (0.05, 0.1, 0.17, 0.4, 0.75, 0.9, 0.99):
        for scale in (0.57, 1.0, 1.37, 2.29):
            for direction in (1, -1):
                dx, dy = buddy._curiosity_lean_offsets(progress, direction, scale)
                assert isinstance(dx, int) and isinstance(dy, int)


def test_draw_translates_by_whole_pixels(clock) -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_cue_active = True
    buddy._curiosity_cue_started_at = clock.now - 0.1  # mid ease-in
    context = Mock()

    buddy._draw(None, context, 137, 137)

    dx, dy = context.translate.call_args_list[0].args
    assert isinstance(dx, int) and isinstance(dy, int)


@pytest.mark.parametrize(("size", "bubble"), [(64, False), (79, False), (80, True), (112, True)])
def test_bubble_only_at_readable_sizes(clock, size, bubble) -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_cue_active = True
    buddy._curiosity_cue_started_at = clock.now - 0.6

    with patch.object(ActiveWindowCuriosityMixin, "_draw_curiosity_bubble") as draw_bubble:
        _render(buddy, size)

    assert draw_bubble.called is bubble


# -- Production composition ---------------------------------------------------


@pytest.mark.parametrize("buddy_type", [PresenceBuddy, PresenceX11Buddy])
def test_curiosity_wraps_the_idle_beat_owner(buddy_type) -> None:
    bases = buddy_type.__bases__
    assert bases.index(ActiveWindowCuriosityMixin) + 1 == bases.index(IdleLookMixin)
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_active_window_curiosity.py 2>&1 | tail -5
```

Expected: FAIL. You should see `AttributeError` for `_boottime_seconds`, `_habituated_cooldown`, `_fire_curiosity`, `_react_to_curiosity` and `_curiosity_lean_offsets`.

- [ ] **Step 3: Rewrite `src/mochi/presence/curiosity.py`**

Overwrite the file with:

```python
"""Brief curiosity when Mochi notices a window switch or a settled browser tab."""

from __future__ import annotations

import math
import time

import cairo
from gi.repository import GLib

from mochi.state import MochiState, PresentationState


def _boottime_seconds(clock=time) -> float:
    """Seconds on a clock that keeps counting while the machine is suspended.

    ``time.monotonic()`` pauses during suspend, so overnight a long habituation
    streak would never reset and cooldowns would stretch across the sleep.
    """
    clock_id = getattr(clock, "CLOCK_BOOTTIME", None)
    if clock_id is not None:
        try:
            return clock.clock_gettime(clock_id)
        except OSError:
            pass
    return clock.monotonic()


class ActiveWindowCuriosityMixin:
    """Notice attention changes without claiming Mochi's behavior state.

    AmbiSense sends a coarse app category when window focus changes and a
    payload-free pulse when the focused browser settles on new content after
    user input. Curiosity never reads window titles, application IDs, or
    screen content.

    Standing-idle Mochi borrows the idle-look lifecycle for one ``investigate``
    beat; otherwise he shows a short overlay cue. Neither path changes
    ``MochiState``. Reactions habituate during busy sessions.
    """

    CURIOSITY_DEBOUNCE_MS = 180
    CURIOSITY_TAB_SETTLE_MS = 1500
    CURIOSITY_BEAT_COOLDOWN_SECONDS = 120.0
    CURIOSITY_BEAT_COOLDOWN_CAP_SECONDS = 600.0
    CURIOSITY_CUE_COOLDOWN_SECONDS = 20.0
    CURIOSITY_CUE_COOLDOWN_CAP_SECONDS = 120.0
    CURIOSITY_HABITUATION_FACTOR = 1.5
    CURIOSITY_HABITUATION_RESET_SECONDS = 300.0
    CURIOSITY_CUE_DURATION_SECONDS = 1.8
    CURIOSITY_LEAN_PX = 4.0
    CURIOSITY_BUBBLE_MIN_SIZE_PX = 80
    CURIOSITY_BEAT_ANIMATION = "investigate"

    _CURIOSITY_CATEGORIES = frozenset(
        ("vscode", "editor", "terminal", "browser", "media", "pixel_art", "unknown")
    )
    _CURIOSITY_CUE_STATES = frozenset(
        (
            MochiState.IDLE,
            MochiState.BLINKING,
            MochiState.WALKING,
            MochiState.TYPING,
            MochiState.COMPUTER,
        )
    )
    _CURIOSITY_SLEEP_STATES = frozenset((MochiState.SLEEPING, MochiState.WAKING))

    # Class-level defaults: every value is immutable, and some tests build
    # production buddies with ``__new__`` without running mixin initializers.
    _curiosity_source_id: int | None = None
    _curiosity_pending_reason: str | None = None
    _curiosity_cue_active = False
    _curiosity_cue_started_at = 0.0
    _curiosity_last_trigger_at = -math.inf
    _curiosity_last_reaction_at = -math.inf
    _curiosity_last_beat_at = -math.inf
    _curiosity_streak = 0

    # -- Clock and pacing ---------------------------------------------------

    def _curiosity_now(self) -> float:
        return _boottime_seconds()

    @classmethod
    def _habituated_cooldown(cls, base: float, cap: float, streak: int) -> float:
        """Stretch a cooldown for each recent reaction, up to its cap."""
        return min(base * cls.CURIOSITY_HABITUATION_FACTOR ** max(0, streak), cap)

    # -- Triggers -------------------------------------------------------------

    def _on_presence_app_focus_changed(self, category: str) -> None:
        super()._on_presence_app_focus_changed(category)
        if category in self._CURIOSITY_CATEGORIES:
            # A quick Alt-Tab pass should not flash a reaction.
            self._schedule_curiosity(self.CURIOSITY_DEBOUNCE_MS, f"window:{category}")

    def _on_presence_browser_tab_changed(self) -> None:
        super()._on_presence_browser_tab_changed()
        # Every pulse restarts the settle, so flicking through tabs produces
        # one reaction once the user lands.
        self._schedule_curiosity(self.CURIOSITY_TAB_SETTLE_MS, "tab")

    def _schedule_curiosity(self, delay_ms: int, reason: str) -> None:
        """Replace any pending trigger; the latest attention change wins."""
        self._cancel_curiosity_source()
        if getattr(self, "_presence_shutting_down", False) or getattr(
            self, "_preview_mode", False
        ):
            return
        self._curiosity_pending_reason = reason
        self._curiosity_source_id = GLib.timeout_add(delay_ms, self._fire_curiosity)

    def _fire_curiosity(self) -> bool:
        self._curiosity_source_id = None
        reason = self._curiosity_pending_reason
        self._curiosity_pending_reason = None
        if reason is not None:
            self._react_to_curiosity(reason)
        return GLib.SOURCE_REMOVE

    def _cancel_curiosity_source(self) -> None:
        source_id = self._curiosity_source_id
        self._curiosity_source_id = None
        self._curiosity_pending_reason = None
        if source_id is None:
            return
        try:
            GLib.source_remove(source_id)
        except Exception:
            pass

    # -- Decision -------------------------------------------------------------

    def _curiosity_allowed(self) -> bool:
        if (
            getattr(self, "_preview_mode", False)
            or getattr(self, "_presence_shutting_down", False)
            or getattr(self, "_user_idle", False)
            or getattr(self, "_context_menu_open", False)
            or getattr(self, "_press", None) is not None
            or getattr(self, "_drag_started", False)
        ):
            return False
        state = getattr(self, "state", None)
        if state is None or state.presentation is not PresentationState.NORMAL:
            return False
        if state.current in self._CURIOSITY_SLEEP_STATES:
            return False
        engine = getattr(self, "_ambient_presence_engine", None)
        tuning = getattr(engine, "tuning", None)
        if tuning is None:
            return True
        return bool(
            getattr(tuning, "ambient_reactions_enabled", True)
            and not getattr(tuning, "quiet_mode", False)
        )

    def _curiosity_cue_allowed(self) -> bool:
        return (
            self._curiosity_allowed()
            and self.state.current in self._CURIOSITY_CUE_STATES
        )

    def _react_to_curiosity(self, reason: str) -> str:
        """Take the first allowed reaction: ``"beat"``, ``"cue"``, or ``"drop"``."""
        if not self._curiosity_allowed():
            # Suppressed triggers never count toward habituation.
            return "drop"

        now = self._curiosity_now()
        if (
            now - self._curiosity_last_trigger_at
            >= self.CURIOSITY_HABITUATION_RESET_SECONDS
        ):
            self._curiosity_streak = 0
        self._curiosity_last_trigger_at = now

        streak = self._curiosity_streak
        reaction_gap = self._habituated_cooldown(
            self.CURIOSITY_CUE_COOLDOWN_SECONDS,
            self.CURIOSITY_CUE_COOLDOWN_CAP_SECONDS,
            streak,
        )
        if now - self._curiosity_last_reaction_at < reaction_gap:
            return "drop"

        beat_cooldown = self._habituated_cooldown(
            self.CURIOSITY_BEAT_COOLDOWN_SECONDS,
            self.CURIOSITY_BEAT_COOLDOWN_CAP_SECONDS,
            streak,
        )
        if now - self._curiosity_last_beat_at >= beat_cooldown and self._play_idle_beat(
            self.CURIOSITY_BEAT_ANIMATION
        ):
            self._curiosity_last_beat_at = now
            reaction = "beat"
        elif self._curiosity_cue_allowed():
            self._curiosity_cue_active = True
            self._curiosity_cue_started_at = now
            self.queue_draw()
            reaction = "cue"
        else:
            return "drop"

        self._curiosity_last_reaction_at = now
        self._curiosity_streak = streak + 1
        logger = getattr(self, "_logger", None)
        if logger is not None:
            logger.debug(
                "[curiosity] %s -> %s (streak=%d)",
                reason,
                reaction,
                self._curiosity_streak,
            )
        return reaction

    def _clear_curiosity_cue(self) -> None:
        if not self._curiosity_cue_active:
            return
        self._curiosity_cue_active = False
        self.queue_draw()

    # -- Lifecycle hooks ------------------------------------------------------

    def _on_pressed(self, *args) -> None:
        self._cancel_curiosity_source()
        self._clear_curiosity_cue()
        super()._on_pressed(*args)

    def _tick(self) -> bool:
        result = super()._tick()
        if not self._curiosity_cue_active:
            return result
        if not self._curiosity_cue_allowed() or self._curiosity_progress() is None:
            self._clear_curiosity_cue()
            return result
        self.queue_draw()
        return result

    def shutdown_presence(self) -> None:
        self._cancel_curiosity_source()
        self._curiosity_cue_active = False
        super().shutdown_presence()

    # -- Rendering --------------------------------------------------------------

    def _curiosity_progress(self, now: float | None = None) -> float | None:
        if not self._curiosity_cue_active:
            return None
        if now is None:
            now = self._curiosity_now()
        elapsed = max(0.0, now - self._curiosity_cue_started_at)
        duration = self.CURIOSITY_CUE_DURATION_SECONDS
        if elapsed >= duration:
            return None
        return elapsed / duration

    @staticmethod
    def _curiosity_alpha(progress: float) -> float:
        """Ease the cue in quickly, hold it, then let it disappear quietly."""
        if progress < 0.12:
            return max(0.0, progress / 0.12)
        if progress <= 0.68:
            return 1.0
        return max(0.0, 1.0 - ((progress - 0.68) / 0.32))

    @staticmethod
    def _curiosity_lean_factor(progress: float) -> float:
        """Small physical perk that never mutates Mochi's actual position."""
        if progress < 0.18:
            return math.sin((progress / 0.18) * (math.pi / 2))
        if progress <= 0.68:
            return 1.0
        tail = min(1.0, (progress - 0.68) / 0.32)
        return math.cos(tail * (math.pi / 2))

    def _curiosity_lean_offsets(
        self, progress: float, direction: int, scale: float
    ) -> tuple[int, int]:
        """Whole-pixel lean: SpriteAtlas samples nearest-neighbor from rounded
        placement, so a fractional translate would make the pixel art shimmer."""
        factor = self._curiosity_lean_factor(progress)
        return (
            round(direction * self.CURIOSITY_LEAN_PX * scale * factor),
            round(-1.0 * scale * factor),
        )

    def _curiosity_direction(self, width: int) -> int:
        """Lean toward screen center without requesting focused-window geometry.

        The AmbiSense contract exposes only a coarse app category. Using
        Mochi's own monitor-relative placement gives the cue a directional feel
        while preserving that privacy boundary.
        """
        placement = getattr(self, "_placement", None)
        position = getattr(placement, "position", None)
        if placement is None or position is None:
            return 1

        try:
            monitor = placement._monitor_for_position(position.x, position.y)
            if monitor is None:
                return 1
            geometry = monitor.get_geometry()
            if getattr(placement, "layer_shell_enabled", False):
                mochi_center = position.x + width / 2
                monitor_center = geometry.width / 2
            else:
                scale = placement._x11_coordinate_scale()
                mochi_center = position.x / max(scale, 0.001) + width / 2
                monitor_center = geometry.x + geometry.width / 2
            return 1 if mochi_center < monitor_center else -1
        except Exception:
            return 1

    def _draw(self, area, context, width: int, height: int) -> None:
        progress = self._curiosity_progress()
        if progress is None:
            super()._draw(area, context, width, height)
            return

        direction = self._curiosity_direction(width)
        scale = max(0.5, min(width, height) / 112.0)
        lean_x, lean_y = self._curiosity_lean_offsets(progress, direction, scale)

        context.save()
        context.translate(lean_x, lean_y)
        super()._draw(area, context, width, height)
        context.restore()

        # Below this size the glyph is an unreadable blob; the lean alone
        # still reads as a little "huh?".
        if min(width, height) >= self.CURIOSITY_BUBBLE_MIN_SIZE_PX:
            self._draw_curiosity_bubble(
                context,
                width=width,
                direction=direction,
                alpha=self._curiosity_alpha(progress),
                scale=scale,
            )

    def _draw_curiosity_bubble(
        self,
        context,
        *,
        width: int,
        direction: int,
        alpha: float,
        scale: float,
    ) -> None:
        """Thought bubble with a tiny magnifying glass that echoes the beat.

        The bubble carries its own light fill and dark outline, so it stays
        readable on any wallpaper or theme.
        """
        if alpha <= 0.0:
            return

        bubble_w = 26.0 * scale
        bubble_h = 22.0 * scale
        center_x = width * 0.5 + direction * 19.0 * scale
        x = max(3.0 * scale, min(center_x - bubble_w / 2, width - bubble_w - 3.0 * scale))
        y = 7.0 * scale

        context.save()
        self._rounded_rect(context, x, y, bubble_w, bubble_h, 7.0 * scale)
        context.set_source_rgba(0.96, 0.98, 0.94, 0.94 * alpha)
        context.fill_preserve()
        context.set_source_rgba(0.12, 0.24, 0.17, 0.78 * alpha)
        context.set_line_width(max(1.0, 1.25 * scale))
        context.stroke()

        # Two small thought dots point the cue back toward Mochi.
        tail_x = x + bubble_w * (0.35 if direction > 0 else 0.65)
        for dx, dy, radius_scale in (
            (-2.0 * direction, 4.0, 1.8),
            (-5.0 * direction, 9.0, 1.2),
        ):
            context.new_sub_path()
            context.arc(
                tail_x + dx * scale,
                y + bubble_h + dy * scale,
                radius_scale * scale,
                0,
                math.tau,
            )
            context.set_source_rgba(0.96, 0.98, 0.94, 0.90 * alpha)
            context.fill_preserve()
            context.set_source_rgba(0.12, 0.24, 0.17, 0.66 * alpha)
            context.set_line_width(max(0.8, scale))
            context.stroke()

        # Magnifying glass: a lens ring with a short handle to the lower right.
        lens_radius = 5.0 * scale
        lens_x = x + bubble_w / 2 - 1.5 * scale
        lens_y = y + bubble_h / 2 - 1.5 * scale
        context.set_source_rgba(0.09, 0.18, 0.12, 0.92 * alpha)
        context.set_line_width(max(1.0, 1.8 * scale))
        context.new_sub_path()
        context.arc(lens_x, lens_y, lens_radius, 0, math.tau)
        context.stroke()
        handle_x = lens_x + lens_radius * math.cos(math.pi / 4)
        handle_y = lens_y + lens_radius * math.sin(math.pi / 4)
        context.set_line_width(max(1.0, 2.2 * scale))
        context.set_line_cap(cairo.LINE_CAP_ROUND)
        context.move_to(handle_x, handle_y)
        context.line_to(handle_x + 4.0 * scale, handle_y + 4.0 * scale)
        context.stroke()
        context.restore()

    @staticmethod
    def _rounded_rect(
        context,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float,
    ) -> None:
        radius = min(radius, width / 2, height / 2)
        context.new_sub_path()
        context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
        context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        context.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
        context.close_path()
```

- [ ] **Step 4: Run the curiosity tests to see them pass**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_active_window_curiosity.py
```

Expected: all passed. `test_curiosity_wraps_the_idle_beat_owner` confirms the order from Task 1. If it fails, edit `src/mochi/presence/click_dialogue.py` so that `ActiveWindowCuriosityMixin,` sits on the line directly above `IdleLookMixin,` in both class definitions.

- [ ] **Step 5: Run the full suite**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: 0 failed.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/presence/curiosity.py tests/test_active_window_curiosity.py src/mochi/presence/click_dialogue.py
git commit -F - <<'EOF'
feat: calm, habituating curiosity with an idle investigate beat

Curiosity now debounces window pulses, settles tab pulses, and picks the
first allowed reaction: an investigate beat when Mochi stands idle, a
small magnifier cue when he is busy, or nothing. Cooldowns grow during
busy sessions and reset after five quiet minutes, on a suspend-aware
clock. The lean is pixel-snapped and the bubble is skipped below 80 px.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
EOF
```

---

### Task 5: Emit `BrowserTabChanged` from the GNOME extension

**Files:**
- Modify: `gnome-extension/mochi-typing@miflow13/extension.js` (as merged in Task 1)
- Modify: `tests/test_gnome_shortcuts.py`

**Interfaces:**
- Consumes:
  - Task 1's extension state: `_lastFocusedWindow`, `_updateAppCategory()` returning the category, the focus handler with `const focusedWindow` and `const category`, and `_emitAppFocus`;
  - the existing `_emitSignal(signalName)`, `this._idleMonitor` (Mutter core idle monitor) and `disable()`.
- Produces:
  - the D-Bus signal `BrowserTabChanged` with no arguments (consumed by Task 3);
  - top-level `normalizeTabTitle(title)` and `shouldEmitTabPulse(idleMs)`;
  - the methods `_trackBrowserTabTitle(window, category)`, `_untrackBrowserTabTitle()`, `_tabTitleDigestFor(window)` and `_onBrowserTabTitleChanged()`.

**Acceptance Criteria:**
- Only windows classified as `browser` get a `notify::title` handler, and switching focus to another window moves or removes it.
- The existing 1 s category heartbeat re-syncs tracking, so a browser window whose identity is classified late still gets tracked.
- On a title change, the digest is compared and stored **before** the input gate, and the emit happens only when `get_idletime() < TAB_INPUT_WINDOW_MS`.
- `BrowserTabChanged` goes through `_emitSignal` with no payload. No title value reaches `console.*`, a `GLib.Variant` or a stored field.
- `disable()` untracks the window and clears the digest.
- An installer guard test fails if any `*.js` in the extension folder is missing from the install script's copy line.

- [ ] **Step 1: Write the failing source-contract tests**

Append to `tests/test_gnome_shortcuts.py`:

```python
def _extension_source() -> str:
    return (EXTENSION / "extension.js").read_text(encoding="utf-8")


def _method_body(source: str, signature: str) -> str:
    """Text from a method signature up to the next four-space-indented method."""
    start = source.index(signature)
    following = source.find("\n    _", start + len(signature))
    return source[start:] if following == -1 else source[start:following]


def test_browser_tab_pulse_constants_are_declared() -> None:
    source = _extension_source()

    assert "const BROWSER_TAB_SIGNAL_NAME = 'BrowserTabChanged';" in source
    assert "const TAB_INPUT_WINDOW_MS = 2000;" in source
    assert "const TAB_TITLE_BADGE_PATTERN = /^\\(\\d+\\+?\\)\\s*/;" in source


def test_tab_title_change_stores_digest_before_input_gate_and_emits_no_payload() -> None:
    handler = _method_body(_extension_source(), "_onBrowserTabTitleChanged() {")

    stored = handler.index("this._tabTitleDigest = digest;")
    gated = handler.index("shouldEmitTabPulse(")
    emitted = handler.index("this._emitSignal(BROWSER_TAB_SIGNAL_NAME);")
    assert stored < gated < emitted
    assert "get_idletime()" in handler


def test_tab_titles_are_reduced_to_a_digest_and_never_leave_the_shell() -> None:
    source = _extension_source()
    digest = _method_body(source, "_tabTitleDigestFor(window) {")
    tracking = (
        digest
        + _method_body(source, "_trackBrowserTabTitle(window, category) {")
        + _method_body(source, "_onBrowserTabTitleChanged() {")
    )

    assert "GLib.ChecksumType.SHA256" in digest
    assert "normalizeTabTitle(" in digest
    assert "console." not in tracking
    assert "GLib.Variant" not in tracking
    assert "this._tabTitle =" not in source


def test_tab_title_tracking_is_browser_only_and_cleaned_up() -> None:
    source = _extension_source()
    track = _method_body(source, "_trackBrowserTabTitle(window, category) {")
    disable = source[source.index("    disable() {"):]

    assert "category === 'browser' ? window : null" in track
    assert "'notify::title'" in track
    assert "this._trackBrowserTabTitle(focusedWindow, category);" in source
    assert "this._untrackBrowserTabTitle();" in disable


def test_category_heartbeat_resyncs_tab_tracking() -> None:
    source = _extension_source()
    start = source.index("VIDEO_FOCUS_HEARTBEAT_MS,")
    heartbeat = source[start:source.index("GLib.SOURCE_CONTINUE", start)]

    # A window can be focused before its identity classifies as a browser.
    assert "this._updateAppCategory();" in heartbeat
    assert (
        "this._trackBrowserTabTitle(global.display.get_focus_window(), this._appCategory);"
        in heartbeat
    )


def test_install_script_copies_every_extension_module() -> None:
    script = (ROOT / "scripts" / "install-typing-extension.sh").read_text(encoding="utf-8")
    copy_line = next(
        line
        for line in script.splitlines()
        if line.lstrip().startswith("cp ") and "extension.js" in line
    )

    modules = sorted(path.name for path in EXTENSION.glob("*.js"))
    assert modules, "expected at least extension.js"
    for module in modules:
        assert f'"$SOURCE_DIR/{module}"' in copy_line, (
            f"{module} would be left out of the installed extension"
        )
```

- [ ] **Step 2: Run them to see them fail**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_gnome_shortcuts.py
```

Expected: the five tab tests FAIL with `ValueError: substring not found` or `AssertionError`. The installer guard PASSES already: it protects the future, and `extension.js` is copied today.

- [ ] **Step 3: Add the constants and pure helpers**

In `extension.js`, directly below `const APP_FOCUS_SIGNAL_NAME = 'AppFocusChanged';`:

```js
const BROWSER_TAB_SIGNAL_NAME = 'BrowserTabChanged';
// Tab switches and link clicks follow real input within this window. Unread
// counters, title blinkers, and autoplay retitles happen hands-off.
const TAB_INPUT_WINDOW_MS = 2000;
// "(3) Inbox" and "(99+) Chat": an unread badge is not a new tab or page.
const TAB_TITLE_BADGE_PATTERN = /^\(\d+\+?\)\s*/;
```

Directly above `export default class MochiTypingActivityExtension extends Extension {`:

```js
function normalizeTabTitle(title) {
    return String(title ?? '').trim().replace(TAB_TITLE_BADGE_PATTERN, '');
}

function shouldEmitTabPulse(idleMs) {
    return Number.isFinite(idleMs) && idleMs >= 0 && idleMs < TAB_INPUT_WINDOW_MS;
}

```

- [ ] **Step 4: Initialize tracking state in `enable()`**

Directly below the PR #133 line `this._lastFocusedWindow = global.display.get_focus_window();`:

```js
        this._tabWindow = null;
        this._tabTitleChangedId = 0;
        this._tabTitleDigest = null;
```

- [ ] **Step 5: Track the focused browser window**

5a. In the `notify::focus-window` handler, directly below `const category = this._updateAppCategory();` (and **above** the PR #133 comment `// Mutter can notify focus-window more than once...`):

```js
                this._trackBrowserTabTitle(focusedWindow, category);
```

5b. After the focus handler is connected there is an initial-sync sequence: `this._updateFileBrowsingState();`, `this._updateYouTubeFocusedState(false);`, `this._updateAppCategory();`, immediately followed by `this._videoFocusHeartbeatId = GLib.timeout_add(`. Directly below **that** `this._updateAppCategory();` line, insert:

```js
        this._trackBrowserTabTitle(global.display.get_focus_window(), this._appCategory);
```

5c. In the heartbeat callback passed to `GLib.timeout_add(GLib.PRIORITY_DEFAULT, VIDEO_FOCUS_HEARTBEAT_MS, () => { ... })`, directly below its `this._updateAppCategory();` line (16-space indent), insert the line below. Identity can arrive after a window is focused, so this picks up a browser that classified late. The call is idempotent: an unchanged target returns immediately.

```js
                this._trackBrowserTabTitle(global.display.get_focus_window(), this._appCategory);
```

5d. Add these methods directly after the PR #133 `_emitAppFocus(category) { ... }` method:

```js
    _trackBrowserTabTitle(window, category) {
        // Only browser titles are observed; every other app stays unwatched.
        const target = category === 'browser' ? window : null;
        if (target === this._tabWindow)
            return;

        this._untrackBrowserTabTitle();
        if (target === null)
            return;

        this._tabWindow = target;
        // A newly focused window is a baseline, not a tab change.
        this._tabTitleDigest = this._tabTitleDigestFor(target);
        this._tabTitleChangedId = target.connect(
            'notify::title',
            () => this._onBrowserTabTitleChanged(),
        );
    }

    _untrackBrowserTabTitle() {
        if (this._tabWindow !== null && this._tabTitleChangedId) {
            try {
                this._tabWindow.disconnect(this._tabTitleChangedId);
            } catch (_error) {
                // The window may already be unmanaged; nothing left to release.
            }
        }
        this._tabWindow = null;
        this._tabTitleChangedId = 0;
        this._tabTitleDigest = null;
    }

    _tabTitleDigestFor(window) {
        let title = '';
        try {
            title = window.get_title();
        } catch (_error) {
            return null;
        }
        // Privacy boundary: keep only a one-way digest for change detection.
        // The title itself is never stored, logged, or sent over D-Bus.
        return GLib.compute_checksum_for_string(
            GLib.ChecksumType.SHA256,
            normalizeTabTitle(title),
            -1,
        );
    }

    _onBrowserTabTitleChanged() {
        if (this._tabWindow === null)
            return;

        const digest = this._tabTitleDigestFor(this._tabWindow);
        if (digest === null || digest === this._tabTitleDigest)
            return;
        // Store first so hands-off churn still becomes the new baseline.
        this._tabTitleDigest = digest;

        if (this._idleMonitor === null)
            return;
        if (!shouldEmitTabPulse(Number(this._idleMonitor.get_idletime())))
            return;

        this._emitSignal(BROWSER_TAB_SIGNAL_NAME);
    }
```

- [ ] **Step 6: Clean up in `disable()`**

In `disable()`, directly after the block that disconnects `this._focusChangedId`, add:

```js
        this._untrackBrowserTabTitle();
```

- [ ] **Step 7: Run the tests to see them pass**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_gnome_shortcuts.py tests/test_presence_watches.py
```

Expected: all passed.

- [ ] **Step 8: Syntax-check the extension**

GJS isn't installed here, so check the syntax with Node, which parses ESM. The `gi://` and `resource://` imports are not resolved during `--check`:

```bash
node --check --input-type=module < gnome-extension/mochi-typing@miflow13/extension.js && echo "syntax ok"
```

Expected: `syntax ok`.

- [ ] **Step 9: Run the full suite**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: 0 failed.

- [ ] **Step 10: Commit**

```bash
git add gnome-extension/mochi-typing@miflow13/extension.js tests/test_gnome_shortcuts.py
git commit -F - <<'EOF'
feat: emit payload-free BrowserTabChanged from the GNOME helper

The extension watches title changes on the focused browser window only,
keeps a SHA-256 digest (never the title) for change detection, strips
unread badges, and emits only when user input happened in the last 2 s.
A guard test keeps every extension module in the installer's copy list.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
EOF
```

---

### Task 6: Documentation and QA watchlist

**Files:**
- Modify: `CHANGELOG.md` (the Unreleased → Added line from Task 1)
- Modify: `gnome-extension/mochi-typing@miflow13/README.md`
- Modify: `docs/ambisense.md`
- Modify: `REGRESSION_WATCHLIST.md`
- Modify: `docs/CODEBASE_MANUAL.md` (§6 "The actual runtime object")

**Interfaces:**
- Consumes: shipped behavior from Tasks 2–5.
- Produces: user-facing and contributor docs.

**Acceptance Criteria:**
- CHANGELOG describes the feature, the GNOME re-login requirement and the privacy guarantee in plain language.
- The extension README lists `BrowserTabChanged`, and states the digest, the timing-only exposure and the input gate.
- `docs/ambisense.md` lists tab/page changes under Signals and explains the digest and session-bus timing under Privacy.
- `REGRESSION_WATCHLIST.md` → Contextual Presence has the six spec QA items.
- `CODEBASE_MANUAL.md` §6 lists the real layer order. Two short notes explain why curiosity is a mixin (every entry point is a cooperative-chain hook), and that `IdleLookMixin` owns all standing-idle beats.
- `git diff --check` is clean.

- [ ] **Step 1: Rewrite the CHANGELOG line**

In `CHANGELOG.md` under `## Unreleased` → `### Added`, replace:

```markdown
- Added a subtle Active Window Curiosity cue that notices privacy-reduced app-focus changes without interrupting Mochi's current behavior.
```

with:

```markdown
- Mochi now notices when you switch windows or settle on a new browser tab.
  If he's standing around he takes a quick look through his magnifying glass;
  if he's busy he shows a tiny thought bubble instead, and he settles down
  during long browsing sessions. Tab awareness comes from the GNOME helper,
  which never reads page titles out to Mochi, and arrives after you log out
  and back in once the update installs.
```

- [ ] **Step 2: Update the extension README**

In `gnome-extension/mochi-typing@miflow13/README.md`, directly below the `- \`AppFocusChanged\` — ...` bullet added by PR #133:

```markdown
- `BrowserTabChanged` — zero-payload pulse when the focused browser window's title changes right after real keyboard or pointer input (a tab switch or a followed link). Unread-badge, title-blinker, and autoplay retitles are ignored.
```

Then, directly below the paragraph that begins `The existing YouTube-focus helper may transiently inspect the focused browser title`, add:

```markdown
Tab awareness observes title changes on the focused browser window only. To detect a change it keeps a one-way SHA-256 digest of the current title (with any leading unread badge removed) in memory; the title itself is never stored, logged, or sent. The digest is defense in depth rather than a hard boundary — GNOME Shell already holds window titles — but it means no extension log or state dump can leak one. `BrowserTabChanged` reveals only *when* you changed tab or page; like every signal here, its timing is visible to other processes on your session bus.
```

- [ ] **Step 3: Update `docs/ambisense.md`**

Under `## Signals`, replace the bullet:

```markdown
- coarse app categories such as editor, terminal, browser, media, or pixel-art
  software;
```

with:

```markdown
- coarse app categories such as editor, terminal, browser, media, or pixel-art
  software, plus a content-free pulse when you switch windows or settle on a
  new browser tab;
```

Under `## Privacy model`, directly after the paragraph that ends `...without reading the user's work.`, add:

```markdown
Browser tab awareness is timing-only. The GNOME helper watches the focused
browser's title change inside GNOME Shell, keeps a one-way digest to tell
whether it changed, and sends Mochi a pulse with no data — only after real
keyboard or pointer input, so unread counters and autoplay do not count. Like
other AmbiSense signals, that pulse's timing is visible on the session bus.
```

- [ ] **Step 4: Add the QA items to `REGRESSION_WATCHLIST.md`**

At the end of the `## Contextual Presence / Media` checklist, directly after `- [ ] Direct interaction can interrupt contextual presentation and ambient recovery is deterministic`, add:

```markdown
- [ ] Flicking through browser tabs produces one curiosity reaction after settling, not one per tab
- [ ] Title changes with hands off the keyboard and mouse (unread badges, chat title blinkers, YouTube autoplay) do not trigger curiosity
- [ ] Investigate beat returns to idle without a visible frame jump
- [ ] Dragging Mochi mid-investigate recovers cleanly
- [ ] Quiet mode / ambient reactions off suppress all curiosity
- [ ] Curiosity lean stays crisp (no pixel shimmer) and the bubble is legible at 112 px and 256 px; 64 px shows lean only
```

- [ ] **Step 5: Correct the codebase manual's layer order**

In `docs/CODEBASE_MANUAL.md` §6, replace the stale "Current layer order" block. It is missing `UpdateControlsMixin` and `PocketBuddyMixin` even before this work:

```
    ClickDialogueMixin
    IdleLookMixin
    QuickStartMixin
    FocusSessionMixin
    FedoraModeMixin
    TerminalCoworkMixin
    MusicDanceMixin
    EdgeRoamMixin
    EmoteCatalogueMixin
    BondMeterMixin
    FeedMochiMixin
    NameplateMixin
    PresenceBuddyMixin
    Buddy
```

with the order now in `src/mochi/presence/click_dialogue.py`:

```
    ClickDialogueMixin
    ActiveWindowCuriosityMixin
    IdleLookMixin
    UpdateControlsMixin
    QuickStartMixin
    FocusSessionMixin
    FedoraModeMixin
    TerminalCoworkMixin
    EdgeRoamMixin
    MusicDanceMixin
    EmoteCatalogueMixin
    BondMeterMixin
    FeedMochiMixin
    PocketBuddyMixin
    NameplateMixin
    PresenceBuddyMixin
    Buddy
```

Before editing, confirm the list against the source:

```bash
sed -n '/^class PresenceBuddy(/,/^):/p' src/mochi/presence/click_dialogue.py
```

Then, directly after the paragraph that ends `Do not use its size as a template for future mixins.`, add:

```markdown
ActiveWindowCuriosityMixin is a deliberate mixin rather than a composed
controller: every entry point it has (`_draw`, `_tick`, `_on_pressed`,
`shutdown_presence`, and the app-focus and browser-tab presence hooks) is a
cooperative-chain hook, and it never claims behavior state. It sits directly
above IdleLookMixin, which owns every standing-idle beat — the timed `look`
and curiosity's `investigate` — through `_play_idle_beat()`, with
`_idle_look_active` as the single ownership flag.
```

- [ ] **Step 6: Check and commit**

```bash
git diff --check && echo clean
git add CHANGELOG.md gnome-extension/mochi-typing@miflow13/README.md docs/ambisense.md REGRESSION_WATCHLIST.md docs/CODEBASE_MANUAL.md
git commit -F - <<'EOF'
docs: document tab-aware curiosity, its privacy model, and QA checks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
EOF
```

---

### Task 7: Final verification, push, and draft PR

**Files:** none. This task covers verification and delivery.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: the pushed branch `claude/optimistic-volta-9jc07e` and a draft PR against `main` that supersedes #133.

**Acceptance Criteria:**
- The same checks CI runs pass locally: the full suite under xvfb, `compileall`, `bash -n install.sh` and `git diff --check`.
- A runtime smoke of the **real app** under Xvfb passes at sizes 64, 112 and 256: tab pulse → settle → `investigate` beat → idle with state `IDLE` throughout; busy tab pulse → cue with state `TYPING`; press clears the cue; clean shutdown with no traceback. A screenshot contact sheet is sent to the owner before the push.
- The branch is pushed and a draft PR is open, its body following `.github/pull_request_template.md`, with "Fedora/GNOME/Wayland visual QA required" called out.
- The PR body states that it supersedes #133 and that the owner should close #133.

- [ ] **Step 1: Run CI's checks locally**

```bash
PYTHONPATH=src xvfb-run -a /usr/bin/python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
/usr/bin/python3.12 -m compileall -q src && echo "compileall ok"
bash -n install.sh && echo "install.sh ok"
node --check --input-type=module < gnome-extension/mochi-typing@miflow13/extension.js && echo "extension syntax ok"
git diff --check origin/main...HEAD && echo "whitespace ok"
```

Expected: 0 failed, then the four `ok` lines.

- [ ] **Step 2: Review the whole diff adversarially before pushing**

```bash
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- src gnome-extension
```

Check specifically:
- no title value is ever passed to `console.*`, a `GLib.Variant` or a field other than `_tabTitleDigest`;
- no code path sets `MochiState` from curiosity;
- every `GLib.timeout_add` in `curiosity.py` has a matching cancel in `_cancel_curiosity_source`.

- [ ] **Step 3: Runtime smoke of the real app under Xvfb (not committed)**

The unit harnesses use fake bases. This step drives the production `PresenceX11Buddy` chain with real GLib timers and a real `AnimationPlayer`. It was verified feasible on 2026-10-05: the app starts headless with `xvfb-run` plus `dbus-run-session`, and missing system services degrade gracefully. Without a compositor, transparent areas render black; that's expected.

Create `$SP/smoke_curiosity.py`, where `SP=/tmp/claude-0/-home-user-mochi-desktop/f682b1cd-28f8-5b93-8cec-02e00dd6f013/scratchpad`:

```python
"""Throwaway runtime smoke for active window curiosity. Not committed."""

import os
import subprocess
import sys

from gi.repository import Gio, GLib

sys.argv = ["mochi", "--debug"]
from mochi import main as mochi_main  # noqa: E402

OUT = os.environ["SMOKE_OUT"]
SIZE = int(os.environ["SMOKE_SIZE"])
results: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    results.append((name, bool(ok)))
    print(f"SMOKE {'PASS' if ok else 'FAIL'} {name}", flush=True)


def buddy():
    return Gio.Application.get_default()._buddy


def shot(name: str) -> None:
    pos = buddy()._placement.position
    root = f"{OUT}/{name}-root.png"
    subprocess.run(["import", "-window", "root", root], check=True)
    subprocess.run(
        ["convert", root, "-crop", f"{SIZE}x{SIZE}+{pos.x}+{pos.y}", "+repage",
         f"{OUT}/{name}-{SIZE}.png"],
        check=True,
    )


def at(ms: int, step) -> None:
    GLib.timeout_add(ms, lambda: (step(), False)[1])


def tab_pulse_while_idle() -> None:
    b = buddy()
    check("starts standing idle", b._is_idle_visual_active())
    b._on_presence_browser_tab_changed()


def mid_beat() -> None:
    b = buddy()
    check("settled pulse plays investigate", b._current_animation == "investigate")
    check("beat keeps state IDLE", b.state.current.name == "IDLE")
    shot("beat")


def after_beat() -> None:
    b = buddy()
    check("beat resumes idle", b._current_animation == "idle" and not b._idle_look_active)
    b._start_typing_emote()


def tab_pulse_while_typing() -> None:
    b = buddy()
    check("typing started", b.state.current.name == "TYPING")
    # Skip the habituated 30 s reaction gap; pacing itself is unit-tested.
    b._curiosity_last_reaction_at = float("-inf")
    b._on_presence_browser_tab_changed()


def mid_cue() -> None:
    b = buddy()
    check("busy pulse shows cue", b._curiosity_cue_active)
    check("cue keeps state TYPING", b.state.current.name == "TYPING")
    shot("cue")


def press() -> None:
    b = buddy()
    b._on_pressed(None, 1, SIZE / 2, SIZE / 2)
    check("press clears cue", not b._curiosity_cue_active)


def quit_app() -> None:
    Gio.Application.get_default().quit()


at(3000, tab_pulse_while_idle)
at(4900, mid_beat)       # 1.5 s settle + ~0.4 s into the 2.4 s beat
at(7600, after_beat)
at(9200, tab_pulse_while_typing)
at(11000, mid_cue)       # 1.5 s settle + ~0.3 s into the 1.8 s cue
at(11300, press)
at(12000, quit_app)

status = mochi_main.main()
check("clean exit", status in (0, None))
sys.exit(0 if all(ok for _, ok in results) else 1)
```

Run it at three sizes. Each run gets a fresh config, so nothing touches the real user config:

```bash
SP=/tmp/claude-0/-home-user-mochi-desktop/f682b1cd-28f8-5b93-8cec-02e00dd6f013/scratchpad
for size in 64 112 256; do
  run="$SP/smoke-$size"; rm -rf "$run"; mkdir -p "$run/config/mochi" "$run/data"
  printf '{"size": %d, "x": 200, "y": 200}\n' "$size" > "$run/config/mochi/config.json"
  XDG_CONFIG_HOME="$run/config" XDG_DATA_HOME="$run/data" SMOKE_OUT="$run" SMOKE_SIZE="$size" \
    PYTHONPATH=src timeout 60 xvfb-run -a -s "-screen 0 1280x800x24" \
    dbus-run-session -- /usr/bin/python3.12 "$SP/smoke_curiosity.py" > "$run/log.txt" 2>&1
  echo "size $size exit=$?"; grep -E "SMOKE|Traceback" "$run/log.txt"
done
montage "$SP"/smoke-*/beat-*.png "$SP"/smoke-*/cue-*.png -tile 3x2 -geometry +12+12 -background '#333' "$SP/curiosity-smoke.png"
```

Expected: `exit=0` for every size, only `SMOKE PASS` lines, and no `Traceback`. On any failure, debug it with `beads-superpowers:systematic-debugging` and fix it in a normal TDD commit before continuing. Send `$SP/curiosity-smoke.png` to the owner with `SendUserFile`; the top row is the beat at 64/112/256 and the bottom row the cue. Expect no bubble at 64 px.

- [ ] **Step 4: Push**

```bash
git push -u origin claude/optimistic-volta-9jc07e
```

On a network failure, retry up to 4 times with backoff of 2 s, 4 s, 8 s and 16 s.

- [ ] **Step 5: Open the draft PR**

Use the GitHub MCP `create_pull_request` tool with `draft: true`, `base: main` and `head: claude/optimistic-volta-9jc07e`. Title it: `feat: tab-aware active window curiosity (supersedes #133)`. The body mirrors `.github/pull_request_template.md`'s headings (Summary, Scope, Verification checklist, Runtime / lifecycle notes, Environment tested) and must state:
- that it supersedes #133;
- the privacy model;
- that Fedora/GNOME/Wayland visual QA is pending, with the six new watchlist items;
- the local result (`N passed, 3 skipped`, taken from Step 1's output) and the Xvfb runtime smoke result.

End the body with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01FM6gLS7KvN4CDGVtmQ9ftG
```

---

## Stress Test Results: Implementation Plan

### Resolved Decisions

- **Merge drift (from evidence):** a trial merge of PR #133 into `main` passes (1059 passed, 3 skipped). The `_tick(self) -> bool`, `_draw` and `_on_pressed(*args)` hook signatures are unchanged. Task 1 needs no drift fixes.
- **Mixin vs. composed controller:** curiosity stays a mixin, because every entry point is a cooperative-chain hook and it never claims behavior state. The stale manual is corrected and the choice explained (Task 6 Step 5).
- **Late-classified browser windows:** the existing 1 s category heartbeat re-syncs tab tracking, idempotently (Task 5 step 5c plus a test).
- **Runtime evidence:** an Xvfb smoke drives the real `PresenceX11Buddy` at 64/112/256 px, and a screenshot contact sheet goes to the owner before the push (Task 7 Step 3). Feasibility was verified.
- **Security:** no new surface beyond the spec. Title handling fails closed and is test-enforced; the smoke uses isolated XDG directories; there are no new dependencies, CI changes or permissions.
- **Reflexion:** PR #133's "category reclassification never triggers curiosity" test is ported into the Task 4 rewrite so that guarantee keeps a test.

### Changes Made

- Task 1: expected count is now the verified `1059 passed, 3 skipped`.
- Task 4: harness tracks `_presence_app_category`; the ported reclassification test and its acceptance criterion are added.
- Task 5: heartbeat re-sync step (5c, with the methods step renumbered to 5d), `test_category_heartbeat_resyncs_tab_tracking`, and an acceptance criterion.
- Task 6: `docs/CODEBASE_MANUAL.md` §6 layer-order correction plus the mixin and idle-beat ownership note.
- Task 7: Xvfb runtime smoke step with a contact sheet; push and PR renumbered to Steps 4 and 5; the PR body reports the smoke result.

### Deferred / Parking Lot

- An Xvfb smoke is X11-only. GNOME Wayland/XWayland behavior and the extension's real `notify::title` timing still need the owner's Fedora QA.
- Releasing `MetaWindow` references on `unmanaged` (instead of on the next focus change) is not done; PR #133's `_lastFocusedWindow` already holds the same kind of reference, and nothing has shown it to matter.

### Confidence Assessment

- Overall: **High** for Tasks 1–4 and 6. The merge is verified, the code is fully specified, and the suite runs locally in 17 s.
- **Medium** for Task 5's live behavior: the source tests pin down structure, not Mutter timing.
- Areas of concern: the feel of the cue and beat, which the Task 7 contact sheet surfaces early.
