# Resource Sense Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use beads-superpowers:subagent-driven-development (recommended) or beads-superpowers:executing-plans to implement this plan task-by-task. Each Task becomes a bead (`bd create -t task --parent <epic-id>`). Steps within tasks use checkbox (`- [ ]`) syntax for human readability.
>
> **Do not start until the spec and this plan are approved by the owner.**

**Goal:** Mochi notices sustained high CPU and high or critical RAM. Once per episode it says an in-character line with the measured number, plays an existing beat (`this_is_fine` or `squish`), and briefly shows a two-meter card in the shared anchor slot. Hovering under load or a session-only *Computer stats* switch shows the card on demand. Only aggregate numbers are read, from two procfs files.

**Architecture:**
- A GTK-free core in `src/mochi/resource_sense.py`: sampler → pressure tracker (edges with dwell and hysteresis) → reaction gate (habituation, escalation) → card wording.
- A small `PresenceEngine` extension so queued events can carry integer values that fill `{cpu}` / `{ram}` placeholders, with anti-repeat keyed on the template.
- `ResourceSenseMixin` owns one GLib poll source (5 s, 1 s while the card is wanted, none while away), announcements, hover, the menu row and a Mochi Lab preview.
- `ResourceCard`, a non-interactive surface built like `BondProgressOverlay`, takes a new tier in the nameplate's shared-anchor resolver.

Not touched: `MochiState`, the behavior controller, `config.py`, `buddy.py`, the updater, `main.py`, GDK backend selection.

**Tech Stack:** Python 3.11+, GTK4/PyGObject, GLib timers, procfs, pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-resource-sense-design.md`

**Mockup:** `docs/design/resource-sense/mockup-light.png`, `mockup-dark.png` (source: `mockup.html`)

## Global Constraints

- Reads exactly `/proc/stat` (first line) and `/proc/meminfo` (`MemTotal`, `MemAvailable`). Never `/proc/<pid>`, process names, command lines, titles or file names. A test pins the set of files read.
- No new runtime dependency. No persisted setting. *Computer stats* is session-only and must never call `ConfigStore`.
- Resource Sense never changes `MochiState` or `PresentationState`. Beats run only through `IdleLookMixin._play_idle_beat`; speech only through `PresenceEngine`; no text reaches any `markup=` parameter.
- One poll source, owned by `ResourceSenseMixin`, stored and cancelled per Manual Rule 4. Start → stop → start leaves exactly one source.
- All Resource Sense timing uses `_resource_now()` (`CLOCK_BOOTTIME`, falling back to `time.monotonic()`).
- Constants (exact values):
  - `CPU_SMOOTHING_ALPHA = 0.3`
  - `cpu_busy`: enter ≥ 85 for 45 s, exit < 60 for 30 s
  - `memory_tight`: enter ≥ 90 for 20 s, exit < 80 for 30 s
  - `memory_critical`: enter ≥ 95 for 10 s, exit < 90 immediately
  - `ResourceReactionGate.BASE_SECONDS = 1200.0`, `CAP_SECONDS = 7200.0`, `STREAK_RESET_SECONDS = 3600.0`
  - `RESOURCE_SAMPLE_SECONDS = 5`, `RESOURCE_CARD_SAMPLE_SECONDS = 1`, `RESOURCE_CARD_SECONDS = 8.0`, `RESOURCE_BEAT_TTL_SECONDS = 30.0`
  - Engine priorities 30 / 30 / 40, category `resources`, TTL 30 s
  - Card colours: calm `#79c98b`, busy `#e5a50a`, critical `#e66a5c`
- **Test command.** Use an interpreter that has `gi` and the GTK 4 typelib. In the planning container that was:
  - `PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider <paths>`
  - CI runs `xvfb-run -a python3 -m pytest -q`.
- **Baseline** on `main` @ `4713426`: **1354 passed, 6 skipped** with `-k "not TypingActivityMonitorTests"`. Those 9 tests abort with SIGTRAP in a container without an accessibility bus, even when run alone; that is an environment limit, and CI is expected to run them. Re-measure at Task 1 and use the new number.
- Commits end with the implementing session's attribution trailer.
- Work on a new branch from `main` (for example `claude/resource-sense`), never on `main`.

## Verified facts

Gathered while writing this plan (2026-10-06), against a scratch copy of `main` @ `4713426`:

| Fact | Evidence |
|---|---|
| Task 2's module and tests are correct as written below | 27 passed; two deliberate mutations (CPU exit threshold, iowait handling) each failed one test |
| The sampler works on a real kernel | `ResourceSampler()` on live procfs returned `cpu_percent=0, ram_percent=4` after one second |
| Task 3's engine and phrase diffs keep every existing test green | Full suite 1354 → 1394 passed (27 + 13 new), 0 failed |
| Task 5's mixin code and tests are correct | 22 passed (fake card, fake GLib), including MRO placement, half-built objects and a pinned card during a lock |
| The plan text itself is executable | Every code block was extracted from this document and applied to a pristine `main` checkout; the full suite passed (see totals) |
| Task 5's anchor-tier diff keeps the nameplate suite green | 6 new + 39 existing nameplate tests passed |
| Task 4's card and tests are correct | 11 passed; a real card built under Xvfb shows in X11 mode at 210×84, suspends, resumes and destroys cleanly |
| All of the above together | 1433 passed, 6 skipped, 0 failed (1354 + 79 new) |
| Tests can import helpers from sibling test modules | `tests/` has no `__init__.py`, so pytest's default import mode puts it on `sys.path`; verified with `PYTHONPATH=src` only |
| `update/worker.py` and `main.py` import without GTK | `'gi' in sys.modules` is `False` after importing both |
| Unknown context-menu rows get a central height increment | `buddy_menu.py:110-116`; no `buddy.py` change needed |
| Mochi Lab's AmbiSense switches are session-only | `presence/integration.py:197-219`; nothing in `config.py` |
| Card colours meet contrast where text is involved | The "!" badge text and all labels are at least 4.5:1 in both themes (mockup contrast check); bars are supplementary |

**Not verified:** anything that needs a real GNOME session: XWayland stacking and positioning, the popover path on pure Wayland, and how "line, then meters" feels. Those are the owner's QA.

## File Map

| File | Responsibility | Task |
|---|---|---|
| `src/mochi/resource_sense.py` (new) | Sampler, tracker, gate, card wording | 2 |
| `tests/test_resource_sense.py` (new) | Core tests | 2 |
| `src/mochi/presence/engine.py` | `emit(values=…)`, template anti-repeat, three resource events | 3 |
| `src/mochi/presence/phrases.py` | Resource lines in `EVENT_PHRASES` | 3 |
| `tests/test_resource_engine_events.py` (new) | Engine tests | 3 |
| `src/mochi/presence/resource_card.py` (new) | Card surface | 4 |
| `tests/test_resource_card.py` (new) | Card tests | 4 |
| `src/mochi/presence/resource_sense.py` (new) | `ResourceSenseMixin` | 5 |
| `tests/test_resource_sense_mixin.py` (new) | Mixin lifecycle tests | 5 |
| `src/mochi/presence/nameplate_controls.py` | Resource-card tier in the shared anchor | 5 |
| `tests/test_resource_card_anchor.py` (new) | Anchor tests | 5 |
| `src/mochi/presence/click_dialogue.py` | Mixin order | 5 |
| `CHANGELOG.md`, `README.md`, `docs/ambisense.md`, `docs/CODEBASE_MANUAL.md`, `REGRESSION_WATCHLIST.md` | Docs and QA | 6 |

---

### Task 1: Branch and baseline

**Files:** none.

**Interfaces:**
- Consumes: `main`.
- Produces: a feature branch and a recorded baseline count.

**Acceptance Criteria:**
- The branch is created from the latest `main`.
- The full suite result is recorded in the PR body later.

- [ ] **Step 1: Branch from main**

```bash
cd /home/user/mochi-desktop
git fetch origin main
git checkout -b claude/resource-sense origin/main
```

- [ ] **Step 2: Record the baseline**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected on `4713426`: `1354 passed, 6 skipped` if the accessibility-bus tests are deselected; otherwise all pass in CI. Write the number down.

---

### Task 2: Pure core — sampler, tracker, gate, card wording

**Files:**
- Create: `src/mochi/resource_sense.py`
- Create: `tests/test_resource_sense.py`

**Interfaces:**
- Consumes: nothing from Mochi.
- Produces:
  - `ResourceSample(cpu_percent: int | None, ram_percent: int | None)`
  - `ResourceSampler(*, read_text=...)` with `sample()` and `reset()`
  - `ResourceLevel` (`CPU_BUSY`, `MEMORY_TIGHT`, `MEMORY_CRITICAL`; values are the engine event names)
  - `ResourceEdge(level, entered, cpu_percent, ram_percent)`
  - `ResourcePressureTracker` with `observe(sample, now) -> list[ResourceEdge]`, `clear() -> list[ResourceEdge]`, `active_levels`, `last_sample`
  - `ResourceReactionGate.should_announce(level, now) -> bool`
  - `habituated_cooldown(base, cap, streak, factor=1.5)`
  - `CardRow`, `CardModel`, `resource_card_model(sample, active) -> CardModel`

**Acceptance Criteria:**
- The module imports without `gi`.
- All 27 tests below pass.
- `git diff --check` is clean.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resource_sense.py`:

```python
"""Resource Sense pure core: sampler, pressure tracker, and reaction gate."""

from __future__ import annotations

from pathlib import Path
import unittest

from mochi.resource_sense import (
    PROC_MEMINFO,
    PROC_STAT,
    ResourceEdge,
    ResourceLevel,
    ResourcePressureTracker,
    ResourceReactionGate,
    ResourceSample,
    ResourceSampler,
    habituated_cooldown,
    resource_card_model,
)

MEMINFO = """MemTotal:       16000000 kB
MemFree:         1000000 kB
MemAvailable:    {available} kB
Buffers:          200000 kB
"""


def stat_line(user, nice, system, idle, iowait, irq=0, softirq=0, steal=0) -> str:
    return (
        f"cpu  {user} {nice} {system} {idle} {iowait} {irq} {softirq} {steal} 0 0\n"
        "cpu0 1 2 3 4 5 6 7 8 0 0\n"
    )


class FakeProc:
    def __init__(self) -> None:
        self.stat = stat_line(0, 0, 0, 0, 0)
        self.meminfo = MEMINFO.format(available=8000000)
        self.reads: list[Path] = []
        self.fail: set[Path] = set()

    def read_text(self, path: Path) -> str:
        self.reads.append(path)
        if path in self.fail:
            raise PermissionError(path)
        return {PROC_STAT: self.stat, PROC_MEMINFO: self.meminfo}[path]


class ResourceSamplerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proc = FakeProc()
        self.sampler = ResourceSampler(read_text=self.proc.read_text)

    def test_first_sample_has_no_cpu_value(self) -> None:
        self.assertEqual(self.sampler.sample(), ResourceSample(None, 50))

    def test_cpu_percent_is_busy_share_of_the_delta(self) -> None:
        self.proc.stat = stat_line(100, 0, 100, 700, 100)
        self.sampler.sample()
        # +300 busy (user+system), +100 idle, +0 iowait -> 75 % busy
        self.proc.stat = stat_line(250, 0, 250, 800, 100)
        self.assertEqual(self.sampler.sample().cpu_percent, 75)

    def test_iowait_counts_as_idle(self) -> None:
        self.proc.stat = stat_line(0, 0, 0, 0, 0)
        self.sampler.sample()
        self.proc.stat = stat_line(10, 0, 0, 0, 90)
        self.assertEqual(self.sampler.sample().cpu_percent, 10)

    def test_ram_percent_uses_mem_available(self) -> None:
        self.proc.meminfo = MEMINFO.format(available=1600000)
        self.assertEqual(self.sampler.sample().ram_percent, 90)

    def test_unreadable_files_mean_unknown_not_zero(self) -> None:
        self.proc.fail = {PROC_STAT, PROC_MEMINFO}
        self.assertEqual(self.sampler.sample(), ResourceSample(None, None))

    def test_unreadable_stat_resets_the_cpu_baseline(self) -> None:
        self.sampler.sample()
        self.proc.fail = {PROC_STAT}
        self.sampler.sample()
        self.proc.fail = set()
        self.proc.stat = stat_line(50, 0, 0, 50, 0)
        self.assertIsNone(self.sampler.sample().cpu_percent)

    def test_counter_wrap_or_reset_is_unknown(self) -> None:
        self.proc.stat = stat_line(100, 0, 0, 100, 0)
        self.sampler.sample()
        self.proc.stat = stat_line(10, 0, 0, 10, 0)
        self.assertIsNone(self.sampler.sample().cpu_percent)

    def test_malformed_meminfo_is_unknown(self) -> None:
        self.proc.meminfo = "MemTotal: lots kB\nMemAvailable: 1 kB\n"
        self.assertIsNone(self.sampler.sample().ram_percent)

    def test_reset_forgets_cpu_baseline(self) -> None:
        self.sampler.sample()
        self.sampler.reset()
        self.assertIsNone(self.sampler.sample().cpu_percent)

    def test_reads_only_the_two_aggregate_files(self) -> None:
        self.sampler.sample()
        self.sampler.sample()
        self.assertEqual(set(self.proc.reads), {PROC_STAT, PROC_MEMINFO})
        self.assertEqual(len(self.proc.reads), 4)


def feed(tracker, values, *, start=0.0, step=5.0, ram=50):
    """Feed CPU values every `step` seconds; return all edges with times."""
    edges = []
    now = start
    for cpu in values:
        for edge in tracker.observe(ResourceSample(cpu, ram), now):
            edges.append((now, edge))
        now += step
    return edges, now


