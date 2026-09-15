# Mochi

A small desktop companion for Linux. Mochi idles, walks, responds to direct
interaction, and can react to broad local desktop activity without reading its
contents.

[Website](https://miflow13.github.io/mochi-desktop) · [Issue tracker](https://github.com/miflow13/mochi-desktop/issues) · [Animation asset guide](assets/mochi/README.md)

> **Project status:** early public alpha. Fedora with GNOME on Wayland is the
> actively tested configuration. Mochi uses XWayland for its window on GNOME
> Wayland, where native positioning restrictions require it.

## Install

The installer has a supported dependency path for Fedora. It creates a private
Python environment, installs the GNOME helper, and adds Mochi to the app grid.

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

On the first GNOME Wayland installation, log out and back in once after the
installer finishes. GNOME then loads Mochi's optional desktop-awareness helper.
Without it, Mochi still runs, but typing, app-category, file-browsing, and
focused-media reactions may be unavailable.

### Fedora with Niri

`install.sh` installs Fedora's `gtk4-layer-shell` dependency for Niri. After an
update, run the installer again and reset Mochi's saved position before
launching:

```bash
./install.sh
mochi --reset-position
```

## Run

Launch Mochi from the application grid or run:

```bash
mochi
```

If `~/.local/bin` is not on `PATH`, use `~/.local/bin/mochi`.

## Use

- Left-click: play a chirp and a tactile reaction.
- Three quick clicks: show a short dialogue line.
- Double-click: show a heart emote.
- Drag: reposition Mochi.
- Right-click: open controls for size, audio, sleep/wake, movement, and quit.
- **Stay put**: disable autonomous walking while leaving other behavior active.

`Ctrl + Alt + Shift + M` opens Mochi Lab, a developer surface for animation and
AmbiSense previews. It requires the GNOME helper.

## AmbiSense and privacy

AmbiSense is Mochi's local, rule-based awareness system. Depending on which
optional integrations are available, it can use broad signals such as:

- anonymous typing activity and sustained typing intensity;
- idle, active, lock, and suspend/return state;
- coarse application categories, including editor, terminal, browser, media,
  and pixel-art software;
- media playback, battery and charging changes, network changes, and
  file-browsing activity.

AmbiSense is not an LLM and does not use a cloud service. Typing awareness is
content-blind: Mochi does not collect characters, words, key values, or typing
history. Application awareness receives only a small semantic category, not an
application title, document name, or on-screen content.

## Troubleshooting

### Typing reactions do not work

Check the GNOME helper status:

```bash
gnome-extensions info mochi-typing@miflow13
```

If it is not active, enable it and then log out and back in once:

```bash
gnome-extensions enable mochi-typing@miflow13
```

### Reset the saved position

```bash
mochi --reset-position
```

### Enable debug logging

```bash
mochi --debug
```

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow and
testing expectations. The current work plan is tracked in
[REGRESSION_WATCHLIST.md](REGRESSION_WATCHLIST.md).

## Roadmap

| Version | Focus |
| --- | --- |
| v0.1 | Core desktop companion behavior |
| v0.2 | Animation polish, AmbiSense, contextual reactions, and reliability |
| v0.3 | Lightweight care and progression |
| v0.4 | More behaviors, expressions, and personalization |
| v0.5 | Broader Linux desktop integration |

The roadmap is directional, not a release schedule.

## Assets and license

Mochi's runtime pixel art and audio are maintained in this repository. See the
[animation asset guide](assets/mochi/README.md) for asset conventions and
validation rules.

Mochi is released under the [MIT License](LICENSE).
