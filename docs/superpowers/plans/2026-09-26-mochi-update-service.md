# Mochi Update Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished, opt-in Mochi updater that detects newer `main` commits, notifies once, performs an exact-commit staged update with rollback, and relaunches a verified working Mochi.

**Architecture:** Keep discovery/presentation inside the running Mochi process and keep installation inside a separate updater process. Resolve one exact target SHA, stage a candidate runtime with the existing installer, swap only after validation, require a startup-ready handshake before deleting the backup, and keep relationship/preferences data outside the replaceable runtime.

**Tech Stack:** Python 3.11+, GTK4/PyGObject, GLib/Gio, Python standard library (`urllib`, `json`, `tarfile`, `tempfile`, `subprocess`, `pathlib`, `threading`), existing Bash installer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-mochi-update-service-design.md`

## Global Constraints

- Automatic checks happen at most once every 24 hours by default.
- Automatic update checks must never block Mochi startup.
- Automatic check failures remain silent; manual checks may show a friendly error.
- Only the official repository `miflow13/mochi-desktop` is a valid normal update source.
- One update attempt resolves `main` once and uses that exact commit SHA for metadata and source download.
- Source archives are downloaded only after explicit **Update & Restart** approval.
- No update may mutate a user's Git checkout.
- The current working runtime remains recoverable until the replacement reports successful startup.
- Bond/progression/preferences/future personality data are not replaced by runtime updates.
- No telemetry, accounts, device IDs, arbitrary update URLs, background auto-install, or forced restart.
- Update UI uses real Mochi pixel art, nearest-neighbor rendering, system light/dark theme behavior, and Mochi green accents.
- The updater must not depend on files/imports from the active venv after the critical runtime rename begins.
- Existing `mochi`, `mochi-uninstall`, clean `./install.sh`, GNOME-helper, context-menu, drag, Sleep, Focus, and ambient behavior must remain intact.

## Review Focus

- **GitHub changes `main` between discovery and install:** pin metadata and archive requests to the originally resolved SHA; test that no second branch-head lookup occurs during an approved update.
- **Interrupted/failed candidate install:** the existing `venv` must remain untouched; test stage failure with a pre-existing runtime marker.
- **New process installs but crashes before readiness:** restore `venv.backup`, preserve user config, and relaunch the old runtime; test handshake timeout/failure.
- **Updater replaces the venv that originally launched it:** bootstrap all critical updater Python/UI files outside the active venv before swap; test the worker continues after the original package path is renamed.
- **Update result arrives while Mochi is busy with drag/Focus/Sleep/menu:** update discovery must not change behavioral state; test menu/bubble integration remains presentation-only and shutdown cancels pending callbacks safely.

---

## File map

### New update-domain files

- `src/mochi/update/__init__.py` — package boundary only.
- `src/mochi/update/model.py` — immutable update/install data types and update-stage enums.
- `src/mochi/update/storage.py` — installed-build metadata store at `$XDG_DATA_HOME/mochi-desktop/install.json`.
- `src/mochi/update/checker.py` — official GitHub source client and cooldown-aware update checker.
- `src/mochi/update/bootstrap.py` — copies updater runtime/assets outside the active venv and launches the independent worker.
- `src/mochi/update/worker.py` — exact-SHA download, validation, staging, swap, handshake, rollback, cleanup.
- `src/mochi/update/window.py` — reusable compact GTK updater window/state rendering.
- `src/mochi/update_cli.py` — `mochi-update` console entry point.

### Runtime integration

- `src/mochi/presence/update_controls.py` — startup/manual checking, speech bubble, context-menu row, updater-window launch; presentation only.
- `src/mochi/presence/click_dialogue.py` — compose `UpdateControlsMixin` into both production Buddy classes.
- `src/mochi/main.py` — internal `--update-ready-file` startup handshake argument.
- `src/mochi/app.py` — signal readiness only after normal Buddy/window initialization succeeds.
- `src/mochi/config.py` — update-check preference/timestamps/dismissed target only.

### Installer/package/release metadata

- `install.sh` — preserve default behavior, add runtime-staging and integration-refresh modes, write normal-install metadata.
- `pyproject.toml` — install `mochi-update` entry point.
- `update.json` — current channel/version plus 2–3 curated highlights.
- `README.md` / `CHANGELOG.md` — user-facing update instructions and feature note.

### Tests

- `tests/test_update_storage.py`
- `tests/test_update_checker.py`
- `tests/test_update_bootstrap.py`
- `tests/test_update_worker.py`
- `tests/test_update_window.py`
- `tests/test_update_controls.py`
- `tests/test_update_handshake.py`
- modify `tests/test_installer.py`
- modify relevant context-menu/composition tests if required by the new row/mixin.

---

### Task 1: Define update identity, preferences, and installed-build storage

**Files:**
- Create: `src/mochi/update/__init__.py`
- Create: `src/mochi/update/model.py`
- Create: `src/mochi/update/storage.py`
- Modify: `src/mochi/config.py`
- Test: `tests/test_update_storage.py`
- Modify/Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `UpdateStatus(Enum): UP_TO_DATE, UPDATE_AVAILABLE, CHECK_FAILED`
  - `UpdateMetadata(version: str, channel: str, highlights: tuple[str, ...])`
  - `InstalledBuild(version: str, commit: str | None, channel: str, installed_at: str)`
  - `UpdateTarget(commit: str, metadata: UpdateMetadata)`
  - `UpdateCheckResult(status: UpdateStatus, target: UpdateTarget | None = None, error: str | None = None, announce: bool = False)`
  - `InstallMetadataStore(path: Path | None = None)`
  - `InstallMetadataStore.load() -> InstalledBuild | None`
  - `InstallMetadataStore.save(build: InstalledBuild) -> None`
  - `ConfigStore.load_update_checks_enabled() -> bool` default `True`
  - `ConfigStore.save_update_checks_enabled(enabled: bool) -> None`
  - `ConfigStore.load_last_update_check() -> float | None`
  - `ConfigStore.save_last_update_check(timestamp: float) -> None`
  - `ConfigStore.load_dismissed_update_commit() -> str | None`
  - `ConfigStore.save_dismissed_update_commit(commit: str | None) -> None`

- [ ] **Step 1: Write failing storage/config tests**

Add tests asserting:

```python
assert ConfigStore(path).load_update_checks_enabled() is True
assert ConfigStore(path).load_last_update_check() is None
assert ConfigStore(path).load_dismissed_update_commit() is None
```

Round-trip explicit values and verify malformed values fall back safely. For `InstallMetadataStore`, assert missing/malformed files return `None`, save/load preserves all four `InstalledBuild` fields, and writes are atomic via a temporary sibling file.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
pytest tests/test_update_storage.py tests/test_config.py -q
```