class ResourcePressureTrackerTests(unittest.TestCase):
    def test_cpu_busy_needs_sustained_smoothed_load(self) -> None:
        tracker = ResourcePressureTracker()
        edges, _ = feed(tracker, [100] * 20)
        self.assertEqual(len(edges), 1)
        when, edge = edges[0]
        self.assertEqual(edge.level, ResourceLevel.CPU_BUSY)
        self.assertTrue(edge.entered)
        # Smoothed value first reaches 85 % at t=0 (seeded at 100), so the
        # 45 s dwell completes at t=45.
        self.assertEqual(when, 45.0)

    def test_short_spike_does_not_enter(self) -> None:
        tracker = ResourcePressureTracker()
        edges, _ = feed(tracker, [10, 100, 100, 100, 10, 10, 10, 10])
        self.assertEqual(edges, [])

    def test_repeated_busy_samples_emit_no_second_edge(self) -> None:
        tracker = ResourcePressureTracker()
        edges, _ = feed(tracker, [100] * 60)
        self.assertEqual([e.entered for _, e in edges], [True])

    def test_exit_needs_hysteresis_and_dwell(self) -> None:
        tracker = ResourcePressureTracker()
        _, now = feed(tracker, [100] * 12)
        # 70 % is below the 85 % entry but above the 60 % exit: stay busy.
        edges, now = feed(tracker, [70] * 20, start=now)
        self.assertEqual(edges, [])
        edges, _ = feed(tracker, [5] * 20, start=now)
        self.assertEqual([(e.level, e.entered) for _, e in edges],
                         [(ResourceLevel.CPU_BUSY, False)])

    def test_memory_levels_escalate_and_recover(self) -> None:
        tracker = ResourcePressureTracker()
        seen = []
        now = 0.0
        for ram in [96] * 6 + [85] * 10 + [70] * 10:
            seen += [(e.level, e.entered) for e in tracker.observe(ResourceSample(10, ram), now)]
            now += 5.0
        self.assertEqual(seen, [
            (ResourceLevel.MEMORY_CRITICAL, True),
            (ResourceLevel.MEMORY_TIGHT, True),
            (ResourceLevel.MEMORY_CRITICAL, False),
            (ResourceLevel.MEMORY_TIGHT, False),
        ])

    def test_unknown_sample_holds_state_and_restarts_dwell(self) -> None:
        tracker = ResourcePressureTracker()
        tracker.observe(ResourceSample(10, 92), 0.0)
        tracker.observe(ResourceSample(10, 92), 15.0)
        tracker.observe(ResourceSample(10, None), 20.0)   # can't tell
        self.assertEqual(tracker.observe(ResourceSample(10, 92), 25.0), [])
        edges = tracker.observe(ResourceSample(10, 92), 45.0)
        self.assertEqual([e.level for e in edges], [ResourceLevel.MEMORY_TIGHT])

    def test_edges_carry_display_numbers(self) -> None:
        tracker = ResourcePressureTracker()
        edges, _ = feed(tracker, [100] * 12, ram=71)
        edge = edges[0][1]
        self.assertEqual((edge.cpu_percent, edge.ram_percent), (100, 71))

    def test_clear_reports_active_levels_as_ended(self) -> None:
        tracker = ResourcePressureTracker()
        feed(tracker, [100] * 12)
        ended = tracker.clear()
        self.assertEqual([(e.level, e.entered) for e in ended],
                         [(ResourceLevel.CPU_BUSY, False)])
        self.assertEqual(tracker.active_levels, frozenset())
        self.assertEqual(tracker.clear(), [])


class ResourceReactionGateTests(unittest.TestCase):
    def test_cooldown_curve_matches_curiosity(self) -> None:
        self.assertEqual(habituated_cooldown(20.0, 120.0, 0), 20.0)
        self.assertEqual(habituated_cooldown(20.0, 120.0, 2), 45.0)
        self.assertEqual(habituated_cooldown(20.0, 120.0, 99), 120.0)
        self.assertEqual(habituated_cooldown(20.0, 120.0, -3), 20.0)

    def test_first_enter_is_announced_then_cooldown_applies(self) -> None:
        gate = ResourceReactionGate()
        self.assertTrue(gate.should_announce(ResourceLevel.CPU_BUSY, 0.0))
        self.assertFalse(gate.should_announce(ResourceLevel.CPU_BUSY, 10 * 60.0))
        self.assertTrue(gate.should_announce(ResourceLevel.CPU_BUSY, 21 * 60.0))

    def test_cooldown_grows_with_each_announcement(self) -> None:
        gate = ResourceReactionGate()
        minute = 60.0
        self.assertTrue(gate.should_announce(ResourceLevel.MEMORY_TIGHT, 0.0))
        # second announcement needs 20 min, third needs 30 min after that
        self.assertTrue(gate.should_announce(ResourceLevel.MEMORY_TIGHT, 20 * minute))
        self.assertFalse(gate.should_announce(ResourceLevel.MEMORY_TIGHT, 45 * minute))
        self.assertTrue(gate.should_announce(ResourceLevel.MEMORY_TIGHT, 50 * minute))

    def test_critical_memory_escalates_once(self) -> None:
        gate = ResourceReactionGate()
        self.assertTrue(gate.should_announce(ResourceLevel.MEMORY_TIGHT, 0.0))
        self.assertTrue(gate.should_announce(ResourceLevel.MEMORY_CRITICAL, 60.0))
        self.assertFalse(gate.should_announce(ResourceLevel.MEMORY_CRITICAL, 120.0))

    def test_quiet_hour_resets_the_streak(self) -> None:
        gate = ResourceReactionGate()
        hour = 3600.0
        for t in (0.0, 0.34 * hour, 0.85 * hour):
            gate.should_announce(ResourceLevel.CPU_BUSY, t)
        # 1 h+ without any enter edge: back to the 20 min base
        self.assertTrue(gate.should_announce(ResourceLevel.CPU_BUSY, 2.0 * hour))
        self.assertFalse(gate.should_announce(ResourceLevel.CPU_BUSY, 2.2 * hour))
        self.assertTrue(gate.should_announce(ResourceLevel.CPU_BUSY, 2.0 * hour + 20 * 60))


if __name__ == "__main__":
    unittest.main()


class ResourceCardModelTests(unittest.TestCase):
    def test_calm_machine(self) -> None:
        model = resource_card_model(ResourceSample(12, 48), frozenset())
        self.assertEqual(model.state_word, "calm")
        self.assertEqual([(r.label, r.value_text, r.tone, r.badge) for r in model.rows],
                         [("CPU", "12%", "calm", None), ("RAM", "48%", "calm", None)])

    def test_state_word_names_the_most_severe_level(self) -> None:
        cases = [
            ({ResourceLevel.CPU_BUSY}, "busy"),
            ({ResourceLevel.CPU_BUSY, ResourceLevel.MEMORY_TIGHT}, "crowded"),
            ({ResourceLevel.MEMORY_TIGHT, ResourceLevel.MEMORY_CRITICAL}, "almost full"),
        ]
        for active, word in cases:
            with self.subTest(active=active):
                model = resource_card_model(ResourceSample(90, 96), frozenset(active))
                self.assertEqual(model.state_word, word)

    def test_tones_follow_levels_not_raw_numbers(self) -> None:
        # 97 % RAM that has not dwelled long enough to enter is still "calm".
        model = resource_card_model(ResourceSample(99, 97), frozenset())
        self.assertEqual([r.tone for r in model.rows], ["calm", "calm"])
        model = resource_card_model(
            ResourceSample(94, 96),
            frozenset({ResourceLevel.CPU_BUSY, ResourceLevel.MEMORY_TIGHT,
                       ResourceLevel.MEMORY_CRITICAL}),
        )
        self.assertEqual([(r.tone, r.badge) for r in model.rows],
                         [("busy", None), ("critical", "!")])

    def test_unknown_values_render_as_a_dash(self) -> None:
        model = resource_card_model(ResourceSample(None, None), frozenset())
        self.assertEqual([(r.value_text, r.fraction) for r in model.rows],
                         [("–", 0.0), ("–", 0.0)])
```

- [ ] **Step 2: Run them and see them fail**

```bash
PYTHONPATH=src python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_sense.py 2>&1 | tail -3
```

Expected: collection error, `ModuleNotFoundError: No module named 'mochi.resource_sense'`.

- [ ] **Step 3: Implement**

Create `src/mochi/resource_sense.py`:

```python
"""Resource Sense: aggregate CPU and RAM load reduced to coarse edges.

GTK-free so it can be tested without a display. Only two aggregate files are
read (``/proc/stat`` line 1 and ``/proc/meminfo``). Nothing here looks at
per-process data, command lines, or anything the user typed.

Pipeline::

    ResourceSampler.sample()          -> ResourceSample (percent ints or None)
    ResourcePressureTracker.observe() -> [ResourceEdge] on enter/exit only
    ResourceReactionGate.should_announce(level) -> speak/beat/card or stay quiet
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

PROC_STAT = Path("/proc/stat")
PROC_MEMINFO = Path("/proc/meminfo")

# /proc/stat "cpu" columns: user nice system idle iowait irq softirq steal
# guest guest_nice. Guest time is already counted in user/nice, so only the
# first eight columns are summed.
_COUNTED_CPU_COLUMNS = 8
_IDLE_COLUMN = 3
_IOWAIT_COLUMN = 4

CPU_SMOOTHING_ALPHA = 0.3


def _read_ascii(path: Path) -> str:
    return path.read_text(encoding="ascii")


def _clamp_percent(fraction: float) -> int:
    return max(0, min(100, round(fraction * 100)))


@dataclass(frozen=True, slots=True)
class ResourceSample:
    """One reading. ``None`` means "can't tell", never "zero"."""

    cpu_percent: int | None
    ram_percent: int | None


class ResourceSampler:
    """Read aggregate CPU and RAM use from procfs."""

    def __init__(self, *, read_text: Callable[[Path], str] = _read_ascii) -> None:
        self._read_text = read_text
        self._previous_cpu: tuple[int, int] | None = None  # (idle, total)

    def reset(self) -> None:
        """Forget the CPU baseline, e.g. after suspend/resume."""
        self._previous_cpu = None

    def sample(self) -> ResourceSample:
        return ResourceSample(self._cpu_percent(), self._ram_percent())

    def _cpu_percent(self) -> int | None:
        try:
            first_line = self._read_text(PROC_STAT).split("\n", 1)[0]
            fields = first_line.split()
            if not fields or fields[0] != "cpu":
                raise ValueError("unexpected /proc/stat layout")
            columns = [int(value) for value in fields[1 : 1 + _COUNTED_CPU_COLUMNS]]
            if len(columns) <= _IOWAIT_COLUMN:
                raise ValueError("too few cpu columns")
        except (OSError, ValueError):
            self._previous_cpu = None
            return None
        idle = columns[_IDLE_COLUMN] + columns[_IOWAIT_COLUMN]
        total = sum(columns)
        previous, self._previous_cpu = self._previous_cpu, (idle, total)
        if previous is None:
            return None
        total_delta = total - previous[1]
        idle_delta = idle - previous[0]
        if total_delta <= 0 or idle_delta < 0:
            return None
        return _clamp_percent(1.0 - idle_delta / total_delta)

    def _ram_percent(self) -> int | None:
        try:
            text = self._read_text(PROC_MEMINFO)
        except OSError:
            return None
        values: dict[str, int] = {}
        for line in text.splitlines():
            key, _, rest = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                try:
                    values[key] = int(rest.split()[0])
                except (ValueError, IndexError):
                    return None
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if not total or available is None:
            return None
        return _clamp_percent(1.0 - available / total)


class ResourceLevel(Enum):
    CPU_BUSY = "cpu_busy"
    MEMORY_TIGHT = "memory_tight"
    MEMORY_CRITICAL = "memory_critical"


@dataclass(frozen=True, slots=True)
class LevelRule:
    metric: str  # "cpu" (smoothed) or "ram" (raw)
    enter_at: int
    enter_after_seconds: float
    exit_below: int
    exit_after_seconds: float


LEVEL_RULES: dict[ResourceLevel, LevelRule] = {
    ResourceLevel.CPU_BUSY: LevelRule("cpu", 85, 45.0, 60, 30.0),
    ResourceLevel.MEMORY_TIGHT: LevelRule("ram", 90, 20.0, 80, 30.0),
    ResourceLevel.MEMORY_CRITICAL: LevelRule("ram", 95, 10.0, 90, 0.0),
}


@dataclass(frozen=True, slots=True)
class ResourceEdge:
    level: ResourceLevel
    entered: bool
    cpu_percent: int | None
    ram_percent: int | None


@dataclass(slots=True)
class _LevelState:
    active: bool = False
    above_since: float | None = None
    below_since: float | None = None


class ResourcePressureTracker:
    """Turn samples into enter/exit edges with dwell and hysteresis.

    Repeated samples of an already-active level never produce another edge
    (Manual Recipe B: start/stop, never "still busy"). A ``None`` reading
    keeps the current state and restarts any pending dwell.
    """

    def __init__(self, rules: dict[ResourceLevel, LevelRule] | None = None) -> None:
        self._rules = dict(LEVEL_RULES if rules is None else rules)
        self._states = {level: _LevelState() for level in self._rules}
        self._cpu_smoothed: float | None = None
        self._last: ResourceSample = ResourceSample(None, None)

    @property
    def active_levels(self) -> frozenset[ResourceLevel]:
        return frozenset(level for level, state in self._states.items() if state.active)

    @property
    def last_sample(self) -> ResourceSample:
        """Smoothed CPU and raw RAM, for the card's numbers."""
        return self._last

    def observe(self, sample: ResourceSample, now: float) -> list[ResourceEdge]:
        if sample.cpu_percent is not None:
            if self._cpu_smoothed is None:
                self._cpu_smoothed = float(sample.cpu_percent)
            else:
                self._cpu_smoothed += CPU_SMOOTHING_ALPHA * (
                    sample.cpu_percent - self._cpu_smoothed
                )
        cpu = None if self._cpu_smoothed is None else round(self._cpu_smoothed)
        self._last = ResourceSample(cpu, sample.ram_percent)
        if sample.cpu_percent is None:
            cpu = None  # unknown this round: hold state, don't advance dwell
        edges: list[ResourceEdge] = []
        for level, rule in self._rules.items():
            value = cpu if rule.metric == "cpu" else sample.ram_percent
            state = self._states[level]
            if value is None:
                state.above_since = None
                state.below_since = None
                continue
            if not state.active:
                if value >= rule.enter_at:
                    if state.above_since is None:
                        state.above_since = now
                    if now - state.above_since >= rule.enter_after_seconds:
                        state.active = True
                        state.above_since = None
                        edges.append(self._edge(level, entered=True))
                else:
                    state.above_since = None
            else:
                if value < rule.exit_below:
                    if state.below_since is None:
                        state.below_since = now
                    if now - state.below_since >= rule.exit_after_seconds:
                        state.active = False
                        state.below_since = None
                        edges.append(self._edge(level, entered=False))
                else:
                    state.below_since = None
        return edges

    def clear(self) -> list[ResourceEdge]:
        """Drop all state (session away / disable); report levels that ended."""
        ended = [
            self._edge(level, entered=False)
            for level, state in self._states.items()
            if state.active
        ]
        self._states = {level: _LevelState() for level in self._rules}
        self._cpu_smoothed = None
        self._last = ResourceSample(None, None)
        return ended

    def _edge(self, level: ResourceLevel, *, entered: bool) -> ResourceEdge:
        return ResourceEdge(level, entered, self._last.cpu_percent, self._last.ram_percent)


