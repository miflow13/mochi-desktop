
# Mochi

## Support Mochi ☕

Mochi is free and open source. If you enjoy having this little desktop buddy around
and would like to support continued development, you can support the project on Ko-fi.

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](YOUR_PUBLIC_KOFI_URL)

[![Tests](https://github.com/miflow13/mochi-desktop/actions/workflows/tests.yml/badge.svg)](https://github.com/miflow13/mochi-desktop/actions/workflows/tests.yml)

<img width="800" height="428" alt="ezgif-2e6aaeb139cf0fe7" src="https://github.com/user-attachments/assets/9f3e0ca5-8454-4e22-a3d1-70d7e27c23fe" />

A Linux desktop companion that idles, walks, responds to interaction, and can
react to broad local desktop activity without reading its contents.

[Website](https://miflow13.github.io/mochi-desktop/) · [Documentation](docs/README.md) · [Changelog](CHANGELOG.md) · [Report a bug](#reporting-bugs) · [Asset guide](assets/mochi/README.md)

> **Status:** early public alpha. Fedora with GNOME on Wayland is the primary
> tested configuration. Mochi uses XWayland for its window on GNOME Wayland,
> where native positioning restrictions require it.

> 🌟 **Milestone:** Mochi reached **30 GitHub stars**! Thank you to everyone
> following, testing, and cheering on this tiny Linux desktop buddy while the
> public alpha takes shape.


## Install

The installer has a supported dependency path for Fedora. It creates a private
Python environment, installs the GNOME helper, adds Mochi to the application
grid, and installs `mochi` and `mochi-uninstall` under `~/.local/bin`.

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

This installs the checked-out source (by default, current `main`), not a pinned
release. The installer may use `sudo dnf` for missing Fedora packages.

After the first GNOME Wayland installation, log out and back in once. This lets
GNOME load Mochi's optional desktop-awareness helper. Without it, Mochi still
runs, but typing, app-category, file-browsing, and focused-media reactions may
be unavailable.

### Update an installed copy

Quit Mochi, then run these commands from your clean `main` checkout:

```bash
git pull --ff-only
./install.sh
```

Relaunch Mochi afterward. The installer copies the checkout into a private
environment; `git pull` alone does not update the app-grid installation, and
an already-running process keeps its loaded code.

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

### Known issues

- **Workspace/Overview freeze — [#45](https://github.com/miflow13/mochi-desktop/issues/45):**
  on GNOME Wayland/XWayland, entering Overview or switching workspaces during
  an emote can leave Mochi visually frozen. This remains an open alpha blocker.

- Alpha behavior and compatibility may change. Passing automated tests does
  not establish reliability across desktop sessions, monitors, or scaling setups.

### Helper and placement checks

If typing reactions do not work, check the helper and log out/in once:

```bash
gnome-extensions info mochi-typing@miflow13
gnome-extensions enable mochi-typing@miflow13
```

Use `mochi --reset-position` to forget saved placement and `mochi --debug` for
diagnostic logging. Detailed setup and recovery steps are in [Getting Started](docs/wiki/Getting-Started.md)
and [Troubleshooting and Regressions](docs/wiki/Troubleshooting-and-Regressions.md).

## Reporting bugs

[Open a bug report](https://github.com/miflow13/mochi-desktop/issues/new?template=bug_report.md)
with the shortest reproduction steps, expected and actual behavior, Linux and
GNOME/compositor versions, Wayland/X11 session type, and monitor layout/scaling.
Include the tested branch/commit or release tag, how you installed/launched Mochi,
and whether you reinstalled and restarted after updating.

For logs, quit Mochi and launch `mochi --debug` in a terminal. Include relevant
output and whether dragging, a menu, an emote, Overview, or a workspace switch
preceded the problem. Check [existing issues](https://github.com/miflow13/mochi-desktop/issues)
first; reports for #45 and #68 are still useful.

## Uninstall

```bash
mochi-uninstall
```

To remove saved settings as well:

```bash
mochi-uninstall --purge
```

## Development

Complete the [Fedora runtime/helper installation](#install) first, then use a
separate editable environment:

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install pytest
python -m pytest
mochi --debug
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [REGRESSION_WATCHLIST.md](REGRESSION_WATCHLIST.md),
and the [documentation index](docs/README.md) for contribution and verification
guidance.

## Roadmap

| Direction | Focus |
| --- | --- |
| Current alpha | Core interactions, AmbiSense, and reliability |
| Future possibilities | Care/progression, more expressions, and personalization |
| Longer term | Broader Linux desktop integration |

Future ideas are not a list of shipped features or a release schedule. Mochi is released under
the [MIT License](LICENSE).