Expected: FAIL because update model/storage/config methods do not exist.

- [ ] **Step 3: Implement the model and persistence interfaces**

Keep install identity in `$XDG_DATA_HOME/mochi-desktop/install.json`; keep check/dismissal preferences in the existing user config file.

`UpdateMetadata.highlights` must normalize to at most three non-empty strings. Invalid installed metadata returns `None` rather than raising into startup.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run:

```bash
pytest tests/test_update_storage.py tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/update src/mochi/config.py tests/test_update_storage.py tests/test_config.py
git commit -m "feat: add update state persistence"
```

---

### Task 2: Add exact-commit GitHub discovery and cooldown-aware checking

**Files:**
- Create: `src/mochi/update/checker.py`
- Create: `update.json`
- Test: `tests/test_update_checker.py`

**Interfaces:**
- Consumes: Task 1 model/storage/config interfaces.
- Produces:
  - `OFFICIAL_REPOSITORY = "miflow13/mochi-desktop"`
  - `AUTO_CHECK_INTERVAL_SECONDS = 86_400`
  - `DEFAULT_NETWORK_TIMEOUT_SECONDS = 3.0`
  - `GitHubUpdateSource.resolve_main_sha() -> str`
  - `GitHubUpdateSource.fetch_metadata(commit: str) -> UpdateMetadata`
  - `UpdateChecker.check(*, manual: bool = False, now: float | None = None) -> UpdateCheckResult`