def habituated_cooldown(base: float, cap: float, streak: int, factor: float = 1.5) -> float:
    """Same curve as ActiveWindowCuriosityMixin._habituated_cooldown."""
    return min(base * factor ** min(max(0, streak), 16), cap)


class ResourceReactionGate:
    """Decide which enter edges Mochi announces (speech + beat + auto card).

    One shared clock for every level, so a machine that lives near a
    threshold is mentioned less and less. ``MEMORY_CRITICAL`` may escalate
    past the cooldown once, unless the previous announcement was already
    critical.
    """

    BASE_SECONDS = 20 * 60.0
    CAP_SECONDS = 2 * 60 * 60.0
    STREAK_RESET_SECONDS = 60 * 60.0

    def __init__(self) -> None:
        self._streak = 0
        self._last_announced_at: float | None = None
        self._last_announced_level: ResourceLevel | None = None
        self._last_enter_at: float | None = None

    def should_announce(self, level: ResourceLevel, now: float) -> bool:
        if (
            self._last_enter_at is not None
            and now - self._last_enter_at >= self.STREAK_RESET_SECONDS
        ):
            self._streak = 0
        self._last_enter_at = now
        escalation = (
            level is ResourceLevel.MEMORY_CRITICAL
            and self._last_announced_level is not ResourceLevel.MEMORY_CRITICAL
        )
        if self._last_announced_at is not None and not escalation:
            # The streak counts announcements already made, so the first
            # repeat waits BASE and each later one waits 1.5x longer.
            cooldown = habituated_cooldown(
                self.BASE_SECONDS, self.CAP_SECONDS, self._streak - 1
            )
            if now - self._last_announced_at < cooldown:
                return False
        self._last_announced_at = now
        self._last_announced_level = level
        self._streak += 1
        return True


# -- Card wording (pure, so it is testable without GTK) -----------------------

_STATE_WORDS = (
    (ResourceLevel.MEMORY_CRITICAL, "almost full"),
    (ResourceLevel.MEMORY_TIGHT, "crowded"),
    (ResourceLevel.CPU_BUSY, "busy"),
)


@dataclass(frozen=True, slots=True)
class CardRow:
    label: str          # "CPU" / "RAM"
    value_text: str     # "94%" or "–" when unknown
    fraction: float     # 0.0–1.0 for the bar
    tone: str           # "calm" / "busy" / "critical" (CSS class suffix)
    badge: str | None   # "!" only for critical


@dataclass(frozen=True, slots=True)
class CardModel:
    state_word: str
    rows: tuple[CardRow, ...]


def _row(label: str, percent: int | None, tone: str) -> CardRow:
    if percent is None:
        return CardRow(label, "–", 0.0, "calm", None)
    return CardRow(
        label,
        f"{percent}%",
        max(0.0, min(1.0, percent / 100)),
        tone,
        "!" if tone == "critical" else None,
    )


def resource_card_model(sample: ResourceSample, active: frozenset[ResourceLevel]) -> CardModel:
    """Rows, tones and the state word. Colour follows levels, not raw numbers."""
    state_word = next((word for level, word in _STATE_WORDS if level in active), "calm")
    cpu_tone = "busy" if ResourceLevel.CPU_BUSY in active else "calm"
    if ResourceLevel.MEMORY_CRITICAL in active:
        ram_tone = "critical"
    elif ResourceLevel.MEMORY_TIGHT in active:
        ram_tone = "busy"
    else:
        ram_tone = "calm"
    return CardModel(
        state_word,
        (_row("CPU", sample.cpu_percent, cpu_tone), _row("RAM", sample.ram_percent, ram_tone)),
    )
```

- [ ] **Step 4: Run them and see them pass**

```bash
PYTHONPATH=src python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_sense.py 2>&1 | tail -3
```

Expected: `27 passed`.

- [ ] **Step 5: Full suite, then commit**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add src/mochi/resource_sense.py tests/test_resource_sense.py
git commit -m "feat: add the Resource Sense sampling and edge core"
```

Expected: baseline + 27 passed.

---

### Task 3: Engine values and resource lines

**Files:**
- Modify: `src/mochi/presence/engine.py`
- Modify: `src/mochi/presence/phrases.py`
- Create: `tests/test_resource_engine_events.py`

**Interfaces:**
- Consumes: `PresenceEngine`, `EVENT_PHRASES`, `PhraseBank`.
- Produces:
  - `PresenceEngine.emit(name, *, now=None, values: Mapping[str, int] | None = None) -> bool`
  - `PresenceAction.template: str | None` (new last field, default `None`)
  - Events `cpu_busy` (30), `memory_tight` (30), `memory_critical` (40), category `resources`

**Acceptance Criteria:**
- Resource lines carry the measured number; anti-repeat remembers the template.
- Events without values behave exactly as before; every existing engine test passes unchanged.
- `memory_critical` reaches the Focus floor; the other two stay below it.
- Resource lines expire after 30 s, are dropped on session away, share the 20 min system cooldown, and are silenced by quiet mode.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resource_engine_events.py`. It imports `Clock` and `generous_tuning` from `tests/test_presence_engine.py`, which works because `tests/` is not a package (verified).

```python
"""Resource Sense events in PresenceEngine: numbers in lines, priorities, expiry."""

from __future__ import annotations

import random
import string

import gi
import pytest

gi.require_version("Gtk", "4.0")

from mochi.presence.context import AmbientContext
from mochi.presence.engine import PresenceEngine
from mochi.presence.phrases import EVENT_PHRASES

from test_presence_engine import Clock, generous_tuning

RESOURCE_EVENTS = {
    "cpu_busy": {"cpu": 94, "ram": 71},
    "memory_tight": {"cpu": 20, "ram": 91},
    "memory_critical": {"cpu": 20, "ram": 97},
}


def engine_for(**tuning):
    return PresenceEngine(tuning=generous_tuning(**tuning), rng=random.Random(3), clock=Clock())


@pytest.mark.parametrize("event", sorted(RESOURCE_EVENTS))
def test_resource_line_carries_the_number_mochi_measured(event):
    engine = engine_for()
    assert engine.emit(event, now=0, values=RESOURCE_EVENTS[event])

    action = engine.evaluate(AmbientContext(), now=0)

    assert action.event == event
    assert action.category == "resources"
    assert action.template in EVENT_PHRASES[event]
    assert action.text == action.template.format_map(RESOURCE_EVENTS[event])
    assert "{" not in action.text


@pytest.mark.parametrize("event", sorted(RESOURCE_EVENTS))
def test_resource_templates_only_use_known_placeholders(event):
    for template in EVENT_PHRASES[event]:
        fields = {name for _, name, _, _ in string.Formatter().parse(template) if name}
        assert fields and fields <= {"cpu", "ram"}, template


def test_anti_repeat_remembers_the_template_not_the_filled_text():
    engine = engine_for()
    engine.emit("memory_critical", now=0, values={"ram": 96})
    first = engine.evaluate(AmbientContext(), now=0)
    engine.record_delivered(first, now=0)

    assert first.template in engine.phrases.recent
    assert first.text not in engine.phrases.recent

    engine.emit("memory_critical", now=1, values={"ram": 97})
    second = engine.evaluate(AmbientContext(), now=1)
    assert second.template != first.template


def test_priorities_respect_the_focus_floor():
    from mochi.presence.focus_session import FOCUS_PRESENCE_PRIORITY_FLOOR

    priorities = {}
    for event, values in RESOURCE_EVENTS.items():
        engine = engine_for()
        engine.emit(event, now=0, values=values)
        priorities[event] = engine.evaluate(AmbientContext(), now=0).priority

    assert priorities["cpu_busy"] < FOCUS_PRESENCE_PRIORITY_FLOOR
    assert priorities["memory_tight"] < FOCUS_PRESENCE_PRIORITY_FLOOR
    assert priorities["memory_critical"] >= FOCUS_PRESENCE_PRIORITY_FLOOR


def test_resource_lines_expire_after_thirty_seconds():
    engine = engine_for()
    engine.emit("cpu_busy", now=0, values=RESOURCE_EVENTS["cpu_busy"])

    action = engine.evaluate(AmbientContext(), now=31)

    assert action is None or action.event != "cpu_busy"


def test_session_away_drops_queued_resource_lines():
    engine = engine_for()
    engine.emit("memory_tight", now=0, values=RESOURCE_EVENTS["memory_tight"])
    engine.note_session_away()

    action = engine.evaluate(AmbientContext(), now=0)

    assert action is None or action.event != "memory_tight"


def test_resources_share_the_system_event_cooldown():
    engine = engine_for(system_event_cooldown_seconds=1200)
    engine.emit("cpu_busy", now=0, values=RESOURCE_EVENTS["cpu_busy"])
    engine.record_delivered(engine.evaluate(AmbientContext(), now=0), now=0)

    engine.emit("memory_tight", now=60, values=RESOURCE_EVENTS["memory_tight"])
    action = engine.evaluate(AmbientContext(), now=60)

    assert action is None or action.event != "memory_tight"


def test_quiet_mode_silences_resource_lines():
    engine = engine_for(quiet_mode=True)
    engine.emit("memory_critical", now=0, values=RESOURCE_EVENTS["memory_critical"])

    assert engine.evaluate(AmbientContext(), now=0) is None


def test_events_without_values_are_unchanged():
    engine = engine_for(agent_event_probability=1)
    engine.emit("agent_finished", now=0)

    action = engine.evaluate(AmbientContext(), now=0)

    assert action.template is None
    assert action.text in EVENT_PHRASES["agent_finished"]
```

- [ ] **Step 2: Run them and see them fail**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_engine_events.py 2>&1 | tail -3
```

Expected: failures, starting with `TypeError: PresenceEngine.emit() got an unexpected keyword argument 'values'`.

- [ ] **Step 3: Apply the engine change**

