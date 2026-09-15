# Getting Started

Mochi is currently an experimental Linux desktop companion under active development.

For alpha testing, use the [README installer and update instructions](../../README.md#install).
The primary tested configuration is Fedora + GNOME + Wayland/XWayland; Niri is
experimental. On first GNOME Wayland installation, log out/in once so the helper
can load. See [current known issues](../../README.md#known-issues) before testing.

The steps below are for an editable development checkout. Unlike the app-grid
installation, editable installs pick up source edits after restarting Mochi.

## Supported development target

Primary environment:

- Fedora Linux
- GNOME
- Wayland session
- Python 3.11+

Mochi may use XWayland for behavior that native GNOME Wayland restrictions make difficult.

## System packages

On Fedora, the [installer](../../install.sh) handles the full runtime dependency
list and GNOME helper setup. Complete the README installation first, then use a
separate development environment below. Other distributions need manual dependency setup.

## Clone the repository

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
```

## Install development checkout

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m pip install pytest
```

This installs the Python package in editable mode so source changes are reflected without rebuilding the package after every edit.

## Launch Mochi

```bash
mochi
```

Useful modes:

```bash
mochi --debug
mochi --reset-position
mochi --preview-animations
```

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

For a wider validation pass:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests -v
git diff --check
```

## Build a wheel

```bash
python3 -m pip wheel . --no-deps --no-build-isolation -w /tmp/mochi-wheel
```

When animation assets or packaging rules change, inspect the wheel contents before treating the build as valid.

## Current user interactions

The project is evolving quickly, but the intended public-alpha interaction model centers on:

- idle/breathing
- click reactions
- double-click heart reaction
- right-click context menu
- walking
- sleep/wake
- pickup/drag/drop
- ambient and explicit emotes such as computer/typing

See [Interaction Core](Interaction-Core.md) for the detailed state model.

## Context menu terminology

The menu opened by right-clicking Mochi is the **context menu**.

Use this term consistently in issues, code comments, and documentation.

## Wayland notes

Wayland intentionally restricts arbitrary synthetic input and certain window-management behavior.

Mochi should work within those constraints rather than requiring invasive permissions.

Normal runtime should not request:

- remote desktop
- screen sharing
- screen recording
- synthetic input control

Development automation may need separate desktop-control permissions for testing, but those are not part of Mochi's runtime design.

## Pixel-art expectations

If Mochi looks blurry, inspect rendering configuration before editing the art.

Runtime rules:

- 256×256 asset frames scaled to the configured window size
- nearest-neighbor scaling
- bottom-center anchoring
- transparent RGBA assets
- no bilinear smoothing

See [Animation and Art Pipeline](Animation-and-Art-Pipeline.md).

## If Mochi becomes unresponsive

Record the exact sequence that caused it.

For example:

```text
IDLE
→ RIGHT CLICK
→ WALK
→ DRAG
→ INPUT FREEZE
```

Then consult [Troubleshooting and Regressions](Troubleshooting-and-Regressions.md) and the repository `REGRESSION_WATCHLIST.md`.

## Current release status

Mochi is not yet presented as a stable public release. The project is currently focused on interaction-core stability and public-alpha readiness.

Package/runtime metadata is `0.2.0a0`. Published GitHub release labels have
[documented discrepancies](../../CHANGELOG.md#release-metadata-note), so include
the tested branch/commit in bug reports. Pulling source alone does not refresh
the app-grid copy: quit Mochi, rerun `./install.sh`, and relaunch it.