Use Python `urllib.request` with a Mochi-specific User-Agent; inject/open through a small callable so tests never use the network.

- [ ] **Step 1: Write failing checker tests**

Cover:

```text
installed commit == resolved main -> UP_TO_DATE
installed commit != resolved main -> UPDATE_AVAILABLE with exact SHA
automatic check inside 86400 seconds -> no HTTP call
manual=True inside cooldown -> HTTP call occurs
network/timeout exception -> CHECK_FAILED, no exception escapes
missing install metadata -> safe CHECK_FAILED/unknown-current result, no false update claim
malformed update.json -> UPDATE_AVAILABLE still carries exact SHA with fallback metadata
dismissed target -> result remains UPDATE_AVAILABLE with `announce is False` without changing target
newer target than dismissed commit -> `announce is True` again
```

Also assert one call resolves `main` and metadata is fetched using the returned SHA, never a second `main` lookup.

- [ ] **Step 2: Run the checker tests and confirm RED**

```bash
pytest tests/test_update_checker.py -q
```

Expected: FAIL because `checker.py` does not exist.

- [ ] **Step 3: Implement `GitHubUpdateSource` and `UpdateChecker`**

Resolve branch head using GitHub's public commit endpoint for `main`. Fetch `update.json` from the exact commit via a raw-content URL.

Record `last_update_check` after an attempted automatic/manual network check so an outage does not create a retry loop in the same session/day. Do not change `dismissed_commit` during discovery.

- [ ] **Step 4: Run the checker tests and confirm GREEN**

```bash
pytest tests/test_update_checker.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/update/checker.py tests/test_update_checker.py update.json
git commit -m "feat: detect exact Mochi updates"
```

---

### Task 3: Refactor the existing installer for staging without changing normal installs

**Files:**
- Modify: `install.sh`
- Modify: `tests/test_installer.py`

**Interfaces:**
- Produces installer modes:
  - `./install.sh` — unchanged full user install/reinstall.
  - `./install.sh --stage-runtime <absolute-venv-path>` — build a candidate runtime only; do not change launchers, desktop file, icon, GNOME helper, uninstall launcher, or `install.json`.
  - `./install.sh --refresh-integrations` — assume final `$APP_HOME/venv` already exists; refresh launcher/uninstaller/icon/desktop/GNOME helper without rebuilding the venv or writing `install.json`.
- Normal full install additionally writes `install.json`; commit identity comes from `MOCHI_INSTALLED_COMMIT` when set, else `git -C "$ROOT" rev-parse HEAD` when available, else JSON `null`.

- [ ] **Step 1: Extend installer harness with staging/refresh assertions**

Add failing tests proving:

```text
normal install still builds ~/.local/share/mochi-desktop/venv
normal install still creates mochi + mochi-uninstall
normal install writes install.json
--stage-runtime <candidate> creates candidate/bin/mochi
--stage-runtime does not move/delete existing final venv
--stage-runtime does not install helper/desktop/icon/launchers
--refresh-integrations does not invoke python -m venv or pip install project
--refresh-integrations points ~/.local/bin/mochi at final APP_HOME/venv/bin/mochi
project-install failure in staging leaves final existing marker intact
```

At this task boundary, assert only the existing `mochi` runtime executable. Task 6 adds and tests the `mochi-update` console script after its entry point exists.

- [ ] **Step 2: Run installer tests and confirm RED**

```bash
pytest tests/test_installer.py -q
```

Expected: FAIL on unsupported staging/refresh modes.