```diff
--- a/src/mochi/presence/engine.py
+++ b/src/mochi/presence/engine.py
@@ -3,7 +3,7 @@
 from __future__ import annotations

 from collections import deque
-from collections.abc import Callable
+from collections.abc import Callable, Mapping
 from dataclasses import dataclass, field
 import logging
 import random
@@ -90,6 +90,9 @@
     priority: int
     event: str | None = None
     display_seconds: float = 3.5
+    # The unformatted phrase, remembered for anti-repeat when ``text`` has
+    # numbers filled in ("(CPU 94%)" vs "(CPU 91%)" are the same line).
+    template: str | None = None

     def __post_init__(self) -> None:
         # Normal ambient/contextual AmbiSense speech gets the small fake
@@ -108,6 +111,7 @@
 class _QueuedEvent:
     name: str
     created_at: float
+    values: tuple[tuple[str, int], ...] = ()


 _EVENT_PRIORITY = {
@@ -124,6 +128,11 @@
     # Coding-agent lines stay below the Focus floor (40) on purpose.
     "agent_needs_input": 30,
     "agent_finished": 30,
+    # Resource Sense: busy CPU and tight memory stay below the Focus floor;
+    # memory that is about to run out is worth one line even during Focus.
+    "cpu_busy": 30,
+    "memory_tight": 30,
+    "memory_critical": 40,
 }
 _EVENT_CATEGORY = {
     "user_returned": "return_from_idle",
@@ -136,6 +145,9 @@
     "build_succeeded": "developer",
     "agent_needs_input": "agent",
     "agent_finished": "agent",
+    "cpu_busy": "resources",
+    "memory_tight": "resources",
+    "memory_critical": "resources",
 }

 # Queued events normally wait up to 120 s for a chance to be spoken. Agent
@@ -143,6 +155,9 @@
 _EVENT_TTL_SECONDS = {
     "agent_needs_input": 30.0,
     "agent_finished": 30.0,
+    "cpu_busy": 30.0,
+    "memory_tight": 30.0,
+    "memory_critical": 30.0,
 }
 _DEFAULT_EVENT_TTL_SECONDS = 120.0

@@ -213,6 +228,7 @@
         environmental = {
             "network_lost", "network_restored", "battery_low",
             "charging_started", "media_started", "user_returned",
+            "cpu_busy", "memory_tight", "memory_critical",
         }
         self._events = deque(
             (event for event in self._events if event.name not in environmental),
@@ -236,7 +252,13 @@
     def set_ambient_reactions_enabled(self, enabled: bool) -> None:
         self.tuning.ambient_reactions_enabled = bool(enabled)

-    def emit(self, name: str, *, now: float | None = None) -> bool:
+    def emit(
+        self,
+        name: str,
+        *,
+        now: float | None = None,
+        values: Mapping[str, int] | None = None,
+    ) -> bool:
         if name not in _EVENT_PRIORITY:
             self._logger.debug("[presence] ignored unknown event=%s", name)
             return False
@@ -246,7 +268,9 @@
             source, state = transient_state
             self._invalidate_transient_events(source, except_state=state)
         if not any(event.name == name for event in self._events):
-            self._events.append(_QueuedEvent(name, timestamp))
+            self._events.append(
+                _QueuedEvent(name, timestamp, tuple(sorted((values or {}).items())))
+            )
             self._logger.debug("[presence] event=%s queued", name)
         return True

@@ -383,7 +407,7 @@
             self._welcome_back_pending = False
         if action.event == "welcome_back":
             self._welcome_back_pending = False
-        self.phrases.remember(action.text)
+        self.phrases.remember(action.template or action.text)
         self.cooldowns.record(
             action.category,
             now=timestamp,
@@ -435,16 +459,25 @@
                 self._logger.debug("[presence] event=%s suppressed: silence roll", event.name)
                 continue
             choices = EVENT_PHRASES.get(event.name)
-            text = (
+            template = (
                 self.phrases.choose_from(choices, exclude_recent=True)
                 if choices
                 else self.phrases.choose(category, exclude_recent=True)
             )
+            if event.values:
+                try:
+                    text = template.format_map(dict(event.values))
+                except (KeyError, IndexError, ValueError):
+                    self._logger.debug("[presence] event=%s bad template %r", event.name, template)
+                    continue
+            else:
+                text = template
             self._logger.debug("[presence] event=%s selected=%r", event.name, text)
             self._events.clear()
             return PresenceAction(
                 "speech", category, text, _EVENT_PRIORITY[event.name], event.name,
                 speech_display_seconds(text),
+                template if event.values else None,
             )
         return None

@@ -560,7 +593,7 @@
     def _category_cooldown(self, category: str) -> float:
         if category == "body_care":
             return self.tuning.body_care_cooldown_seconds
-        if category in ("battery", "network"):
+        if category in ("battery", "network", "resources"):
             return self.tuning.system_event_cooldown_seconds
         return self._rng.uniform(
             self.tuning.same_category_min_seconds,
@@ -578,6 +611,8 @@
             return self.tuning.build_event_probability
         if name in ("agent_needs_input", "agent_finished"):
             return self.tuning.agent_event_probability
+        if name in ("cpu_busy", "memory_tight", "memory_critical"):
+            return self.tuning.system_event_probability
         return 1.0

     def _prune_events(self, now: float) -> None:
```

- [ ] **Step 4: Add the lines**

```diff
--- a/src/mochi/presence/phrases.py
+++ b/src/mochi/presence/phrases.py
@@ -876,6 +876,22 @@
 }

 EVENT_PHRASES: dict[str, tuple[str, ...]] = {
+    # Resource Sense lines carry Mochi-computed integers ({cpu}, {ram}).
+    # Feel first, number second; never tell the user to close anything.
+    "cpu_busy": (
+        "Whew, the computer's thinking really hard… (CPU {cpu}%)",
+        "Is it warm in here? (CPU {cpu}%)",
+        "Something's keeping the computer busy. (CPU {cpu}%)",
+    ),
+    "memory_tight": (
+        "It's getting crowded in here… (RAM {ram}%)",
+        "Scootching over to make room. (RAM {ram}%)",
+        "Lots of things open today! (RAM {ram}%)",
+    ),
+    "memory_critical": (
+        "Squished! Memory's almost full. (RAM {ram}%)",
+        "No room left to wiggle… (RAM {ram}%)",
+    ),
     "battery_low": (
         "we're getting sleepy 🔋",
         "battery looking a little tired",
```

- [ ] **Step 5: Run the new and existing engine tests**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_engine_events.py tests/test_presence_engine.py 2>&1 | tail -3
```

Expected: `83 passed` on `4713426` (13 new + 70 existing).

- [ ] **Step 6: Full suite, then commit**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
git add src/mochi/presence/engine.py src/mochi/presence/phrases.py tests/test_resource_engine_events.py
git commit -m "feat: let presence events carry numbers for Resource Sense lines"
```

---

### Task 4: The resource card surface

**Files:**
- Create: `src/mochi/presence/resource_card.py`
- Create: `tests/test_resource_card.py`

**Interfaces:**
- Consumes: `CardModel` from Task 2; `get_window_position`, `move_window`, `request_keep_above` from `mochi.x11`; `ANIMATIONS` from `mochi.sprites`.
- Produces:
  - `ResourceCard(*, owner, anchor_widget, logger=None)` with `active`, `visible`, `show_model(model)`, `deactivate()`, `suspend()`, `resume()`, `update_position()`, `destroy()`
  - `card_position(...) -> (x, y)`, a pure placement function
  - `RESOURCE_CARD_CSS`

