# Public alpha release audit

Verdict: **READY WITH NOTES**. Audited on Fedora 44 with Python 3.14.7.
The release version remains `0.2.0a0`.

## Scope and fixes

The clean `chore/alpha-release-hardening` branch started at `ad91f8f`,
12 commits ahead of current `origin/main` (`cf3cfe3`), with no missing main
commits. No branches or history were removed or rewritten.

- Aligned the stale `mochi.__version__` (`0.1.0`) with package metadata.
- Replaced deprecated license-table metadata with the SPDX expression and
  explicit license file. Setuptools 77 is the minimum supporting this metadata;
  Fedora 44's installed setuptools 80.10.2 also builds successfully without
  build isolation. Added the repository and issue URLs to package metadata.
- Included the installer, uninstaller, desktop template, helper installer,
  GNOME extension sources/schema, and artwork documentation in the sdist.
- Removed `typing_activity_atspi_text.py`: no tracked code, tests, or documents
  reference it, no dynamic module loader exists, and the live
  `typing_activity.py` implements the AT-SPI fallback itself.
- Corrected click and Close-menu descriptions, documented Fedora 44/GNOME 50
  support, and supplied missing development system-package/helper instructions.
- Added version and runtime packaging inventory regression checks and common
  editor/temporary-file ignore patterns.

## Verification

- Python compilation: passed.
- Initial full suite: **285 passed, 0 failed**.
- Final full suite: **287 passed, 0 failed, 0 skipped**.
- Extracted final sdist suite: **287 passed, 0 failed, 0 skipped**.
- Isolated `python -m build`: wheel and sdist succeeded, no build warnings.
- Both artifacts contain byte-identical copies of all 40 current Python modules,
  229 PNGs, the manifest, and four OGG files. The wheel entry point, MIT license,
  README metadata, and version were checked; the sdist helper/installer files
  were checked. No obsolete typing module or caches remain in either artifact.
- Installed the wheel into a separate system-site-packages venv and tested from
  `/tmp` with isolated Python: all modules import, all 32 runtime/derived
  animations load, asset/audio lookup uses the installed venv, and `mochi --help`
  succeeds. The 28 manifest animations have valid counts, timing, PNGs, and
  declared dimensions/alpha. Every runtime PNG belongs to the manifest.
- Shell syntax, JavaScript syntax, and strict GNOME schema validation passed.
- No tracked backup/build/cache files, duplicate non-art files, or obvious
  credential signatures were found. This was not an exhaustive security audit.
- Runtime imports require only the standard library plus system GI/Cairo;
  build, Pillow, and pytest remain development extras. Fedora CI provides GTK,
  GI, Cairo, X11/XWayland and Xvfb, compilation, tests, and a release build.

The test run emits one system PyGObject deprecation warning about
`GLib.unix_signal_add_full`. Some checkout runs also emitted sandbox dconf
write warnings. Neither caused failures. The installed-wheel check does not
replace a fresh graphical install/uninstall test.

## Remaining desktop QA and deferred work

Mika should verify a fresh Fedora 44/GNOME 50 Wayland install, helper enablement
after logout/login, launcher/audio, and uninstall with and without `--purge`.
Exercise terminal/editor switching, sustained typing, video focus and pause,
music, Fedora mode interruption/exit, repeated idle/wake cycles, pickup/drop,
Quick Start, Stay put, Edge roam, and menus on mixed-scale monitors.

These existing integration limitations were left outside the release freeze:

- The helper publishes context transitions, without a current-state query for
  newly started clients. Existing focus may need to change before Mochi learns
  it; helper activation after Mochi starts can require restarting Mochi.
- Menu close does not explicitly re-evaluate deferred ambient/idle events.
  Context recovery can wait for another animation completion or activity event.
- Media polling uses synchronous D-Bus calls on the UI thread; an unresponsive
  player can cause a visible pause. Broader polling/lifecycle refactoring was
  deliberately deferred.
- Some UI tests inspect source strings or use isolated mocks, so passing them
  does not prove compositor behavior or full mixin integration.

No animation/state logic, pixel files, timing, scaling, or visual styling was
changed. Byte-identical authored frames were preserved in their declared
sequences. Historical wiki checkpoints and future audio hooks were retained.
Checkout v6 was retained during the freeze; upstream now documents v7, but this
workflow uses ordinary push/pull_request events and does not require migration.

References: [setuptools metadata support](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html),
[upstream checkout documentation](https://github.com/actions/checkout).