- [ ] **Step 3: Refactor `install.sh` into runtime and integration functions**

Keep dependency checks shared. Move current venv creation/pip install behavior into a function that accepts the target venv path. Move launcher/uninstaller/icon/desktop/helper work into a separate integration function.

Default no-argument execution must call both paths in the current order and preserve existing rollback behavior.

- [ ] **Step 4: Add normal-install metadata writing**

Write `$APP_HOME/install.json` atomically only after a normal full install succeeds. Do not write metadata from `--stage-runtime` or `--refresh-integrations`.

Read package version from `pyproject.toml` through the installed candidate Python/importlib metadata rather than duplicate the version string in shell.

- [ ] **Step 5: Run installer tests and shell syntax check**

```bash
bash -n install.sh
pytest tests/test_installer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add install.sh tests/test_installer.py
git commit -m "refactor: support staged Mochi installs"
```

---

### Task 4: Implement the transactional update worker and rollback

**Files:**
- Create: `src/mochi/update/worker.py`
- Test: `tests/test_update_worker.py`

**Interfaces:**
- Consumes: Task 1 model/storage; Task 3 installer modes.
- Produces:
  - `UpdateStage(Enum)`: `DOWNLOADING`, `VERIFYING`, `INSTALLING`, `SWAPPING`, `REFRESHING`, `RESTARTING`, `SUCCESS`, `FAILED`.
  - `UpdateProgress(stage: UpdateStage, message: str, downloaded: int | None = None, total: int | None = None)`.
  - `UpdatePaths.for_environment(...) -> UpdatePaths` with final `venv`, `venv.update`, `venv.backup`, app home, temp source, ready-file.
  - `UpdateWorker.run(target: UpdateTarget, *, wait_pid: int | None, on_progress: Callable[[UpdateProgress], None]) -> int`.

The worker package must use only standard library plus system-available PyGObject in UI code. Critical transaction logic must not import ordinary Mochi runtime modules outside `mochi.update`.

- [ ] **Step 1: Write failing transaction tests with fake filesystem/subprocess/download seams**

Cover:

```text
archive URL contains exact target SHA
required pyproject.toml, install.sh, src/mochi/, assets/mochi/ are validated
invalid archive exits before installer invocation
stage install failure leaves final venv untouched
candidate validation checks executable, package metadata/import, and required assets
existing stale venv.update / venv.backup are handled deterministically
worker waits for wait_pid to exit before swap
same-filesystem rename order is final -> backup, candidate -> final
refresh-integrations failure restores backup runtime
new process readiness success deletes backup and writes install.json
readiness timeout restores backup and relaunches prior runtime
rollback never deletes user config
temporary archive/source/ready files are cleaned on both success and failure
no second resolve-main operation exists in worker
```

- [ ] **Step 2: Run worker tests and confirm RED**

```bash
pytest tests/test_update_worker.py -q
```

Expected: FAIL because `worker.py` does not exist.

- [ ] **Step 3: Implement exact-SHA download/extraction and validation**

Download:

```text
https://codeload.github.com/miflow13/mochi-desktop/tar.gz/<TARGET_SHA>
```

Reject unsafe tar members that escape the extraction directory. Locate the single extracted repository root and validate the four required source paths before invoking shell code.

- [ ] **Step 4: Implement candidate staging and validation**

Invoke:

```bash
./install.sh --stage-runtime "$APP_HOME/venv.update"
```

from the extracted exact-SHA source.

Validate the candidate with its own Python/executable and installed data before touching the final runtime.

- [ ] **Step 5: Implement swap, integration refresh, readiness, and rollback**

After `wait_pid` has exited:

1. move final `venv` to `venv.backup`;
2. move `venv.update` to final `venv`;
3. run extracted `./install.sh --refresh-integrations`;
4. launch final `venv/bin/mochi --update-ready-file <ready-file>`;
5. wait up to **10 seconds** for readiness;
6. on success write `install.json`, remove backup;
7. on failure restore backup and relaunch previous `venv/bin/mochi`.