**Acceptance Criteria:**
- Never takes input or focus: every widget, the window and the popover have targeting and focus off, as in `BondProgressOverlay.__init__` (`bond_progress_overlay.py:122-144`).
- `show_model` updates both copies (window and popover) and leaves exactly one tone class per bar.
- `suspend()` hides without deactivating; `resume()` shows only while active; `deactivate()` hides and clears `active`; `destroy()` is safe.
- Near the top of a monitor the card goes **below** Mochi (the bubble's rule, `bubble.py:516-521`). The bond card clamps instead, so this is a deliberate difference.
- The theme trough minimum is overridden so the card is about 210×84 px including its shadow margins, matching the mockup.
- The state word uses full foreground (10 px / 600), not 0.62 alpha.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resource_card.py`, using the `object.__new__` harness style of `tests/test_bond_progress_overlay.py:14-56`:

```python
"""ResourceCard: a visual-only surface that mirrors the bond card's lifecycle."""

from __future__ import annotations

from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")

from mochi.presence import resource_card
from mochi.presence.resource_card import ResourceCard, _CardWidgets, _RowWidgets, card_position
from mochi.resource_sense import ResourceLevel, ResourceSample, resource_card_model


def _widgets() -> _CardWidgets:
    rows = (_RowWidgets(Mock(), Mock(), Mock()), _RowWidgets(Mock(), Mock(), Mock()))
    return _CardWidgets(Mock(), Mock(), rows)


def _card() -> ResourceCard:
    card = object.__new__(ResourceCard)
    card._active = False
    card._mode = None
    card._owner = Mock()
    card._anchor = Mock()
    card._logger = Mock()
    card._widgets = _widgets()
    card._popover_widgets = _widgets()
    card._window = Mock()
    card._window.get_visible.return_value = False
    card._popover = Mock()
    card._popover.get_visible.return_value = False
    return card


def test_show_model_writes_both_copies_and_activates():
    card = _card()
    model = resource_card_model(
        ResourceSample(94, 96),
        frozenset({ResourceLevel.CPU_BUSY, ResourceLevel.MEMORY_CRITICAL}),
    )
    card.show_model(model)
    assert card.active is True
    for widgets in (card._widgets, card._popover_widgets):
        widgets.state.set_label.assert_called_with("almost full")
        cpu, ram = widgets.rows
        cpu.value.set_label.assert_called_with("94%")
        ram.value.set_label.assert_called_with("! 96%")
        cpu.bar.set_fraction.assert_called_with(0.94)
        cpu.bar.add_css_class.assert_called_with("mochi-resource-busy")
        ram.bar.add_css_class.assert_called_with("mochi-resource-critical")


def test_tone_classes_are_swapped_not_stacked():
    card = _card()
    card.show_model(resource_card_model(ResourceSample(10, 10), frozenset()))
    bar = card._widgets.rows[0].bar
    removed = {call.args[0] for call in bar.remove_css_class.call_args_list}
    assert removed == {"mochi-resource-calm", "mochi-resource-busy", "mochi-resource-critical"}
    bar.add_css_class.assert_called_once_with("mochi-resource-calm")


def test_suspend_hides_but_keeps_active():
    card = _card()
    card._active = True
    card._window.get_visible.return_value = True
    card.suspend()
    card._window.hide.assert_called_once_with()
    assert card.active is True


def test_resume_does_nothing_when_inactive():
    card = _card()
    with patch.object(resource_card, "get_window_position", return_value=(0, 0)):
        card.resume()
    card._window.set_visible.assert_not_called()
    card._popover.popup.assert_not_called()


def test_resume_uses_the_x11_window_when_positionable():
    card = _card()
    card._active = True
    card._position_x11 = Mock()
    card._window.set_visible.side_effect = (
        lambda value: card._window.get_visible.configure_mock(return_value=value)
    )
    with patch.object(resource_card, "get_window_position", return_value=(10, 20)):
        card.resume()
    card._window.set_visible.assert_called_once_with(True)
    card._position_x11.assert_called_once_with()
    assert card._mode == "x11"


def test_resume_uses_the_popover_on_wayland():
    card = _card()
    card._active = True
    card._position_wayland_anchor = Mock()
    with patch.object(resource_card, "get_window_position", return_value=None):
        card.resume()
    card._popover.popup.assert_called_once_with()
    assert card._mode == "wayland"


def test_deactivate_hides_and_clears_active():
    card = _card()
    card._active = True
    card._popover.get_visible.return_value = True
    card.deactivate()
    card._popover.popdown.assert_called_once_with()
    assert card.active is False


def test_css_uses_theme_colours_and_the_three_tones():
    css = resource_card.RESOURCE_CARD_CSS
    assert "@theme_bg_color" in css and "@theme_fg_color" in css
    for colour in ("#79c98b", "#e5a50a", "#e66a5c"):
        assert colour in css
    assert "alpha(@theme_fg_color, 0.62)" not in css  # state word stays legible


MONITOR = [(0.0, 0.0, 1920.0, 1080.0)]


def _place(visible_top, visible_bottom, center_x=960.0):
    return card_position(
        center_x=center_x, visible_top=visible_top, visible_bottom=visible_bottom,
        card_width=196.0, card_height=74.0, gap=7.0, monitor_padding=12.0,
        monitors=MONITOR, fallback_right=0.0, fallback_bottom=0.0,
    )


def test_card_sits_centred_above_the_sprite():
    assert _place(visible_top=800.0, visible_bottom=900.0) == (862, 719)


def test_card_falls_below_when_there_is_no_room_above():
    x, y = _place(visible_top=40.0, visible_bottom=140.0)
    assert y == 147  # 140 + 7 gap, not clamped on top of Mochi


def test_card_is_clamped_to_the_monitor_edges():
    x, _ = _place(visible_top=800.0, visible_bottom=900.0, center_x=20.0)
    assert x == 12
    x, _ = _place(visible_top=800.0, visible_bottom=900.0, center_x=1915.0)
    assert x == 1920 - 12 - 196
```

`tests/test_theme_colors.py` already scans every `src/mochi/**/*.py` for disallowed `@name` colours, so it covers the new file without changes.

- [ ] **Step 2: Run them and see them fail**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_card.py 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'mochi.presence.resource_card'`.

- [ ] **Step 3: Implement**

Create `src/mochi/presence/resource_card.py`. The placement helpers are copied from `bond_progress_overlay.py:608-740` rather than imported, so neither surface depends on the other; the X11 vertical rule is the bubble's.

```python
"""Visual-only CPU/RAM card above Mochi (Resource Sense).

Built like BondProgressOverlay: a transient X11 window on XWayland and a
popover on pure Wayland, with no input, focus, gestures or GTK autohide
anywhere (nameplate.py's docstring records why). NameplateMixin decides when
the card may own the shared anchor; this class only shows, hides and places
itself.

The positioning helpers are copied from bond_progress_overlay.py rather than
imported, so neither surface depends on the other. Unlike the bond card, the
X11 placement falls back below Mochi when there is no room above, as the
speech bubble does (bubble.py).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.resource_sense import CardModel  # noqa: E402
from mochi.sprites import ANIMATIONS  # noqa: E402
from mochi.x11 import get_window_position, move_window, request_keep_above  # noqa: E402

_TONES = ("calm", "busy", "critical")

RESOURCE_CARD_CSS = """
window.mochi-resource-window {
    background: transparent;
}
.mochi-resource-shell {
    background: transparent;
}
.mochi-resource-card {
    background: alpha(@theme_bg_color, 0.97);
    color: @theme_fg_color;
    border: 1px solid alpha(#79c98b, 0.44);
    border-radius: 11px;
    box-shadow: 0 5px 18px alpha(black, 0.16);
    padding: 8px 10px;
}
.mochi-resource-title {
    font-size: 11px;
    font-weight: 700;
}
.mochi-resource-state {
    font-size: 10px;
    font-weight: 600;
}
.mochi-resource-label {
    font-size: 10px;
    font-weight: 700;
    min-width: 28px;
}
.mochi-resource-value {
    font-size: 11px;
    font-weight: 700;
    font-feature-settings: "tnum";
}
progressbar.mochi-resource-bar trough {
    min-width: 96px;
    min-height: 7px;
    border-radius: 999px;
    background: alpha(@theme_fg_color, 0.12);
}
progressbar.mochi-resource-bar progress {
    min-height: 7px;
    border-radius: 999px;
}
progressbar.mochi-resource-calm progress {
    background: #79c98b;
}
progressbar.mochi-resource-busy progress {
    background: #e5a50a;
}
progressbar.mochi-resource-critical progress {
    background: #e66a5c;
}
popover.mochi-resource-popover > contents {
    background: transparent;
    border: none;
    box-shadow: none;
    padding: 0;
}
popover.mochi-resource-popover > arrow {
    background: alpha(@theme_bg_color, 0.97);
    border-color: alpha(#79c98b, 0.44);
}
"""


@dataclass(slots=True)
class _RowWidgets:
    label: Gtk.Label
    bar: Gtk.ProgressBar
    value: Gtk.Label


@dataclass(slots=True)
class _CardWidgets:
    root: Gtk.Box
    state: Gtk.Label
    rows: tuple[_RowWidgets, _RowWidgets]


class ResourceCard:
    """Two meters and a state word. Never participates in input handling."""

    GAP_PX = 7
    MONITOR_PADDING_PX = 12
    FALLBACK_WIDTH = 210  # measured under Xvfb, shell margins included
    FALLBACK_HEIGHT = 84

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        anchor_widget: Gtk.Widget,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._anchor = anchor_widget
        self._logger = logger or logging.getLogger(__name__)
        self._active = False
        self._mode: str | None = None
        self._widgets = self._make_content()
        self._popover_widgets = self._make_content()

        self._window = Gtk.Window()
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_modal(False)
        self._window.set_focusable(False)
        self._window.set_can_focus(False)
        self._window.set_hide_on_close(True)
        self._window.set_transient_for(owner)
        self._window.add_css_class("mochi-resource-window")
        self._window.set_child(self._widgets.root)
        self._window.connect("map", self._on_window_map)

        self._popover = Gtk.Popover()
        self._popover.set_parent(anchor_widget)
        self._popover.set_autohide(False)
        self._popover.set_has_arrow(True)
        self._popover.set_position(Gtk.PositionType.TOP)
        self._popover.set_offset(0, -self.GAP_PX)
        self._popover.set_focusable(False)
        self._popover.set_can_focus(False)
        self._popover.set_can_target(False)
        self._popover.add_css_class("mochi-resource-popover")
        self._popover.set_child(self._popover_widgets.root)

        self._install_css(owner.get_display())

    @staticmethod
    def _make_content() -> _CardWidgets:
        # The transparent shell margins keep the card's shadow from clipping.
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shell.add_css_class("mochi-resource-shell")
        for set_margin in (
            shell.set_margin_top,
            shell.set_margin_bottom,
            shell.set_margin_start,
            shell.set_margin_end,
        ):
            set_margin(7)
        shell.set_focusable(False)
        shell.set_can_focus(False)
        shell.set_can_target(False)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        card.add_css_class("mochi-resource-card")
        card.set_can_target(False)
        shell.append(card)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Computer")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("mochi-resource-title")
        state = Gtk.Label(label="calm")
        state.set_xalign(1)
        state.add_css_class("mochi-resource-state")
        header.append(title)
        header.append(state)
        card.append(header)

        rows: list[_RowWidgets] = []
        for name in ("CPU", "RAM"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            label = Gtk.Label(label=name)
            label.set_xalign(0)
            label.add_css_class("mochi-resource-label")
            bar = Gtk.ProgressBar()
            bar.set_hexpand(True)
            bar.set_valign(Gtk.Align.CENTER)
            bar.set_size_request(96, 7)
            bar.add_css_class("mochi-resource-bar")
            bar.add_css_class("mochi-resource-calm")
            value = Gtk.Label(label="–")
            value.set_xalign(1)
            value.set_width_chars(4)
            value.add_css_class("mochi-resource-value")
            for widget in (label, bar, value):
                widget.set_can_target(False)
                row.append(widget)
            card.append(row)
            rows.append(_RowWidgets(label, bar, value))
        return _CardWidgets(shell, state, (rows[0], rows[1]))

    @property
    def active(self) -> bool:
        return self._active

    @property
    def visible(self) -> bool:
        return bool(self._window.get_visible() or self._popover.get_visible())

    def show_model(self, model: CardModel) -> None:
        for widgets in (self._widgets, self._popover_widgets):
            widgets.state.set_label(model.state_word)
            for row_widgets, row in zip(widgets.rows, model.rows):
                row_widgets.label.set_label(row.label)
                row_widgets.bar.set_fraction(row.fraction)
                for tone in _TONES:
                    row_widgets.bar.remove_css_class(f"mochi-resource-{tone}")
                row_widgets.bar.add_css_class(f"mochi-resource-{row.tone}")
                text = f"{row.badge} {row.value_text}" if row.badge else row.value_text
                row_widgets.value.set_label(text)
        self._active = True

    def deactivate(self) -> None:
        self._active = False
        self._hide_surfaces()

    def suspend(self) -> None:
        """Temporarily yield the shared anchor (bubble, bond card, Focus hint)."""
        self._hide_surfaces()

    def resume(self) -> None:
        if not self._active:
            return
        if get_window_position(self._owner) is not None:
            self._mode = "x11"
            if self._popover.get_visible():
                self._popover.popdown()
            self._window.set_visible(True)
            self.update_position()
        else:
            self._mode = "wayland"
            if self._window.get_visible():
                self._window.hide()
            self.update_position()
            if not self._popover.get_visible():
                self._popover.popup()

    def update_position(self) -> None:
        if not self.visible:
            return
        if self._mode == "x11":
            self._position_x11()
        elif self._mode == "wayland":
            self._position_wayland_anchor()

    def destroy(self) -> None:
        self.deactivate()
        self._window.destroy()
        self._popover.unparent()

    def _hide_surfaces(self) -> None:
        if self._window.get_visible():
            self._window.hide()
        if self._popover.get_visible():
            self._popover.popdown()
        self._mode = None

    # -- Placement (copied from bond_progress_overlay.py) ------------------------

    def _visible_anchor_bounds(
        self, owner_width: int, owner_height: int
    ) -> tuple[float, float, float, float]:
        atlas = getattr(self._anchor, "atlas", None)
        if atlas is not None and hasattr(atlas, "visible_bounds"):
            # A fixed idle reference frame keeps the card from jittering with
            # the animation, exactly like the bond card and nameplate.
            reference_frame = replace(
                ANIMATIONS["idle"].frames[0],
                horizontal_offset=0.0,
                vertical_offset=0.0,
            )
            try:
                return atlas.visible_bounds(reference_frame, owner_width, owner_height)
            except Exception as exc:
                self._logger.debug(
                    "Resource card visible-bounds lookup failed; using widget bounds: %s",
                    exc,
                )
        return (0.0, 0.0, float(owner_width), float(owner_height))

    @staticmethod
    def _x11_coordinate_scale(window: Gtk.Window) -> float:
        surface = window.get_surface()
        if surface is None:
            return 1.0
        for getter_name in ("get_scale", "get_scale_factor"):
            getter = getattr(surface, getter_name, None)
            if callable(getter):
                try:
                    scale = float(getter())
                except (TypeError, ValueError):
                    scale = 1.0
                if scale > 0:
                    return scale
        return 1.0

    def _position_wayland_anchor(self) -> None:
        width = max(1, self._anchor.get_width())
        height = max(1, self._anchor.get_height())
        visible_x, visible_y, visible_width, _ = self._visible_anchor_bounds(width, height)
        rectangle = Gdk.Rectangle()
        rectangle.x = round(visible_x + visible_width / 2)
        rectangle.y = round(visible_y)
        rectangle.width = 1
        rectangle.height = 1
        self._popover.set_pointing_to(rectangle)

    def _position_x11(self) -> bool:
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            self.suspend()
            return GLib.SOURCE_REMOVE

        owner_x, owner_y = owner_position
        owner_width = max(1, self._owner.get_width())
        owner_height = max(1, self._owner.get_height())
        width = self._window.get_width()
        height = self._window.get_height()
        if width <= 1:
            width = self.FALLBACK_WIDTH
        if height <= 1:
            height = self.FALLBACK_HEIGHT

        owner_scale = self._x11_coordinate_scale(self._owner)
        overlay_scale = self._x11_coordinate_scale(self._window)
        visible_x, visible_y, visible_width, visible_height = self._visible_anchor_bounds(
            owner_width, owner_height
        )
        visible_x *= owner_scale
        visible_y *= owner_scale
        visible_width *= owner_scale
        visible_height *= owner_scale
        overlay_width = width * overlay_scale
        overlay_height = height * overlay_scale
        gap = self.GAP_PX * owner_scale
        monitor_padding = self.MONITOR_PADDING_PX * owner_scale

        center_x = owner_x + visible_x + visible_width / 2
        visible_top = owner_y + visible_y
        visible_bottom = visible_top + visible_height

        display = self._owner.get_display()
        monitors = display.get_monitors()
        geometries = [
            monitors.get_item(index).get_geometry()
            for index in range(monitors.get_n_items())
        ]
        x, y = card_position(
            center_x=center_x,
            visible_top=visible_top,
            visible_bottom=visible_bottom,
            card_width=overlay_width,
            card_height=overlay_height,
            gap=gap,
            monitor_padding=monitor_padding,
            monitors=[
                (g.x * owner_scale, g.y * owner_scale, g.width * owner_scale, g.height * owner_scale)
                for g in geometries
            ],
            fallback_right=owner_x + owner_width * owner_scale + overlay_width,
            fallback_bottom=owner_y + owner_height * owner_scale + overlay_height,
        )
        move_window(self._window, x, y)
        return GLib.SOURCE_REMOVE

    def _on_window_map(self, _window: Gtk.Window) -> None:
        request_keep_above(self._window)
        GLib.idle_add(self._position_x11)

    @staticmethod
    def _install_css(display: Gdk.Display | None) -> None:
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_string(RESOURCE_CARD_CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )


def card_position(
    *,
    center_x: float,
    visible_top: float,
    visible_bottom: float,
    card_width: float,
    card_height: float,
    gap: float,
    monitor_padding: float,
    monitors: list[tuple[float, float, float, float]],
    fallback_right: float,
    fallback_bottom: float,
) -> tuple[int, int]:
    """Centre above the sprite; below it when there is no room; clamp to the monitor.

    Pure (device pixels in, device pixels out) so the top-edge fallback is
    testable without a display. Mirrors bubble.py's above-else-below rule.
    """
    if monitors:
        monitor_x, monitor_y, monitor_width, monitor_height = min(
            monitors,
            key=lambda m: (max(m[0], min(center_x, m[0] + m[2])) - center_x) ** 2
            + (max(m[1], min(visible_top, m[1] + m[3])) - visible_top) ** 2,
        )
        left = monitor_x + monitor_padding
        top = monitor_y + monitor_padding
        right = monitor_x + monitor_width - monitor_padding
        bottom = monitor_y + monitor_height - monitor_padding
    else:
        left, top = 0.0, 0.0
        right, bottom = fallback_right, fallback_bottom

    x = round(center_x - card_width / 2)
    y_above = round(visible_top - card_height - gap)
    y_below = round(visible_bottom + gap)
    y = y_above if y_above >= top else y_below
    x = max(round(left), min(x, max(round(left), round(right - card_width))))
    y = max(round(top), min(y, max(round(top), round(bottom - card_height))))
    return x, y
```

- [ ] **Step 4: Run the card and theme tests**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_card.py tests/test_theme_colors.py 2>&1 | tail -3
```

Expected: all pass (11 card tests).

- [ ] **Step 5: Construct a real card headless (not committed)**

```bash
PYTHONPATH=src xvfb-run -a python3.12 - <<'PY'
import gi; gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from mochi.presence.resource_card import ResourceCard
from mochi.resource_sense import ResourceLevel, ResourceSample, resource_card_model
Gtk.init()
owner = Gtk.Window(); owner.present(); ctx = GLib.MainContext.default()
card = ResourceCard(owner=owner, anchor_widget=owner)
card.show_model(resource_card_model(
    ResourceSample(94, 96), frozenset({ResourceLevel.CPU_BUSY, ResourceLevel.MEMORY_CRITICAL})))
card.resume()
for _ in range(80): ctx.iteration(False)
print("mode:", card._mode, "visible:", card.visible,
      "size:", card._window.get_width(), "x", card._window.get_height())
card.suspend(); print("after suspend:", card.visible, "active:", card.active)
card.destroy(); print("destroyed ok")
PY
```

Expected (verified 2026-10-06 under Xvfb): `mode: x11 visible: True size: 210 x 84`, `after suspend: False active: True`, `destroyed ok`.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/presence/resource_card.py tests/test_resource_card.py
git commit -m "feat: add the Resource Sense card surface"
```

---

### Task 5: ResourceSenseMixin, anchor tier, menu row and Lab preview

**Files:**
- Create: `src/mochi/presence/resource_sense.py`
- Create: `tests/test_resource_sense_mixin.py`
- Modify: `src/mochi/presence/nameplate_controls.py`
- Create: `tests/test_resource_card_anchor.py`
- Modify: `src/mochi/presence/click_dialogue.py`

**Interfaces:**
- Consumes: Tasks 2–4; `_curiosity_suppression()` (`curiosity.py:140`), `_play_idle_beat()` (`idle_look.py:91`), `_ambient_presence_engine`, `_session_blocked()` (`integration.py:650`), `_register_context_menu_row()`, `_close_context_menu_then()`, `_make_menu_button()`, `_developer_menu_content`.
- Produces: `ResourceSenseMixin` with the attributes `_resource_card`, `_resource_tracker`, `_resource_pinned`, and the cooperative overrides `_on_enter`, `_on_leave`, `_build_context_menu`, `_build_developer_menu`, `_on_presence_session_away`, `_on_presence_session_returned`, `shutdown_presence`.

**Acceptance Criteria:**
- Every test below passes, plus the full suite.
- `ResourceSenseMixin` sits immediately **before** `AgentCoworkMixin` in both buddy classes. `tests/test_agent_cowork.py:358-362` pins `AgentCoworkMixin` directly before `TerminalCoworkMixin`, so it cannot go after it. It must also precede `NameplateMixin`, so its hover override decides before the anchor is resolved.
- Every cooperative hook tolerates an object built with `object.__new__` (other suites run the full shutdown chain on such objects).
- The new tier sits between the Focus hint and feedback; existing nameplate tests pass unchanged.
- The menu row is registered after `stay-put` through `_register_context_menu_row`; `tests/test_context_menu_layout.py` passes.

- [ ] **Step 1: Write the failing mixin tests**

Create `tests/test_resource_sense_mixin.py`:

```python
"""ResourceSenseMixin lifecycle with fake bases, a fake card, and fake GLib."""

from __future__ import annotations

from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from mochi.presence import resource_sense as module
from mochi.presence.resource_sense import ResourceSenseMixin
from mochi.resource_sense import ResourceEdge, ResourceLevel, ResourceSample


class FakeGLib:
    SOURCE_CONTINUE = GLib.SOURCE_CONTINUE
    SOURCE_REMOVE = GLib.SOURCE_REMOVE

    def __init__(self) -> None:
        self.sources: dict[int, tuple[int, object]] = {}
        self._next = 1

    def timeout_add_seconds(self, interval, callback):
        source_id = self._next
        self._next += 1
        self.sources[source_id] = (interval, callback)
        return source_id

    def source_remove(self, source_id):
        del self.sources[source_id]

    def fire(self, source_id):
        _interval, callback = self.sources[source_id]
        result = callback()
        if result is GLib.SOURCE_REMOVE:
            self.sources.pop(source_id, None)
        return result

    @property
    def intervals(self) -> list[int]:
        return [interval for interval, _ in self.sources.values()]


class FakeCard:
    def __init__(self) -> None:
        self.active = False
        self.visible = False
        self.model = None
        self.destroyed = 0

    def show_model(self, model):
        self.model = model
        self.active = True
        self.visible = True  # no bubble in these tests: shown immediately

    def deactivate(self):
        self.active = False
        self.visible = False

    def destroy(self):
        self.destroyed += 1
        self.deactivate()


class _Base:
    def __init__(self, *args, **kwargs) -> None:
        self._preview_mode = True  # keep __init__ from building a real card/source
        self._presence_shutting_down = False
        self._blocked = False
        self._suppression: str | None = None
        self._ambient_presence_engine = Mock()
        self._logger = Mock()
        self.beats: list[str] = []
        self.beat_allowed = True
        self.calls: list[str] = []

    def _session_blocked(self) -> bool:
        return self._blocked

    def _curiosity_suppression(self):
        return self._suppression

    def _play_idle_beat(self, name: str) -> bool:
        if self.beat_allowed:
            self.beats.append(name)
            return True
        return False

    def _on_enter(self, controller, x, y):
        self.calls.append("enter")

    def _on_leave(self, controller):
        self.calls.append("leave")

    def _on_presence_session_away(self):
        self.calls.append("away")

    def _on_presence_session_returned(self):
        self.calls.append("returned")

    def _close_context_menu_then(self, action):
        action()

    def shutdown_presence(self):
        self.calls.append("shutdown")


class Harness(ResourceSenseMixin, _Base):
    pass


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def env(monkeypatch):
    glib = FakeGLib()
    monkeypatch.setattr(module.GLib, "timeout_add_seconds", glib.timeout_add_seconds)
    monkeypatch.setattr(module.GLib, "source_remove", glib.source_remove)
    buddy = Harness()
    buddy._preview_mode = False
    clock = Clock()
    buddy._resource_now = clock
    samples: list[ResourceSample] = []
    buddy._resource_sampler = Mock()
    buddy._resource_sampler.sample.side_effect = lambda: samples.pop(0) if samples else ResourceSample(5, 40)
    buddy._resource_card = FakeCard()
    return buddy, glib, clock, samples


def only_source(glib):
    assert len(glib.sources) == 1, glib.sources
    return next(iter(glib.sources))


def run_load(buddy, glib, clock, samples, cpu, ram, seconds, step=5.0):
    """Feed one sample per tick for `seconds`, firing whatever source exists."""
    elapsed = 0.0
    while elapsed < seconds:
        samples.append(ResourceSample(cpu, ram))
        glib.fire(only_source(glib))
        clock.now += step
        elapsed += step


def test_one_five_second_source_while_idle(env):
    buddy, glib, *_ = env
    buddy._ensure_resource_source()
    buddy._ensure_resource_source()
    assert glib.intervals == [5]


def test_start_stop_start_leaves_one_source(env):
    buddy, glib, *_ = env
    buddy._ensure_resource_source()
    buddy._cancel_resource_source()
    buddy._cancel_resource_source()
    buddy._ensure_resource_source()
    assert glib.intervals == [5]


def test_no_source_in_preview_or_while_away_or_after_shutdown(env):
    buddy, glib, *_ = env
    buddy._preview_mode = True
    buddy._ensure_resource_source()
    assert glib.sources == {}
    buddy._preview_mode = False
    buddy._blocked = True
    buddy._ensure_resource_source()
    assert glib.sources == {}
    buddy._blocked = False
    buddy.shutdown_presence()
    buddy._presence_shutting_down = True
    buddy._ensure_resource_source()
    assert glib.sources == {}


def test_sustained_memory_load_announces_once_with_the_number(env):
    buddy, glib, clock, samples = env
    buddy._ensure_resource_source()
    run_load(buddy, glib, clock, samples, cpu=10, ram=92, seconds=120)

    engine = buddy._ambient_presence_engine
    engine.emit.assert_called_once_with("memory_tight", values={"cpu": 10, "ram": 92})
    assert buddy.beats == ["squish"]


def test_announcement_switches_to_one_second_source_then_back(env):
    buddy, glib, clock, samples = env
    buddy._ensure_resource_source()
    run_load(buddy, glib, clock, samples, cpu=10, ram=92, seconds=25)
    assert glib.intervals == [1]  # card wanted: live numbers

    run_load(buddy, glib, clock, samples, cpu=10, ram=92, seconds=10, step=1.0)
    assert buddy._resource_card_remaining == 0
    assert glib.intervals == [5]
    assert buddy._resource_card.active is False


def test_card_countdown_pauses_while_suspended(env):
    buddy, glib, clock, samples = env
    buddy._resource_card_remaining = 8.0
    buddy._resource_last_tick_at = clock.now
    buddy._resource_card.visible = False  # under the speech bubble
    clock.now += 5
    buddy._advance_resource_card(clock.now)
    assert buddy._resource_card_remaining == 8.0
    buddy._resource_card.visible = True
    clock.now += 3
    buddy._advance_resource_card(clock.now)
    assert buddy._resource_card_remaining == 5.0


def test_suppressed_announcement_still_speaks_to_engine_but_no_beat_or_card(env):
    buddy, glib, clock, samples = env
    buddy._suppression = "focus session"
    buddy._announce_resource_edge(ResourceEdge(ResourceLevel.MEMORY_CRITICAL, True, 20, 97), clock.now)

    buddy._ambient_presence_engine.emit.assert_called_once_with(
        "memory_critical", values={"cpu": 20, "ram": 97}
    )
    assert buddy._resource_pending_beat is None
    assert buddy._resource_card_remaining == 0


def test_gate_refusal_does_nothing_visible(env):
    buddy, glib, clock, samples = env
    buddy._resource_gate.should_announce(ResourceLevel.CPU_BUSY, clock.now)  # recent announcement
    buddy._apply_resource_edges([ResourceEdge(ResourceLevel.CPU_BUSY, True, 95, 40)], clock.now + 60)

    buddy._ambient_presence_engine.emit.assert_not_called()
    assert buddy._resource_pending_beat is None


def test_exit_edge_discards_the_queued_line(env):
    buddy, glib, clock, samples = env
    buddy._apply_resource_edges([ResourceEdge(ResourceLevel.CPU_BUSY, False, 20, 40)], clock.now)
    buddy._ambient_presence_engine.discard.assert_called_once_with("cpu_busy")


def test_beat_waits_for_suppression_to_clear_then_expires(env):
    buddy, glib, clock, samples = env
    buddy._resource_pending_beat = ("this_is_fine", clock.now + 30)
    buddy.beat_allowed = False
    buddy._try_resource_beat(clock.now)
    assert buddy._resource_pending_beat is not None
    buddy._try_resource_beat(clock.now + 31)
    assert buddy._resource_pending_beat is None
    assert buddy.beats == []


def test_menu_or_drag_dismisses_an_announcement_card(env):
    buddy, glib, clock, samples = env
    buddy._resource_card_remaining = 8.0
    buddy._suppression = "context menu"
    buddy._refresh_resource_card()
    assert buddy._resource_card_remaining == 0
    assert buddy._resource_card.active is False


def test_hover_shows_card_only_while_a_level_is_active(env):
    buddy, glib, clock, samples = env
    buddy._on_enter(None, 1, 1)
    assert buddy._resource_card.active is False
    assert buddy.calls == ["enter"]
    buddy._on_leave(None)

    buddy._ensure_resource_source()
    run_load(buddy, glib, clock, samples, cpu=10, ram=92, seconds=25)
    buddy._resource_card_remaining = 0
    buddy._refresh_resource_card()
    buddy._on_enter(None, 1, 1)
    assert buddy._resource_card.active is True
    assert buddy._resource_card.model.state_word == "crowded"
    buddy._on_leave(None)
    assert buddy._resource_card.active is False


def test_pin_shows_live_card_and_is_never_saved(env):
    buddy, glib, clock, samples = env
    buddy._config = Mock()
    buddy._ensure_resource_source()
    buddy._toggle_resource_stats()
    assert buddy._resource_pinned is True
    assert buddy._resource_card.active is True
    assert glib.intervals == [1]
    buddy._toggle_resource_stats()
    assert buddy._resource_card.active is False
    assert glib.intervals == [5]
    assert buddy._config.method_calls == []


def test_unreadable_proc_marks_stats_unavailable(env):
    buddy, glib, clock, samples = env
    samples.append(ResourceSample(None, None))
    buddy._resource_sample_once()
    assert buddy._resource_readable is False


def test_session_away_clears_state_and_removes_source(env):
    buddy, glib, clock, samples = env
    buddy._ensure_resource_source()
    run_load(buddy, glib, clock, samples, cpu=10, ram=92, seconds=25)
    buddy._blocked = True
    buddy._on_presence_session_away()

    assert glib.sources == {}
    assert buddy._resource_tracker.active_levels == frozenset()
    buddy._ambient_presence_engine.discard.assert_called_with("memory_tight")
    assert buddy._resource_card.active is False

    buddy._blocked = False
    buddy._on_presence_session_returned()
    assert glib.intervals == [5]


def test_shutdown_is_idempotent_and_destroys_the_card(env):
    buddy, glib, *_ = env
    card = buddy._resource_card
    buddy._ensure_resource_source()
    buddy.shutdown_presence()
    buddy.shutdown_presence()
    assert glib.sources == {}
    assert card.destroyed == 1
    assert buddy.calls == ["shutdown", "shutdown"]


def test_tick_exception_removes_its_source(env):
    buddy, glib, clock, samples = env
    buddy._ensure_resource_source()
    buddy._resource_sampler.sample.side_effect = RuntimeError("weird procfs")
    assert glib.fire(only_source(glib)) is GLib.SOURCE_REMOVE
    assert glib.sources == {}
    assert buddy._resource_source_id is None
    buddy._logger.exception.assert_called_once()


def test_tick_during_shutdown_removes_itself(env):
    buddy, glib, *_ = env
    buddy._ensure_resource_source()
    buddy._presence_shutting_down = True
    assert glib.fire(only_source(glib)) is GLib.SOURCE_REMOVE
    assert buddy._resource_source_id is None


def test_preview_alternates_and_bypasses_the_gate(env):
    buddy, glib, clock, samples = env
    buddy._preview_resource_sense()
    buddy._preview_resource_sense()
    names = [call.args[0] for call in buddy._ambient_presence_engine.emit.call_args_list]
    assert names == ["cpu_busy", "memory_critical"]
    assert buddy._ambient_presence_engine.cooldowns.clear.call_count == 2
    assert buddy._resource_card.model.state_word == "almost full"


def test_hooks_tolerate_objects_built_without_init():
    """Other suites build full buddies with object.__new__ and run the chain."""
    buddy = object.__new__(Harness)
    buddy.calls = []
    buddy._session_blocked = lambda: False
    buddy.shutdown_presence()
    buddy._on_enter(None, 0, 0)
    buddy._on_leave(None)
    buddy._on_presence_session_away()
    buddy._on_presence_session_returned()
    assert buddy.calls == ["shutdown", "enter", "leave", "away", "returned"]


def test_mixin_sits_before_agent_cowork_and_nameplate():
    from mochi.presence.agent_cowork import AgentCoworkMixin
    from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
    from mochi.presence.nameplate_controls import NameplateMixin
    from mochi.presence.terminal_cowork import TerminalCoworkMixin

    for buddy_type in (PresenceBuddy, PresenceX11Buddy):
        mro = buddy_type.__mro__
        assert mro.index(ResourceSenseMixin) + 1 == mro.index(AgentCoworkMixin)
        assert mro.index(AgentCoworkMixin) + 1 == mro.index(TerminalCoworkMixin)
        assert mro.index(ResourceSenseMixin) < mro.index(NameplateMixin)


def test_pinned_card_hides_while_locked_and_returns_after(env):
    buddy, glib, clock, samples = env
    buddy._ensure_resource_source()
    buddy._toggle_resource_stats()
    assert buddy._resource_card.active is True

    buddy._blocked = True
    buddy._on_presence_session_away()
    assert buddy._resource_card.active is False
    assert buddy._resource_pinned is True  # the switch stays on
    assert glib.sources == {}

    buddy._blocked = False
    buddy._on_presence_session_returned()
    assert buddy._resource_card.active is True
    assert glib.intervals == [1]
```

- [ ] **Step 2: Write the failing anchor tests**

Create `tests/test_resource_card_anchor.py`:

```python
"""The resource card's tier in the shared anchor above Mochi."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_nameplate_controls import _FakeBubble, _make_hover_harness, _make_mixin


def _card(*, active: bool, visible: bool):
    return SimpleNamespace(
        active=active, visible=visible, suspend=Mock(), resume=Mock(), update_position=Mock()
    )


def _sync(mixin):
    with patch("mochi.presence.nameplate_controls.time.monotonic", return_value=10.0):
        mixin._sync_nameplate_with_speech()


def test_speech_bubble_suspends_the_card():
    mixin, nameplate = _make_mixin(nameplate_visible=False, bubble=_FakeBubble(visible=True))
    mixin._resource_card = _card(active=True, visible=True)
    _sync(mixin)
    mixin._resource_card.suspend.assert_called_once_with()
    mixin._resource_card.resume.assert_not_called()


def test_bond_progress_outranks_the_card():
    mixin, nameplate = _make_mixin(nameplate_visible=False, bubble=_FakeBubble(visible=False))
    mixin._bond_progress_overlay = _card(active=True, visible=True)
    mixin._resource_card = _card(active=True, visible=True)
    _sync(mixin)
    mixin._resource_card.suspend.assert_called_once_with()
    mixin._bond_progress_overlay.resume.assert_called_once_with()


def test_focus_hint_outranks_the_card():
    mixin, nameplate = _make_mixin(nameplate_visible=False, bubble=_FakeBubble(visible=False))
    mixin._focus_bond_hint_active = lambda: True
    mixin._resource_card = _card(active=True, visible=True)
    _sync(mixin)
    mixin._resource_card.suspend.assert_called_once_with()
    mixin._resource_card.resume.assert_not_called()


def test_active_card_resumes_and_hides_the_nameplate():
    mixin, nameplate = _make_mixin(nameplate_visible=True, bubble=_FakeBubble(visible=False))
    mixin._resource_card = _card(active=True, visible=False)
    _sync(mixin)
    assert nameplate.visible is False
    mixin._resource_card.resume.assert_called_once_with()
    mixin._resource_card.update_position.assert_called_once_with()


def test_card_outranks_hover_nameplate():
    mixin, nameplate = _make_hover_harness(nameplate_visible=False, bubble=_FakeBubble(visible=False))
    mixin._resource_card = _card(active=True, visible=False)
    with patch("mochi.presence.nameplate_controls.time.monotonic", return_value=10.0):
        mixin._on_enter(None, 0.0, 0.0)
    assert nameplate.show_calls == 0
    mixin._resource_card.resume.assert_called_once_with()


def test_inactive_card_leaves_the_nameplate_alone():
    mixin, nameplate = _make_hover_harness(nameplate_visible=False, bubble=_FakeBubble(visible=False))
    mixin._resource_card = _card(active=False, visible=False)
    with patch("mochi.presence.nameplate_controls.time.monotonic", return_value=10.0):
        mixin._on_enter(None, 0.0, 0.0)
    assert nameplate.visible is True
    mixin._resource_card.resume.assert_not_called()
```

- [ ] **Step 3: Run them and see them fail**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_sense_mixin.py tests/test_resource_card_anchor.py 2>&1 | tail -3
```

Expected: the mixin module is missing, and the anchor tests fail because nothing calls `resume()` or `suspend()` on the card.

- [ ] **Step 4: Implement the mixin**

Create `src/mochi/presence/resource_sense.py`:

```python
"""Resource Sense: Mochi notices sustained CPU and memory load.

The pure core (sampling, edges, habituation, card wording) lives in
``mochi.resource_sense``. This mixin owns the GTK-side lifecycle:

- exactly one GLib poll source: 5 s normally, 1 s while the card is wanted,
  none while the session is away, in preview mode, or after shutdown;
- announcements: one engine line (with the measured number), one queued beat
  and a brief card, each behind its own gates;
- the session-only "Computer stats" menu switch and a Mochi Lab preview.

It never claims behavior state. Beats go through ``_play_idle_beat`` and are
gated by ``_curiosity_suppression()``.
"""

from __future__ import annotations

import time

from gi.repository import GLib, Gtk

from mochi.resource_sense import (
    ResourceEdge,
    ResourceLevel,
    ResourcePressureTracker,
    ResourceReactionGate,
    ResourceSample,
    ResourceSampler,
    resource_card_model,
)

from .resource_card import ResourceCard

_BEATS = {
    ResourceLevel.CPU_BUSY: "this_is_fine",
    ResourceLevel.MEMORY_TIGHT: "squish",
    ResourceLevel.MEMORY_CRITICAL: "squish",
}


class ResourceSenseMixin:
    RESOURCE_SAMPLE_SECONDS = 5
    RESOURCE_CARD_SAMPLE_SECONDS = 1
    RESOURCE_CARD_SECONDS = 8.0
    RESOURCE_BEAT_TTL_SECONDS = 30.0

    def __init__(self, *args, **kwargs) -> None:
        self._resource_sampler = ResourceSampler()
        self._resource_tracker = ResourcePressureTracker()
        self._resource_gate = ResourceReactionGate()
        self._resource_source_id: int | None = None
        self._resource_source_interval: int | None = None
        self._resource_last_tick_at: float | None = None
        self._resource_pending_beat: tuple[str, float] | None = None
        self._resource_card: ResourceCard | None = None
        self._resource_card_remaining = 0.0
        self._resource_card_override: tuple[ResourceSample, frozenset[ResourceLevel]] | None = None
        self._resource_pinned = False  # session-only: never saved
        self._resource_hovering = False
        self._resource_readable = True
        self._resource_stats_switch: Gtk.Switch | None = None
        self._resource_stats_label: Gtk.Label | None = None
        self._resource_stats_button: Gtk.Button | None = None
        self._resource_preview_critical = False
        super().__init__(*args, **kwargs)
        window = getattr(self, "_window", None)
        if not getattr(self, "_preview_mode", False) and window is not None:
            self._resource_card = ResourceCard(
                owner=window, anchor_widget=self, logger=getattr(self, "_logger", None)
            )
            self._ensure_resource_source()

    def _resource_inert(self) -> bool:
        """True on objects built without __init__ (tests use object.__new__).

        Cooperative hooks must still pass the call down the chain then, the
        same tolerance the other presence mixins' teardown has.
        """
        return getattr(self, "_resource_tracker", None) is None

    # -- Clock ------------------------------------------------------------------

    def _resource_now(self) -> float:
        """CLOCK_BOOTTIME, like _curiosity_now(): suspended time counts."""
        try:
            return time.clock_gettime(time.CLOCK_BOOTTIME)
        except (AttributeError, OSError):
            return time.monotonic()

    # -- Poll source -------------------------------------------------------------

    def _resource_session_away(self) -> bool:
        session_blocked = getattr(self, "_session_blocked", None)
        return bool(callable(session_blocked) and session_blocked())

    def _resource_wanted_interval(self) -> int | None:
        if getattr(self, "_preview_mode", False):
            return None
        if getattr(self, "_presence_shutting_down", False):
            return None
        if self._resource_session_away():
            return None
        if self._resource_card_wanted():
            return self.RESOURCE_CARD_SAMPLE_SECONDS
        return self.RESOURCE_SAMPLE_SECONDS

    def _ensure_resource_source(self) -> None:
        interval = self._resource_wanted_interval()
        if interval is not None and interval == self._resource_source_interval:
            return
        self._cancel_resource_source()
        if interval is None:
            return
        self._resource_source_id = GLib.timeout_add_seconds(interval, self._resource_tick)
        self._resource_source_interval = interval

    def _cancel_resource_source(self) -> None:
        source_id = getattr(self, "_resource_source_id", None)
        self._resource_source_id = None
        self._resource_source_interval = None
        if source_id is None:
            return
        try:
            GLib.source_remove(source_id)
        except Exception:
            pass

    def _forget_resource_source(self) -> None:
        """The running tick is about to return SOURCE_REMOVE by itself."""
        self._resource_source_id = None
        self._resource_source_interval = None

    def _resource_tick(self) -> bool:
        if getattr(self, "_presence_shutting_down", False):
            self._forget_resource_source()
            return GLib.SOURCE_REMOVE
        interval = self._resource_source_interval
        try:
            self._resource_sample_once()
        except Exception:
            # Never leave a dead source id behind: the next start re-arms.
            self._forget_resource_source()
            logger = getattr(self, "_logger", None)
            if logger is not None:
                logger.exception("[resources] sample failed")
            return GLib.SOURCE_REMOVE
        if self._resource_wanted_interval() != interval:
            # The card appeared or went away: hand over to a source at the
            # new interval. This tick's source removes itself.
            self._forget_resource_source()
            self._ensure_resource_source()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # -- Sampling and edges ------------------------------------------------------

    def _resource_sample_once(self) -> None:
        now = self._resource_now()
        sample = self._resource_sampler.sample()
        readable = sample.ram_percent is not None
        if readable != self._resource_readable:
            self._resource_readable = readable
            self._sync_resource_stats_row()
        self._apply_resource_edges(self._resource_tracker.observe(sample, now), now)
        self._try_resource_beat(now)
        self._advance_resource_card(now)
        self._refresh_resource_card()

    def _apply_resource_edges(self, edges: list[ResourceEdge], now: float) -> None:
        engine = getattr(self, "_ambient_presence_engine", None)
        for edge in edges:
            if not edge.entered:
                if engine is not None:
                    engine.discard(edge.level.value)
                continue
            if self._resource_gate.should_announce(edge.level, now):
                self._announce_resource_edge(edge, now)

    def _announce_resource_edge(self, edge: ResourceEdge, now: float) -> None:
        # Speech always goes to the engine: it owns speech/quiet/idle/menu
        # suppression and the Focus floor (memory_critical passes it).
        engine = getattr(self, "_ambient_presence_engine", None)
        values = {
            key: value
            for key, value in (("cpu", edge.cpu_percent), ("ram", edge.ram_percent))
            if value is not None
        }
        if engine is not None:
            engine.emit(edge.level.value, values=values)
        # Beat and auto card follow curiosity's rules, so Focus, sleep, the
        # menu, drag, quiet mode and ambient-off never get an animation or card.
        if self._curiosity_suppression() is not None:
            return
        self._resource_pending_beat = (_BEATS[edge.level], now + self.RESOURCE_BEAT_TTL_SECONDS)
        self._resource_card_remaining = self.RESOURCE_CARD_SECONDS

    def _try_resource_beat(self, now: float) -> None:
        pending = self._resource_pending_beat
        if pending is None:
            return
        name, expires_at = pending
        if now >= expires_at:
            self._resource_pending_beat = None
            return
        if self._curiosity_suppression() is not None:
            return
        if self._play_idle_beat(name):
            self._resource_pending_beat = None

    # -- Card ------------------------------------------------------------------

    def _resource_card_wanted(self) -> bool:
        if self._resource_session_away():
            return False  # a pinned card waits, hidden, until the user is back
        return (
            self._resource_pinned
            or self._resource_card_remaining > 0
            or (self._resource_hovering and bool(self._resource_tracker.active_levels))
        )

    def _advance_resource_card(self, now: float) -> None:
        """Count down the announcement card only while it is actually shown."""
        last, self._resource_last_tick_at = self._resource_last_tick_at, now
        card = self._resource_card
        if (
            self._resource_card_remaining > 0
            and last is not None
            and card is not None
            and card.visible
        ):
            self._resource_card_remaining = max(0.0, self._resource_card_remaining - (now - last))
        if self._resource_card_remaining <= 0:
            self._resource_card_override = None

    def _refresh_resource_card(self) -> None:
        if self._resource_card_remaining > 0 and self._curiosity_suppression() is not None:
            # An announcement card yields to the menu, drag, Focus, sleep...
            self._resource_card_remaining = 0.0
            self._resource_card_override = None
        card = self._resource_card
        if card is None:
            return
        if not self._resource_card_wanted():
            card.deactivate()
            return
        if self._resource_card_override is not None:
            sample, levels = self._resource_card_override
        else:
            sample = self._resource_tracker.last_sample
            levels = self._resource_tracker.active_levels
        card.show_model(resource_card_model(sample, levels))

    # -- Hover -----------------------------------------------------------------

    def _on_enter(self, controller, x: float, y: float) -> None:
        if self._resource_inert():
            super()._on_enter(controller, x, y)
            return
        # Decide before NameplateMixin resolves the shared anchor in super().
        self._resource_hovering = True
        self._refresh_resource_card()
        self._ensure_resource_source()
        super()._on_enter(controller, x, y)

    def _on_leave(self, controller) -> None:
        if self._resource_inert():
            super()._on_leave(controller)
            return
        self._resource_hovering = False
        self._refresh_resource_card()
        self._ensure_resource_source()
        super()._on_leave(controller)

    # -- Menu ------------------------------------------------------------------

    def _build_context_menu(self):
        popover = super()._build_context_menu()
        row = self._make_resource_stats_row()
        # Sleep -> Edge roam -> Stay put -> Computer stats
        self._register_context_menu_row("resource-stats", row, after="stay-put")
        return popover

    def _make_resource_stats_row(self) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("mochi-menu-row")
        button.set_tooltip_text("Show CPU and memory meters above Mochi until you turn this off")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("utilities-system-monitor-symbolic")
        icon.add_css_class("mochi-menu-icon")
        row.append(icon)
        label = Gtk.Label(label="Computer stats")
        label.set_xalign(0)
        label.set_hexpand(True)
        row.append(label)
        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_active(self._resource_pinned)
        switch.set_can_target(False)
        switch.set_focusable(False)
        row.append(switch)
        button.set_child(row)
        button.connect("clicked", self._toggle_resource_stats)
        self._resource_stats_button = button
        self._resource_stats_label = label
        self._resource_stats_switch = switch
        self._sync_resource_stats_row()
        return button

    def _sync_resource_stats_row(self) -> None:
        if self._resource_stats_button is None:
            return
        self._resource_stats_button.set_sensitive(self._resource_readable)
        self._resource_stats_label.set_label(
            "Computer stats" if self._resource_readable else "Can't read system stats"
        )

    def _toggle_resource_stats(self, _button=None) -> None:
        self._resource_pinned = not self._resource_pinned
        if self._resource_stats_switch is not None:
            self._resource_stats_switch.set_active(self._resource_pinned)
        self._close_context_menu_then(self._apply_resource_pin)

    def _apply_resource_pin(self) -> None:
        if self._resource_pinned:
            self._resource_sample_once()  # numbers now, not in up to 5 s
        self._refresh_resource_card()
        self._ensure_resource_source()

    # -- Mochi Lab preview ----------------------------------------------------------

    def _build_developer_menu(self):
        popover = super()._build_developer_menu()
        button, _label = self._make_menu_button(
            "Preview Resource Sense",
            "utilities-system-monitor-symbolic",
            self._preview_resource_sense,
        )
        self._developer_menu_content.append(button)
        return popover

    def _preview_resource_sense(self, _button=None) -> None:
        """Owner QA: a fake announcement through the real path, gate bypassed."""
        critical = self._resource_preview_critical
        self._resource_preview_critical = not critical
        if critical:
            edge = ResourceEdge(ResourceLevel.MEMORY_CRITICAL, True, 31, 96)
            levels = frozenset({ResourceLevel.MEMORY_TIGHT, ResourceLevel.MEMORY_CRITICAL})
        else:
            edge = ResourceEdge(ResourceLevel.CPU_BUSY, True, 94, 71)
            levels = frozenset({ResourceLevel.CPU_BUSY})
        engine = getattr(self, "_ambient_presence_engine", None)
        if engine is not None:
            engine.cooldowns.clear()
        self._announce_resource_edge(edge, self._resource_now())
        if self._resource_card_remaining > 0:
            self._resource_card_override = (
                ResourceSample(edge.cpu_percent, edge.ram_percent),
                levels,
            )
        self._refresh_resource_card()
        self._ensure_resource_source()

    # -- Session and shutdown ------------------------------------------------------

    def _on_presence_session_away(self) -> None:
        super()._on_presence_session_away()
        if self._resource_inert():
            return
        self._apply_resource_edges(self._resource_tracker.clear(), self._resource_now())
        self._resource_sampler.reset()
        self._resource_pending_beat = None
        self._resource_card_remaining = 0.0
        self._resource_card_override = None
        self._resource_last_tick_at = None
        self._cancel_resource_source()
        self._refresh_resource_card()

    def _on_presence_session_returned(self) -> None:
        super()._on_presence_session_returned()
        if not self._resource_inert():
            self._refresh_resource_card()
            self._ensure_resource_source()

    def shutdown_presence(self) -> None:
        self._cancel_resource_source()
        self._resource_pending_beat = None
        self._resource_card_remaining = 0.0
        self._resource_card_override = None
        self._resource_pinned = False
        card = getattr(self, "_resource_card", None)
        self._resource_card = None
        if card is not None:
            card.destroy()
        super().shutdown_presence()
```

- [ ] **Step 5: Add the anchor tier**

```diff
--- a/src/mochi/presence/nameplate_controls.py
+++ b/src/mochi/presence/nameplate_controls.py
@@ -12,8 +12,8 @@
 The shared surface keeps one priority order while the nameplate itself remains
 ephemeral:

-    speech bubble > bond progress > Focus hint > temporary feedback
-    > hover/post-speech nameplate > hidden
+    speech bubble > bond progress > Focus hint > resource card
+    > temporary feedback > hover/post-speech nameplate > hidden

 It appears while Mochi is hovered, briefly after speech ends, or while short
 care/interaction feedback is active. Fade progression piggybacks on the
@@ -403,6 +403,7 @@
         bubble = getattr(self, "_presence_bubble", None)
         bubble_visible = bool(bubble is not None and bubble.visible)
         bond_overlay = getattr(self, "_bond_progress_overlay", None)
+        resource_card = getattr(self, "_resource_card", None)
         focus_hint_active = False
         focus_hint = getattr(self, "_focus_bond_hint_active", None)
         if callable(focus_hint):
@@ -420,16 +421,20 @@
             )
             self._cancel_nameplate_fade()

