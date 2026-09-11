# Getting Started

Mochi is currently an experimental Linux desktop companion under active development.

This guide covers development checkout setup rather than a polished end-user installer.

## Supported development target

Primary environment:

- Fedora Linux
- GNOME
- Wayland session
- Python 3.11+

Mochi may use XWayland for behavior that native GNOME Wayland restrictions make difficult.

## System packages

On Fedora:

```bash
sudo dnf install python3 python3-gobject gtk4 gtk4-layer-shell
```

Package names may differ on other distributions.

## Clone the repository

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
```

## Install development checkout

```bash
python3 -m pip install -e .
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

Do not assume package metadata, README status text, and local development branches always advance at the same moment; verify the branch/commit you are testing.