Keep the exact 10-second handshake limit as a named constant.

- [ ] **Step 6: Run worker tests and confirm GREEN**

```bash
pytest tests/test_update_worker.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/mochi/update/worker.py tests/test_update_worker.py
git commit -m "feat: add transactional Mochi updater"
```

---

### Task 5: Bootstrap the updater outside the active venv

**Files:**
- Create: `src/mochi/update/bootstrap.py`
- Test: `tests/test_update_bootstrap.py`

**Interfaces:**
- Consumes: Task 1 update target.
- Produces:
  - `bootstrap_updater(target: UpdateTarget, *, gui: bool, wait_pid: int | None = None) -> subprocess.Popen`
  - bootstrap workspace containing a copied `mochi/update` package plus these existing authored art directories: `idle`, `wave`, `sad_idle`, and `focus`.
  - worker process started with the base/system Python executable, not `sys.executable` from the replaceable private venv.

- [ ] **Step 1: Write failing bootstrap tests**

Assert:

```text
bootstrap copies the update package to a temporary/app-owned workspace
bootstrap copies only `idle`, `wave`, `sad_idle`, and `focus` updater animation assets
worker command uses sys._base_executable when executable, else /usr/bin/python3 fallback
target SHA/version/channel and wait_pid survive serialization into worker args
renaming the original installed package path after Popen setup does not remove worker source/assets
bootstrap never copies user config/bond data
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
pytest tests/test_update_bootstrap.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement bootstrap copy + re-exec boundary**

Do not let the external worker import through the original private venv after bootstrap. The copied update package must be sufficient for worker execution and updater UI.

- [ ] **Step 4: Run tests and confirm GREEN**

```bash
pytest tests/test_update_bootstrap.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/update/bootstrap.py tests/test_update_bootstrap.py
git commit -m "feat: isolate updater from active runtime"
```

---

### Task 6: Add the `mochi-update` CLI and installed startup handshake

**Files:**
- Create: `src/mochi/update_cli.py`
- Modify: `src/mochi/main.py`
- Modify: `src/mochi/app.py`
- Modify: `pyproject.toml`
- Test: `tests/test_update_handshake.py`
- Test: `tests/test_update_cli.py`
- Modify: `tests/test_installer.py` for launcher coverage

**Interfaces:**
- Consumes: Tasks 1, 2, 4, 5.
- Produces:
  - console script `mochi-update = "mochi.update_cli:main"`.
  - internal Mochi argument `--update-ready-file PATH`.
  - `MochiApplication(..., update_ready_file: Path | None = None)`.
  - `signal_update_ready(path: Path) -> None` called only after Buddy construction/window presentation reaches normal initialized state.

CLI behavior:

```text
mochi-update
  -> check current vs main
  -> "already up to date" and exit 0, or show target highlights
  -> prompt "Update & restart Mochi? [y/N]"
  -> on yes bootstrap exact target updater

mochi-update --yes
  -> same flow without prompt

mochi-update --target-sha <sha> --target-version <version> --target-channel <channel> --wait-pid <pid> [--gui]
  -> internal handoff path; do not resolve main again