-        # Shared anchor priority:
-        # speech > bond progress > Focus hint > feedback > hover/post-speech.
+        # Shared anchor priority: speech > bond progress > Focus hint
+        # > resource card > feedback > hover/post-speech.
         if bubble_visible:
             if bond_overlay is not None and bond_overlay.visible:
                 bond_overlay.suspend()
+            if resource_card is not None and resource_card.visible:
+                resource_card.suspend()
             if nameplate.visible:
                 nameplate.hide()
             return

         if bond_overlay is not None and bond_overlay.active:
+            if resource_card is not None and resource_card.visible:
+                resource_card.suspend()
             if nameplate.visible:
                 nameplate.hide()
             bond_overlay.resume()
@@ -437,10 +442,19 @@
             return

         if focus_hint_active:
+            if resource_card is not None and resource_card.visible:
+                resource_card.suspend()
             if nameplate.visible:
                 nameplate.hide()
             return

+        if resource_card is not None and resource_card.active:
+            if nameplate.visible:
+                nameplate.hide()
+            resource_card.resume()
+            resource_card.update_position()
+            return
+
         if self._nameplate_feedback is not None or getattr(self, "_hovered", False):
             self._show_nameplate_full_opacity()
             return
```

- [ ] **Step 6: Wire the mixin into both buddies**

In `src/mochi/presence/click_dialogue.py`, import `ResourceSenseMixin` from `.resource_sense` and insert it on the line **before** `AgentCoworkMixin,` in both `PresenceBuddy` and `PresenceX11Buddy`:

```
    FedoraModeMixin,
    ResourceSenseMixin,
    AgentCoworkMixin,
    TerminalCoworkMixin,
