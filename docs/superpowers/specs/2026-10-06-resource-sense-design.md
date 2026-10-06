# Resource Sense — Design

**Date:** 2026-10-06

**Builds on:** AmbiSense system signals (`UPowerSignalAdapter`, `presence/signals.py`), the Agent Companion's on-demand poll source (`presence/agent_cowork.py`), and Active Window Curiosity's suppression and habituation (`presence/curiosity.py`)

**Status:** proposed, awaiting owner approval. Implementation plan: `docs/superpowers/plans/2026-10-06-resource-sense.md`. Mockup: `docs/design/resource-sense/`. No runtime code exists yet.

## Purpose

Mochi should notice when the computer is struggling: a build pinning every core for a minute, or memory filling up until the desktop starts to stutter. When that happens Mochi says so in character, with the number attached ("It's getting crowded in here… (RAM 91%)"), plays an animation that already exists, and briefly shows two small meters. When the load passes, Mochi goes back to normal and nothing stays on screen.

The idea comes from the OpenPets "System Resources" plugin, which pins live CPU/RAM meters under the pet and announces numbers ("RAM usage is at 90 percent"). Mochi keeps the useful part, a timely heads-up with a real number, and drops the always-on meter panel. See [Fit with the project philosophy](#fit-with-the-project-philosophy).

## Goals

- Notice **sustained** high CPU and high or critical RAM, never short spikes.
- React once per episode: one line, one beat, one brief card. Repeated samples of an ongoing episode never re-trigger.
- Let the owner check on demand from the context menu, and see meters when hovering Mochi while the machine is under load.
- Read only two aggregate procfs files. No per-process data, no process names, no new dependencies.
- Respect every existing quieting rule: speech enabled, ambient reactions, quiet mode, Focus, sleep, menu, drag.
- Settle down on machines that live near a threshold (habituation).
- Degrade silently when `/proc` is unreadable.

## Non-goals

- Disk, temperature, GPU, swap, or network throughput. These are deferred; see the parking lot.
- Battery. `UPowerSignalAdapter` already covers low battery and charging (`presence/signals.py:110-204`, `engine.py:118-119`).
- Naming *what* is using the CPU or memory. A per-process list would read command lines and process names, which the Agent Companion spec already rejected as privacy-adjacent (`docs/superpowers/specs/2026-10-05-agent-companion-design.md:204`).
- Advice. Mochi never says "close some apps".
- A persisted on/off setting. Quiet mode and Ambient reactions already opt out, the same decision Active Window Curiosity made (`docs/superpowers/specs/2026-10-05-active-window-curiosity-design.md:29`).
- New animation assets. The beats reuse `this_is_fine` and `squish`.

## Fit with the project philosophy

`docs/wiki/Project-Philosophy.md:13-15` lists "a system-monitor panel" first among the things Mochi must not become. This feature is close to that line, so the design stays on the right side of it deliberately:

- The philosophy's own authority order (`Project-Philosophy.md:253-262`) puts an explicit owner requirement above the philosophy, and the owner asked for this feature.
- §15 (`Project-Philosophy.md:197-201`) asks for "contextual UI that appears when useful and disappears cleanly". That is the display model here: nothing is visible by default, the card appears at a moment that justifies it, and it hides again.
- The only way to keep meters up is a context-menu switch that is **session-only**. It resets when Mochi restarts, so a dashboard can never become the default by accident.
- Mochi *feels* the load first (a line and an animation) and shows numbers second.

## Behavior

### What is measured

| Metric | Source | Formula |
|---|---|---|
| CPU % | `/proc/stat`, first line (`cpu ...`) | `1 − Δ(idle + iowait) / Δtotal` between two samples, over the first eight columns (guest time is already inside user/nice). Smoothed with an exponential moving average, α = 0.3. |
| RAM % | `/proc/meminfo` | `1 − MemAvailable / MemTotal`, raw. Memory moves slowly enough that it needs no smoothing. |

A reading that fails or cannot be computed is `None` ("can't tell"), never 0. The first sample after start or resume has no CPU value, because it needs a delta.

### Triggers

| Level | Enter when | …for at least | Exit when | …for at least | Speech priority |
|---|---|---|---|---|---|
| `cpu_busy` | smoothed CPU ≥ 85 % | 45 s | < 60 % | 30 s | 30 (silent during Focus) |
| `memory_tight` | RAM ≥ 90 % | 20 s | < 80 % | 30 s | 30 (silent during Focus) |
| `memory_critical` | RAM ≥ 95 % | 10 s | < 90 % | immediately | 40 (passes the Focus floor, `focus_session.py:26`) |

The gap between the enter and exit thresholds is hysteresis: a machine hovering around 85 % CPU cannot flap in and out. Starting from idle, a build at 100 % takes about 30 s to push the smoothed value past 85 %, plus the 45 s dwell, so Mochi reacts after roughly 75 s of sustained load. A `None` reading holds the current state and restarts any pending dwell.

Only edges matter. While a level stays active, further samples produce nothing (Manual Recipe B, `docs/CODEBASE_MANUAL.md:1680-1700`).

### Reaction ladder

When a level **enters**, the reaction gate (see Habituation) decides whether Mochi *announces* it. An announcement is one unit with three parts, each with its own gates:

1. **Speech.** `PresenceEngine.emit(level, values={"cpu": …, "ram": …})`. The engine applies its normal suppression, cooldowns and Focus floor. The line names the number Mochi measured at the edge.
2. **Beat.** `this_is_fine` for `cpu_busy`, `squish` for either memory level, played through `IdleLookMixin._play_idle_beat` (`presence/idle_look.py:91-112`) and only when `_curiosity_suppression()` returns `None` (`presence/curiosity.py:140-175`). The latest requested beat wins and expires after 30 s, which is the Agent Companion's beat queue (`agent_cowork.py:179-198`). The beat never changes `MochiState` and never wakes Mochi.
3. **Card.** The resource card becomes active for 8 s of *visible* time. Under the speech bubble it waits, suspended, so the meters appear as the line ends (see [The card](#the-card)).

When a level **exits**, Mochi discards any still-queued line for it (`engine.discard`, `engine.py:253`). The card, if visible, updates its state word. Nothing else happens: recovering never gets a line of its own.

Speech lines, all plain text and never passed to `markup=`:

| Level | Lines |
|---|---|
| `cpu_busy` | "Whew, the computer's thinking really hard… (CPU {cpu}%)" · "Is it warm in here? (CPU {cpu}%)" · "Something's keeping the computer busy. (CPU {cpu}%)" |
| `memory_tight` | "It's getting crowded in here… (RAM {ram}%)" · "Scootching over to make room. (RAM {ram}%)" · "Lots of things open today! (RAM {ram}%)" |
| `memory_critical` | "Squished! Memory's almost full. (RAM {ram}%)" · "No room left to wiggle… (RAM {ram}%)" |

### Habituation

A developer machine runs builds all day, and a browser-heavy laptop may sit at 90 % RAM for hours. `ResourceReactionGate` keeps one clock shared by all three levels:

- The first enter edge is announced.
- Each later announcement waits `min(20 min × 1.5^(n−1), 2 h)` after the previous one, where `n` is the number of announcements so far: 20 min, 30 min, 45 min, …, capped at 2 h. This is the curiosity curve (`curiosity.py:88-93`) with longer bases.
- One hour without any enter edge resets the streak.
- **Escalation:** `memory_critical` may announce inside the cooldown once, unless the previous announcement was already critical. Running out of memory deserves a line even ten minutes after "it's getting crowded".

An enter edge the gate refuses still updates the tracker, so hover and the menu show the right state. The engine's own `resources` category cooldown (20 min, shared with battery and network through `system_event_cooldown_seconds`) remains a floor underneath.

All timing uses `CLOCK_BOOTTIME`, falling back to `time.monotonic()`, like `_curiosity_now()` (`curiosity.py:84`). Suspended time counts, so a long sleep resets habituation.

### The card

The card is a small, non-interactive surface built the same way as the bond-progress card (`presence/bond_progress_overlay.py`): a transient X11 window on XWayland and a popover on pure Wayland, `set_can_target(False)` everywhere, and the same interface (`active`, `visible`, `suspend()`, `resume()`, `update_position()`, `destroy()`) plus `show_model()` and `deactivate()`. It has no timers of its own: the mixin's poll tick counts down its lifetime.

**Contents** (mockup: `docs/design/resource-sense/mockup-light.png`):

```
╭──────────────────────────────╮
│ Computer                busy │   11 px / 700 title, state word on the right
│ CPU ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░   94%   │   7 px rounded bars
│ RAM ▓▓▓▓▓▓▓▓▓▓░░░░░░░   71%   │
╰───────────────▾──────────────╯
```

- The state word is the most severe active level: "almost full" (critical) › "crowded" (tight) › "busy" (CPU) › "calm".
- Bar colour follows the level, not the raw number, so it matches what Mochi said: calm `#79c98b` (Mochi's accent), busy or tight amber `#e5a50a`, critical coral `#e66a5c` plus a "!" before the value ("! 96%"). Numbers and the state word are always text in the theme foreground, so colour is never the only signal.
- The state word uses the full theme foreground at 10 px / 600. The bond card's secondary style (foreground at 0.62 alpha) measures about 3.8:1 on the light theme, which fails WCAG AA for small text; the mockup's contrast check caught this. The same finding applies to the existing bond card and menu subtitle and is noted in the parking lot rather than fixed here.
- Styling copies the bond card's runtime CSS (`bond_progress_overlay.py:752-836`): `alpha(@theme_bg_color, 0.97)`, a 1 px `alpha(#79c98b, 0.44)` border, 11 px radius, and a soft shadow. Light and dark mode come from the theme colours. It does **not** use the historical Figma cream/plum tokens in `docs/design/figma/`, which no runtime surface uses.
- Numbers refresh every second while the card is visible. CPU shows the smoothed value.

**Shared anchor.** The card takes a new tier in `NameplateMixin._sync_nameplate_with_speech` (`presence/nameplate_controls.py:423-460`):

    speech bubble > bond progress > Focus hint > resource card > feedback > hover/post-speech nameplate

A visible bubble suspends the card exactly as it suspends the bond overlay, which is how an announcement reads "line first, meters second". The 8 s lifetime only counts down while the card is actually visible.

**When it is active:**

1. **After an announcement**, for 8 s of visible time.
2. **On hover while any level is active.** Hovering Mochi shows the card instead of the "Mochi" nameplate. This is the contextual part: a calm machine shows the normal nameplate on hover.
3. **While "Computer stats" is on.** A new context-menu switch row, *Computer stats* (row id `resource-stats`, placed after *Stay put*), pins the card with live numbers. The switch is session-only: it is not saved and starts off at every launch.

When `/proc` cannot be read, the menu row shows "Can't read system stats" and the switch is insensitive.

### Suppression

- **Beats and auto cards** are suppressed by everything that silences curiosity: preview mode, shutdown, user idle, an open context menu, a press or drag, Focus work or thinking, a non-`NORMAL` presentation state, sleeping or waking, ambient reactions off, and quiet mode. `_curiosity_suppression()` is reused rather than copied.
- **Speech** always goes to the engine, which applies its own overlapping rules (`speech_enabled`, ambient reactions, quiet mode, user idle, menu, interaction, sleeping states, a recently dismissed bubble, the media quiet bias; `engine.py:530-558`), its global and category cooldowns, the hourly cap, and, at display time, the Focus floor.
- `memory_critical` speech passes the Focus floor, but its beat and auto card still follow curiosity suppression, so Focus never gets an animation or a card.
- Hover and the *Computer stats* switch are direct interaction. Quiet mode does not block them.
- A suppressed beat or auto card is dropped, not queued, and an engine line waits at most its 30 s TTL. Either way the announcement counts for habituation, so Mochi does not bring it up the moment quiet mode ends.

### Interruption and recovery

- **Press or drag during a beat:** the existing idle-look cancellation restores idle. The card is non-targetable and never intercepts input.
- **Menu opened while the card is up:** the auto card is dismissed and a pinned card stays. Context menu and card never compete for focus because the card cannot take it (`presence/nameplate.py:9-14` explains why an interactive overlay once caused freezes).
- **Session away (lock or suspend):** sampling stops, the tracker clears, queued resource lines are dropped through `note_session_away()`'s environmental set, and the card deactivates. On return, sampling restarts with a fresh baseline and no line about the time away.
- **Size change or drag:** the card repositions on the same hooks as the nameplate (`nameplate_controls.py:478-486`).

## Signals and privacy

### What crosses into Mochi

Two integers per sample: aggregate CPU % and RAM %. Mochi reads `/proc/stat`'s first line and `/proc/meminfo`'s `MemTotal` and `MemAvailable`. It reads no per-CPU lines, no `/proc/<pid>`, no process names, command lines, window titles or file names. Nothing is logged above debug level, stored, or sent anywhere.

### Why a poll is acceptable here

Every existing AmbiSense system signal is event-driven over D-Bus. Load has no such event, so this feature polls, under these rules:

- **One source**, owned by `ResourceSenseMixin` and re-armed only when its interval changes: every 5 s normally, every 1 s while the card is wanted (announced, hovered under load, or pinned).
- **No source** while the session is away, in preview mode, or after shutdown. The pattern is `_ensure_agent_source` / `_agent_tick` (`agent_cowork.py:208-235`): a tick that raises removes itself and leaves no dead source id, and the next start re-arms it.
- Each 5 s sample is two small file reads, which costs far less than Mochi's existing 16 ms animation tick.

### Rejected alternatives

| Alternative | Why not |
|---|---|
| `psutil` | A new runtime dependency (`pyproject.toml` has `dependencies = []`, AGENTS.md:23) for two numbers the stdlib reads in a few lines. |
| A "top processes" list | Reads process names and command lines, against the AmbiSense boundary and the Agent Companion spec's explicit rejection. |
| Always-on meter panel (OpenPets-style) | The one thing the philosophy names first. The session-only switch covers people who want meters for a while. |
| Polling every second all the time | No benefit for edges measured in tens of seconds. 1 s is used only while numbers are on screen. |
| Load average (`os.getloadavg`) | Counts runnable and uninterruptible tasks, not CPU use, and needs a core count to interpret. Percentages are what people expect. |
| Showing numbers in the nameplate text | Smallest change, but a text capsule cannot show bars, and the nameplate's feedback slot is shared with care feedback. |
| Systemd-oomd / PSI pressure files | Better at "about to stall" signals, but not every kernel exposes `/proc/pressure`, and the numbers are harder to explain in a speech line. Kept in the parking lot. |

## Architecture

```
/proc/stat, /proc/meminfo
        │  two reads per sample
        ▼
resource_sense.py   ResourceSampler ──► ResourceSample(cpu %, ram %)          (GTK-free)
                    ResourcePressureTracker ──► [ResourceEdge] enter/exit only
                    ResourceReactionGate ──► announce? (habituation, escalation)
                    resource_card_model() ──► rows + state word for the card
        ▼
presence/resource_sense.py   ResourceSenseMixin                               (GTK side)
   ├─ one GLib source: 5 s, or 1 s while the card is visible
   ├─ enter + announce → engine.emit(level, values=…)        ──► engine.py / phrases.py
   │                   → queued beat via _play_idle_beat     ──► idle_look.py
   │                   → card lifetime = 8 s of visible time ──► resource_card.py
   ├─ exit             → engine.discard(level), card state refresh
   ├─ hover while active / "Computer stats" switch → card active
   └─ session away / shutdown → tracker.clear(), source removed, card destroyed
        ▼
presence/nameplate_controls.py   shared-anchor tier: speech › bond › Focus hint › card › …
```

### `src/mochi/resource_sense.py` (new, GTK-free)

`ResourceSampler(read_text=...)`, `ResourcePressureTracker(rules=...)`, `ResourceReactionGate`, `habituated_cooldown()`, `ResourceLevel`, `ResourceSample`, `ResourceEdge`, and a pure `resource_card_model(sample, active_levels)` that returns the rows, tones, badge and state word, so the card's wording is testable without GTK. The sampler takes an injected `read_text` and the tracker takes explicit `now` values, following the injection style of `presence/signals.py`.

| Constant | Value |
|---|---|
| `CPU_SMOOTHING_ALPHA` | 0.3 |
| `cpu_busy` rule | enter ≥ 85 for 45 s, exit < 60 for 30 s |
| `memory_tight` rule | enter ≥ 90 for 20 s, exit < 80 for 30 s |
| `memory_critical` rule | enter ≥ 95 for 10 s, exit < 90 immediately |
| `ResourceReactionGate.BASE_SECONDS` | 1200.0 |
| `ResourceReactionGate.CAP_SECONDS` | 7200.0 |
| `ResourceReactionGate.STREAK_RESET_SECONDS` | 3600.0 |
| `habituated_cooldown` factor / exponent clamp | 1.5 / 16 |

`habituated_cooldown` repeats curiosity's three-line formula instead of importing it, because `curiosity.py` is a GTK-side mixin and this module must import without GTK.

### `src/mochi/presence/engine.py` and `phrases.py`

- `emit(name, *, now=None, values: Mapping[str, int] | None = None)`. Values are stored on the queued event as a sorted tuple.
- When a queued event has values, `_evaluate_events` formats the chosen phrase with `str.format_map`. A template that does not format is logged at debug level and skipped. Events without values are unchanged.
- `PresenceAction` gains `template: str | None = None`, and `record_delivered` remembers `action.template or action.text`, so anti-repeat compares lines rather than lines-with-numbers.
- `cpu_busy` / `memory_tight` / `memory_critical` are added to `_EVENT_PRIORITY` (30 / 30 / 40), `_EVENT_CATEGORY` (`resources`), `_EVENT_TTL_SECONDS` (30 s each), `note_session_away()`'s environmental set, `_category_cooldown` (with battery and network), and `_event_probability` (`system_event_probability`).
- `EVENT_PHRASES` gains the three line sets above.

This change was prototyped against `main` @ `4713426`: the existing engine tests and the whole suite pass with it.

### `src/mochi/presence/resource_sense.py` (new, `ResourceSenseMixin`)

A cooperative mixin, like `AgentCoworkMixin`, because its entry points are all chain hooks (`_build_context_menu`, `_build_developer_menu`, `_on_enter` / `_on_leave`, `_on_presence_session_away` / `_returned`, `shutdown_presence`). It owns the sampler, tracker, gate, the single poll source, the pending beat and the card. It never claims behavior state.

Mochi Lab gains one button, **Preview Resource Sense**. Each press alternates between a fake `cpu_busy` and a fake `memory_critical` announcement through the real path, bypassing the gate and clearing the engine's cooldowns first, the way a test tool should. The card shows the fake numbers for its 8 s. It exists so the owner can QA the feel without filling 95 % of RAM.

### `src/mochi/presence/resource_card.py` (new, `ResourceCard`)

The card surface described above, about 210×84 px including its shadow margins (measured headless; the GTK theme's 150 px progress-bar minimum is overridden to get there). Positioning repeats the X11 and Wayland anchor code that `nameplate.py`, `bond_progress_overlay.py` and `bubble.py` each already carry, which makes this the fourth copy. One deliberate difference from the bond card: near the top of a monitor the bond card clamps and would cover Mochi, so the card uses the bubble's above-else-below rule (`bubble.py:516-521`) through a pure, tested `card_position()`. Extracting a shared helper is a separate refactor and is listed in the parking lot rather than folded in here (AGENTS.md: no drive-by refactors).

### `src/mochi/presence/nameplate_controls.py`

One new tier in `_sync_nameplate_with_speech`, between the Focus hint and feedback. The bubble branch also suspends the card.

### `src/mochi/presence/click_dialogue.py`

Insert `ResourceSenseMixin` immediately before `AgentCoworkMixin` in both `PresenceBuddy` and `PresenceX11Buddy`. It cannot go after it, because `tests/test_agent_cowork.py:358-362` pins `AgentCoworkMixin` directly before `TerminalCoworkMixin`. It must precede `NameplateMixin` so its hover override runs before the shared anchor is resolved. Like the other presence mixins, its hooks pass straight through on objects built without `__init__`, which other suites use.

## Edge cases

| Case | Handling |
|---|---|
| `/proc` unreadable (sandbox, hardened kernel) | Samples are `None`; no edges; the menu row says "Can't read system stats". |
| First sample after start or resume | No CPU value until the second sample. |
| CPU counters go backwards (CPU hot-unplug, counter reset) | That sample's CPU is `None`; the next pair is normal. |
| Kernel without `MemAvailable` (older than 3.14) | RAM is `None`. Fedora always has it. |
| Both memory levels enter within seconds | Critical announces; the gate then refuses tight because it is inside the cooldown and escalation only applies to critical. One line, one beat. |
| Machine idles at 92 % RAM all day | One announcement per episode. Hover shows meters; nothing else repeats. |
| Load starts while Mochi sleeps | Announcement suppressed and counted; tracker state stays correct for hover after waking. |
| Quiet mode on | No line, beat or auto card. Hover and the switch still work. |
| Card visible and the bubble appears | Card suspends, then resumes; its 8 s countdown pauses meanwhile. |
| Mochi near the top of a monitor | Card goes below Mochi instead of covering it, then clamps to the monitor edges. |
| Card pinned and the session locks | Card hides and the switch stays on; numbers resume after unlock. |
| Shutdown during a sample | `_presence_shutting_down` guard, source removed in `shutdown_presence()`, card destroyed. |
| Tick raises (unexpected procfs format) | Logged once, source removed, re-armed on the next start or session return. |
| Wall-clock change | `CLOCK_BOOTTIME` is unaffected. |

## Testing

Run with `PYTHONPATH=src xvfb-run -a python3 -m pytest -q`. CI is the authoritative gate.

1. **Sampler** (`tests/test_resource_sense.py`, fake procfs): first sample has no CPU; CPU is the busy share of the delta; iowait counts as idle; RAM uses `MemAvailable`; unreadable files are `None`, not 0; an unreadable stat resets the baseline; counter wrap is `None`; malformed meminfo is `None`; `reset()` forgets the baseline; exactly the two aggregate files are read.
2. **Tracker:** sustained load enters at the right time; a short spike does not; repeated samples produce one edge; exit needs both hysteresis and dwell; memory escalates and recovers in the right order; `None` holds state and restarts dwell; edges carry display numbers; `clear()` reports active levels as ended, once.
3. **Gate:** the cooldown curve matches curiosity's; first-then-cooldown; growth per announcement; critical escalates once; a quiet hour resets the streak.
4. **Card model:** state word priority; tones per level; "!" only for critical; `None` values render as "–".
5. **Engine** (`tests/test_resource_engine_events.py`): the line carries the measured number; templates use only `{cpu}` / `{ram}`; anti-repeat stores the template; the Focus floor split (30/30/40); 30 s expiry; session away drops lines; shared `resources` cooldown; quiet mode silences them; events without values are unchanged.
6. **Mixin** (`tests/test_resource_sense_mixin.py`, fake bases like `tests/test_idle_beats.py`): MRO placement; hooks pass through on half-built objects; one source at a time; the interval switches between 5 s and 1 s; start → stop → start leaves one source; enter + announce emits, queues the beat and activates the card; a refused announcement does none of that; exit discards; suppression drops beats but keeps tracking; session away clears and removes the source, and a pinned card hides until the user returns; shutdown is idempotent; a tick exception removes the source; hover while active selects the card; the switch is session-only.
7. **Anchor** (`tests/test_resource_card_anchor.py`, reusing the `tests/test_nameplate_controls.py` harness): the bubble suspends the card; bond progress and the Focus hint outrank it; an active card resumes and hides the nameplate; it outranks the hover nameplate; an inactive card changes nothing.
8. **Card surface** (`tests/test_resource_card.py`, `object.__new__` harness like `tests/test_bond_progress_overlay.py`): `show_model` writes both copies (window and popover); tone classes swap cleanly; `suspend`/`resume`/`deactivate`/`destroy` behave like the bond card's; placement goes below Mochi near the top edge and clamps to the monitor; the CSS keeps the state word at full foreground. `tests/test_theme_colors.py` and `tests/test_context_menu_layout.py` already cover theme colours and row registration for every module.

Prototype status: all eight groups (79 tests) were written and run against `main` @ `4713426`, and the plan's code blocks were applied to a clean checkout: the suite goes from 1354 to 1433 passed with nothing else changed. See the plan's Verified facts.

## Documentation

- `CHANGELOG.md` Unreleased → Added: one plain-language entry.
- `README.md`: the feature in the AmbiSense list and *Computer stats* in the controls section.
- `docs/ambisense.md`: CPU and RAM under Signals; under Privacy, the two files read, "aggregate only", and the poll rules.
- `docs/CODEBASE_MANUAL.md` §6: add `ResourceSenseMixin` to the layer list.
- `REGRESSION_WATCHLIST.md`, new **Resource Sense** section:
  - [ ] A 30 s CPU spike causes nothing; a sustained build gets one line, one `this_is_fine` beat and the card after the line
  - [ ] RAM above 95 % speaks once even during Focus, with no beat or card until Focus ends
  - [ ] Quiet mode / ambient reactions off: no line, beat or auto card; hover and *Computer stats* still work
  - [ ] Hovering Mochi on a calm machine shows the nameplate; under load it shows the card
  - [ ] The card never blocks click, drag or right-click, and never stays stuck visible after drag/size changes
  - [ ] *Computer stats* is off again after restarting Mochi
  - [ ] Lock → unlock during load: no line about the time away; the card resumes only if pinned
  - [ ] Card legible in light and dark themes at 64, 112 and 256 px

## Delivery

- This spec, the plan and the mockup ship as a docs-only draft PR from `claude/resource-sense-design`.
- After approval, implementation happens on a new branch from `main` following the plan, test-first, as one reviewable PR.
- Live verification on Fedora / GNOME / Wayland (XWayland) by the owner before merge. Generating load for QA: `stress-ng --cpu 0 --timeout 120s` for CPU; the Mochi Lab preview button for memory.

## Risks

- **Thresholds are guesses until lived with.** 85/90/95 % and the dwell times are one constants table. Owner QA may move them.
- **zram on Fedora.** Compressed swap keeps the desktop responsive at higher RAM % than older setups, so 90 % may feel early. `MemAvailable` already accounts for reclaimable cache, which helps.
- **Smoothed CPU vs. what `top` shows.** The spoken number is the smoothed value, so it can differ from a tool's instantaneous reading by a few points. This is acceptable for a companion's remark.
- **A fourth copy of the anchor-positioning code** raises the cost of the eventual refactor slightly.
- **The card on pure Wayland** uses the popover path, which, like the bond card, has less real-world testing than XWayland.

## Stress Test Results: Resource Sense

### Resolved Decisions

- **Scope (owner, 2026-10-06):** CPU + RAM only; battery already exists; disk, temperature and GPU deferred.
- **Display (owner):** contextual + on demand, never a persistent panel; session-only pin.
- **Voice (owner):** in-character line with the number.
- **Philosophy tension:** addressed explicitly through the authority order and §15, with no persisted panel.
- **Privacy:** aggregate numbers only, two files, enforced by a test on the files read.
- **Poll justification:** one owned source, 5 s / 1 s, none while away; the agent poll pattern.
- **Anti-repeat with numbers (found during prototyping):** remembering filled-in text would never match, so `PresenceAction.template` is remembered instead.
- **Flapping near thresholds:** hysteresis plus dwell in the tracker, and habituation in the gate.

### Changes Made

- **Dropped the planned persisted "Notice system load" toggle.** While writing this spec it turned out that Mochi Lab's AmbiSense switches (Speech bubbles, Ambient reactions, Quiet mode) are session-only developer controls (`presence/integration.py:197-219`, nothing in `config.py`). A persisted setting there would be the odd one out, and curiosity's precedent is "no new toggle". It is replaced by the Lab preview button and is listed in the parking lot.
- **No `buddy.py` change for the menu row:** unknown rows already get a central 44 px height increment (`buddy_menu.py:110-116`).
- **Escalation rule** added so critical memory is never swallowed by a recent "crowded" line.

### Deferred / Parking Lot

- A persisted opt-out specific to Resource Sense, if QA shows people want resource lines off but other ambient reactions on.
- Disk free space (`os.statvfs`), CPU temperature (`/sys/class/thermal`, hwmon), AMD GPU busy (`/sys/class/drm/*/device/gpu_busy_percent`). NVIDIA needs `nvidia-smi` and is out.
- PSI (`/proc/pressure/memory`) as a better "about to stall" signal where available.
- Extracting the shared anchored-overlay positioning helper used by the nameplate, bond card, bubble and this card.
- A dedicated "overheated" animation, if new art is ever made for it.
- Contrast of existing secondary text: the bond card's activity/XP labels (foreground at 0.62 alpha) and the menu subtitle (0.58) measure 3.4–3.8:1 on the light theme. Raising them to about 0.74 reaches 5.2:1. That is a separate accessibility fix.

### Confidence Assessment

- **High** for the code: every part, including the GTK card, was prototyped and run against the full suite, and a real card was built headless (210×84 px, X11 mode).
- **Medium** for live behavior: XWayland stacking, the pure-Wayland popover, and the feel of "line, then meters" need owner QA.
- **Areas of concern:** threshold feel on real workloads, and whether hover-to-show feels discoverable.