```

- [ ] **Step 1: Write failing parser/handshake/CLI tests**

Cover:

```text
main parser accepts internal --update-ready-file
ready file is not written if application construction/activation fails
ready file is atomically created after normal activation reaches presented Buddy
CLI up-to-date returns 0 without bootstrap
CLI declined prompt returns 0 without bootstrap
CLI --yes bootstraps exact target
internal --target-sha path never calls checker.resolve_main_sha
pyproject exposes mochi-update console script
installer-produced launcher exists after full install
```

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
pytest tests/test_update_handshake.py tests/test_update_cli.py tests/test_installer.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement startup readiness signaling**

Keep the argument internal/unadvertised in normal help text if practical. Write the ready file only after the window/Buddy has initialized successfully; use atomic file creation/replacement.

- [ ] **Step 4: Implement CLI and package entry point**

The CLI must use the same checker/bootstrap/worker path as the GUI. No second updater implementation.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```bash
pytest tests/test_update_handshake.py tests/test_update_cli.py tests/test_installer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/update_cli.py src/mochi/main.py src/mochi/app.py pyproject.toml tests/test_update_handshake.py tests/test_update_cli.py tests/test_installer.py
git commit -m "feat: add mochi-update command"
```

---

### Task 7: Build the polished reusable GTK updater window

**Files:**
- Create: `src/mochi/update/window.py`
- Test: `tests/test_update_window.py`

**Interfaces:**
- Consumes: Task 1 target/model and Task 4 progress stages.
- Produces:
  - `UpdateWindow(Gtk.Window)`
  - `UpdateWindow.show_available(installed: InstalledBuild | None, target: UpdateTarget) -> None`
  - `UpdateWindow.show_progress(progress: UpdateProgress) -> None`
  - `UpdateWindow.show_failure(message: str, details: str) -> None`
  - `UpdateWindow.show_success() -> None`
  - callback constructor arguments for `on_later`, `on_update_restart`, `on_retry`, `on_close`.
  - internal `UpdaterSprite` using copied real Mochi frames with nearest-neighbor GTK texture filtering.

Use:
- idle/wave frames for available/success;
- a calm existing authored loop such as `focus` or `coffee` for install progress if its packaged frame set is appropriate;
- sad idle for failure;
- no regenerated/modified artwork.

- [ ] **Step 1: Write failing view-model/widget-state tests**

Do not require pixel-perfect screenshot testing. Assert the GTK state model exposes:

```text
available -> installed/available version, max 3 highlights, Later + Update & Restart
downloading with byte totals -> real progress fraction
installing/checking/restarting -> stage list, no fake numeric fraction
critical stages -> no Cancel action
failure -> Try Again / Close / Show Details and "current Mochi is still safe"
success -> "All updated!" / return presentation
light/dark styling uses theme colors and #79c98b accent rather than fixed dark background
sprite frame rendering requests nearest-neighbor filtering
```

- [ ] **Step 2: Run window tests under Xvfb and confirm RED**

```bash
xvfb-run -a pytest tests/test_update_window.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement the compact window and reusable state transitions**

Keep one `UpdateWindow` instance per process and mutate its content/state; do not create nested modal chains.

- [ ] **Step 4: Run window tests and confirm GREEN**

```bash
xvfb-run -a pytest tests/test_update_window.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/update/window.py tests/test_update_window.py
git commit -m "feat: add polished Mochi updater window"
```

---

### Task 8: Integrate quiet checks, bubble notification, and context-menu controls

**Files:**
- Create: `src/mochi/presence/update_controls.py`
- Modify: `src/mochi/presence/click_dialogue.py`
- Modify: `src/mochi/buddy.py` only if existing mixin forwarding/composition requires it
- Modify: `src/mochi/buddy_menu.py` only for menu min-height/layout metadata if the new row needs it
- Test: `tests/test_update_controls.py`
- Modify/Test: `tests/test_context_menu_layout.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 5, 7.
- Produces `UpdateControlsMixin` with:
  - `UPDATE_STARTUP_DELAY_MS = 5_000`
  - `_start_update_check(*, manual: bool) -> None`
  - `_apply_update_check_result(result: UpdateCheckResult, *, manual: bool) -> bool` for `GLib.idle_add`
  - `_show_update_window(target: UpdateTarget) -> None`
  - `shutdown_presence() -> None` that invalidates callbacks and closes update UI before `super()`.

Runtime network work must run off the GTK main thread; GTK mutation returns to the main loop with `GLib.idle_add`.

- [ ] **Step 1: Write failing integration tests**

Cover:

```text
preview mode does not schedule/check updates
startup schedules one delayed automatic check
automatic check runs off main-thread seam and result is applied via GLib idle callback
UPDATE_AVAILABLE changes row label/indicator without changing MochiState
eligible target attempts exactly one "psst... i learned some new things! 🌱" bubble in the session
busy/dialogue-disallowed state does not force a state transition to show update speech
Later saves dismissed target commit
same dismissed commit does not re-announce
manual Check for updates bypasses cooldown and opens friendly up-to-date/check-failed presentation
Update & Restart calls bootstrap_updater(target, gui=True, wait_pid=os.getpid()) then requests clean Gtk.Application quit
shutdown prevents late network callback from mutating destroyed UI
context menu retains ordering/reopen behavior after update row is added
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
xvfb-run -a pytest tests/test_update_controls.py tests/test_context_menu_layout.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement `UpdateControlsMixin` without behavioral-state ownership**