```

- [ ] **Step 7: Run the new tests, the neighbours, and the full suite**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider tests/test_resource_sense_mixin.py tests/test_resource_card_anchor.py tests/test_nameplate_controls.py tests/test_context_menu_layout.py tests/test_agent_cowork.py 2>&1 | tail -3
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
```

Expected: all pass. In the planning run the mixin (22) and anchor (6) tests passed, and the full suite reached 1433.

- [ ] **Step 8: Commit**

```bash
git add src/mochi/presence/resource_sense.py src/mochi/presence/nameplate_controls.py src/mochi/presence/click_dialogue.py tests/test_resource_sense_mixin.py tests/test_resource_card_anchor.py
git commit -m "feat: Mochi notices sustained CPU and memory load"
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
- README lists Resource Sense with the AmbiSense features and *Computer stats* in the controls section.
- `docs/ambisense.md` names the two files read, says "aggregate only", and states the poll rules.
- CODEBASE_MANUAL §6 layer list includes `ResourceSenseMixin`.
- REGRESSION_WATCHLIST has the spec's **Resource Sense** section verbatim.
- `git diff --check` is clean.

- [ ] **Step 1: CHANGELOG**

Under `## Unreleased` → `### Added`:

```markdown
- Mochi now notices when your computer is working hard. After a minute or so
  of sustained high CPU, or when memory gets tight, Mochi says so with the
  number attached, plays a little reaction, and briefly shows CPU and RAM
  meters. Hover Mochi while things are busy to see the meters again, or turn
  on "Computer stats" in the menu to keep them up for the session. Mochi only
  reads overall CPU and memory use, never which programs are running.
```

