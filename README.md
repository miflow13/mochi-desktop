# Mochi

[![Tests](https://github.com/miflow13/mochi-desktop/actions/workflows/tests.yml/badge.svg)](https://github.com/miflow13/mochi-desktop/actions/workflows/tests.yml)

<img width="800" height="475" alt="Mochi desktop companion" src="https://github.com/user-attachments/assets/f2030934-4153-4c03-9b84-350505b9f75e" />

A Linux desktop companion that idles, walks, responds to interaction, and can
react to broad local desktop activity without reading its contents.

[Website](https://miflow13.github.io/mochi-desktop/) · [Documentation](docs/README.md) · [Changelog](CHANGELOG.md) · [Issues](https://github.com/miflow13/mochi-desktop/issues) · [Asset guide](assets/mochi/README.md)

> **Status:** early public alpha. Fedora with GNOME on Wayland is the primary
> tested configuration. Mochi uses XWayland for its window on GNOME Wayland,
> where native positioning restrictions require it.

## Install

The installer has a supported dependency path for Fedora. It creates a private
Python environment, installs the GNOME helper, adds Mochi to the application
grid, and installs `mochi` and `mochi-uninstall` under `~/.local/bin`.

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

After the first GNOME Wayland installation, log out and back in once. This lets
GNOME load Mochi's optional desktop-awareness helper. Without it, Mochi still
runs, but typing, app-category, file-browsing, and focused-media reactions may
be unavailable.

### Fedora with Niri

Niri support is experimental. After an update, rerun the installer and reset
Mochi's saved position before launching:

```bash
./install.sh
mochi --reset-position
```

## Run and interact

Launch Mochi from the application grid or run `mochi`. If `~/.local/bin` is
not on `PATH`, use `~/.local/bin/mochi`.

- Left-click: chirp and tactile reaction.
- Three quick clicks: short dialogue.
- Double-click: heart emote.
- Drag: reposition Mochi.
- Right-click: controls for size, audio, sleep/wake, movement, and quit.
- **Stay put**: disable autonomous walking while leaving other behavior active.

`Ctrl + Alt + Shift + M` opens Mochi Lab, a developer surface for animation and
AmbiSense previews. It requires the GNOME helper.

## AmbiSense and privacy

AmbiSense is Mochi's local, rule-based awareness system. Depending on the
available integrations, it can use anonymous typing activity, session state,
coarse app categories, media playback, power changes, network changes, and
file-browsing activity.

It is not an LLM and does not use a cloud service. Mochi does not collect typed
characters, words, key values, typing history, application titles, document
names, or on-screen content. See the [AmbiSense documentation](docs/ambisense.md)
for its event flow and privacy model.

## Compatibility and troubleshooting

- Fedora with GNOME on Wayland is the primary tested target. Other
  distributions may work, but automatic dependency installation supports Fedora
  only.
- GNOME provides the fullest AmbiSense integration. Other desktops may have
  reduced awareness features.
- Niri, fractional scaling, and multi-monitor configurations receive less
  regression coverage.

If typing reactions do not work, check the helper and log out/in once:

```bash
gnome-extensions info mochi-typing@miflow13
gnome-extensions enable mochi-typing@miflow13
```

Use `mochi --reset-position` to forget saved placement and `mochi --debug` for
diagnostic logging. Detailed setup and recovery steps are in [Getting Started](docs/wiki/Getting-Started.md)
and [Troubleshooting and Regressions](docs/wiki/Troubleshooting-and-Regressions.md).

## Uninstall

```bash
mochi-uninstall
```

To remove saved settings as well:

```bash
mochi-uninstall --purge
```

## Development

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
python -m pytest
mochi --debug
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [REGRESSION_WATCHLIST.md](REGRESSION_WATCHLIST.md),
and the [documentation index](docs/README.md) for contribution and verification
guidance.

## Roadmap

| Version | Focus |
| --- | --- |
| v0.1 | Core desktop companion behavior |
| v0.2 | Animation polish, AmbiSense, contextual reactions, and reliability |
| v0.3 | Lightweight care and progression |
| v0.4 | More behaviors, expressions, and personalization |
| v0.5 | Broader Linux desktop integration |

The roadmap is directional, not a release schedule. Mochi is released under
the [MIT License](LICENSE).