Use the existing `SpeechBubble.show(text, duration_seconds=...)` and menu registration APIs. Do not transition Mochi's state, cancel Focus, interrupt drag, or create an ambient-state owner.

Use one context-menu row:
- label **Check for updates** when no update is known;
- label **Update available** when a target is known.

Place it near Quick Start/Close so care/movement controls stay grouped.

- [ ] **Step 4: Compose the mixin in both production Buddy classes**

Add the mixin to `PresenceBuddy` and `PresenceX11Buddy` in the same relative location so Linux backend choice does not alter updater behavior. Add an MRO regression if the new mixin's `shutdown_presence` or `_build_context_menu` chain could be shadowed.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```bash
xvfb-run -a pytest tests/test_update_controls.py tests/test_context_menu_layout.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mochi/presence/update_controls.py src/mochi/presence/click_dialogue.py src/mochi/buddy.py src/mochi/buddy_menu.py tests/test_update_controls.py tests/test_context_menu_layout.py
git commit -m "feat: notify users about Mochi updates"
```

---

### Task 9: Wire the external GUI progress handoff end-to-end

**Files:**
- Modify: `src/mochi/update_cli.py`
- Modify: `src/mochi/update/worker.py`
- Modify: `src/mochi/update/window.py`
- Modify: `src/mochi/update/bootstrap.py`
- Test: `tests/test_update_cli.py`
- Test: `tests/test_update_worker.py`
- Test: `tests/test_update_window.py`

**Interfaces:**
- Consumes: Tasks 4–8.
- Produces:
  - external GUI updater started by `bootstrap_updater(..., gui=True)`;
  - worker progress marshalled onto GTK main loop;
  - same `UpdateWindow` visual component used for runtime available state and external downloading/installing/failure state.

- [ ] **Step 1: Add failing handoff tests**

Assert:

```text
GUI handoff receives exact target without branch re-resolution
external updater shows downloading before old Mochi exits
worker waits for old pid before SWAPPING, not before downloading/staging
progress events map to the expected UpdateWindow stages
closing GUI during safe pre-swap phase requests cancellation
closing/cancel control is unavailable once SWAPPING begins
worker failure after runtime quit shows friendly failure while rollback is attempted
successful readiness closes updater and leaves relaunched Mochi as final UI
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
xvfb-run -a pytest tests/test_update_cli.py tests/test_update_worker.py tests/test_update_window.py -q
```

Expected: FAIL.

- [ ] **Step 3: Implement the progress-thread/GTK-main-loop bridge**

Run blocking download/install work on a worker thread/process path. Use `GLib.idle_add` only for GTK state mutation. Cancellation is honored only before the critical swap boundary.

- [ ] **Step 4: Run tests and confirm GREEN**

```bash
xvfb-run -a pytest tests/test_update_cli.py tests/test_update_worker.py tests/test_update_window.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mochi/update_cli.py src/mochi/update/worker.py src/mochi/update/window.py src/mochi/update/bootstrap.py tests/test_update_cli.py tests/test_update_worker.py tests/test_update_window.py
git commit -m "feat: connect updater progress and restart flow"
```

---

### Task 10: Documentation, regression coverage, and release verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/wiki/Roadmap-and-Public-Alpha.md` only to list the updater as supporting infrastructure if appropriate; do not redefine v0.4 personality scope.
- Modify: `REGRESSION_WATCHLIST.md` with updater-specific menu/quit/restart checks.
- Tests: full suite.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: documented user flow and verified branch ready for Mika's live Fedora QA.