- [ ] **Step 2: README, ambisense.md, manual, watchlist**

Make the changes listed in the acceptance criteria. Copy the watchlist items from the spec's Documentation section.

- [ ] **Step 3: Commit**

```bash
git diff --check && git add -A CHANGELOG.md README.md docs/ambisense.md docs/CODEBASE_MANUAL.md REGRESSION_WATCHLIST.md
git commit -m "docs: document Resource Sense and add its QA checklist"
```

---

### Task 7: Final verification, push and draft PR

**Files:** none.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: the pushed branch and a draft PR against `main`.

**Acceptance Criteria:**
- Full suite, `compileall`, `bash -n install.sh` and `git diff --check` all pass locally.
- A headless smoke of the real app shows one announcement for injected load, then a clean shutdown.
- The PR body follows `.github/pull_request_template.md` and lists the owner's manual QA steps.

- [ ] **Step 1: Run CI's checks locally**

```bash
PYTHONPATH=src xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider 2>&1 | tail -3
python3.12 -m compileall -q src && echo "compileall ok"
bash -n install.sh && echo "install.sh ok"
git diff --check origin/main...HEAD && echo "whitespace ok"
```

- [ ] **Step 2: Review the diff adversarially**

```bash
git diff origin/main...HEAD -- src
```

Check specifically:
- the only paths opened are `PROC_STAT` and `PROC_MEMINFO`;
- nothing calls `ConfigStore` for Resource Sense;
- every `GLib.timeout_add_seconds` in `presence/resource_sense.py` is matched by `_cancel_resource_source` or `_forget_resource_source`;
- no resource text reaches a `markup=` argument;
- the card's widgets, window and popover all have targeting and focus off.

- [ ] **Step 3: Smoke the real app headless (not committed)**

Start Mochi under `xvfb-run` and `dbus-run-session` with isolated XDG directories, as the curiosity plan's Task 7 did. Replace `buddy._resource_sampler.sample` with a function returning `ResourceSample(10, 96)`, advance `_resource_now` past the dwell, and confirm: one `memory_critical` engine event with `values={"cpu": 10, "ram": 96}`, a `squish` beat, the card active, state still `IDLE`, then a clean shutdown with no traceback.

- [ ] **Step 4: Push and open a draft PR**

```bash
git push -u origin claude/resource-sense
```

PR body sections: Summary, Scope, Verification (actual counts), Runtime / lifecycle notes (one poll source, edges only, shared anchor tier), Environment tested (headless only), Notes (owner QA: `stress-ng --cpu 0 --timeout 120s`, the Mochi Lab preview button, and the watchlist section).

---

## Stress Test Results: Implementation Plan

### Resolved Decisions

- **Prototype before plan:** Tasks 2–5 were run against a scratch copy of `main` while writing this plan, so their code and expected counts are evidence rather than guesses.
- **Pinned card during a lock** (found while reviewing the spec against the code): the pin kept the card wanted while the session was away. `_resource_card_wanted()` is now false while away, and returning refreshes the card; a test pins it.
- **Card width** (found by building it): the GTK theme's progress-bar trough minimum (about 150 px) made the first card 267 px wide; `min-width: 96px` on the trough brings it to the mockup's 210 px.
- **Top edge** (found by reading the bond card): `BondProgressOverlay` clamps to the top, which would cover Mochi; the card uses the bubble's above-else-below rule instead, as a pure, tested `card_position()`.
- **Template anti-repeat** (found during prototyping): without it, filled-in numbers would make every resource line look new to `PhraseBank`.
- **Speech vs. beat suppression:** the mixin always emits to the engine, because the engine owns speech suppression and the Focus floor, while beats and auto cards follow curiosity suppression. A test pins both halves.
- **No config change:** the menu switch is session-only, and a test asserts the config store is never called.
- **Composition vs. mixin:** a mixin, like `AgentCoworkMixin`, because every entry point is a cooperative chain hook and it never claims behavior state.
- **Mixin placement and half-built objects** (found by dry-running this plan on a clean checkout): "after `AgentCoworkMixin`" broke `test_agent_cowork_sits_right_before_terminal_cowork`, and the agent suite's `object.__new__` buddies reached `shutdown_presence` without Resource Sense state. The mixin now goes before `AgentCoworkMixin`, its hooks pass straight through when uninitialized, and two tests pin both.

### Changes Made

- Dropped the persisted "Notice system load" toggle; see the spec's Changes Made.
- Dropped the planned `buddy.py` menu-height change; unknown rows already get a height increment.

### Deferred / Parking Lot

- Extracting the shared anchored-overlay positioning helper (Task 4 makes it the fourth copy).

### Confidence Assessment

- **High** for Tasks 2–5: every code block in them was run, alone and against the full suite.
- **Medium** for live behavior, which only a GNOME session can show.
- Areas of concern: the feel of "line, then meters" on XWayland, and threshold tuning on real workloads. Both need owner QA.