- [ ] **Step 1: Update user documentation**

Replace the primary installed-update instructions with:

```bash
mochi-update
```

Document GUI **Check for updates** / **Update & Restart**, while retaining the manual Git + `./install.sh` path for developers/source checkouts.

State clearly that alpha updates track `main`.

- [ ] **Step 2: Add updater regression-watchlist entries**

Include:

```text
context menu reopens after update window Later/Close
drag still works after opening/closing updater
Sleep and Focus are not interrupted by a background check
automatic network failure produces no bubble/dialog/log spam
Update & Restart performs clean shutdown
successful update preserves bond/config
failed update restores runnable prior runtime
GNOME helper notice remains non-blocking
app-grid launcher starts updated Mochi
```

- [ ] **Step 3: Run focused updater suite**

```bash
xvfb-run -a pytest   tests/test_update_storage.py   tests/test_update_checker.py   tests/test_update_bootstrap.py   tests/test_update_worker.py   tests/test_update_window.py   tests/test_update_controls.py   tests/test_update_handshake.py   tests/test_update_cli.py   tests/test_installer.py   tests/test_context_menu_layout.py -q
```

Expected: PASS.

- [ ] **Step 4: Run full automated verification**

```bash
xvfb-run -a python3 -m pytest -q
python3 -m compileall -q src tests
bash -n install.sh
git diff --check
```

Expected: all tests PASS, compileall exits 0, shell syntax exits 0, `git diff --check` produces no output.

- [ ] **Step 5: Perform local non-destructive updater smoke test where possible**

Use a temporary `HOME`/`XDG_DATA_HOME` and fake or controlled source target to prove:

```text
normal install -> checker sees controlled newer target -> stage -> swap -> ready handshake
failure before swap preserves original marker/runtime
failure after swap restores original marker/runtime
```

Do not claim real Fedora/GNOME visual verification from this step.

- [ ] **Step 6: Commit documentation/release changes**

```bash
git add README.md CHANGELOG.md docs/wiki/Roadmap-and-Public-Alpha.md REGRESSION_WATCHLIST.md
git commit -m "docs: document Mochi update workflow"
```

- [ ] **Step 7: Request whole-branch code review**

Review specifically for:

```text
transaction/rollback correctness
tar extraction safety
subprocess quoting/path handling
updater independence from the replaced venv
GTK thread confinement
MRO/menu/shutdown regressions
user-state preservation
```

Address technically valid feedback one item at a time with focused tests.

- [ ] **Step 8: Mika live Fedora/GNOME/Wayland QA**

Required manual checklist:

```text
1. Launch installed Mochi normally.
2. Force/use a test target so "Update available" appears.
3. Verify one cute bubble and no repeated nagging.
4. Open updater from context menu; verify theme, real pixel art, highlights, Later.
5. Close/reopen menu; drag; Sleep; Focus; confirm no regressions.
6. Start Update & Restart; verify polished downloading/installing stages.
7. Verify Mochi exits cleanly only at swap time.
8. Verify updated Mochi relaunches and gives one "i'm back! 🌱" acknowledgement.
9. Verify Bond XP/unlocks/preferences/position remain intact.
10. Run a controlled failure test and confirm old Mochi is restored/runnable.
11. If helper changes, verify the logout/login notice is informative but non-blocking.
12. Relaunch from GNOME app grid.
```

Do not merge until this live QA passes and Mika explicitly decides the branch is ready.
