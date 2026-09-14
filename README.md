# mochi 🌱

> ⚠️ **First install on GNOME Wayland**
>
> **Log out and back in once after installing Mochi.**
>
> This activates Mochi’s desktop-awareness helper for typing, app, file, and focused media reactions. Mochi will finish enabling it automatically after you sign back in.

*A tiny Deskling companion for Linux.*

[website](https://miflow13.github.io/mochi-desktop/) · [issues](https://github.com/miflow13/mochi-desktop/issues) · [animation guide](assets/mochi/README.md)

Mochi is a lightweight Linux desktop companion designed to make the desktop feel a little more alive. He wanders, reacts to clicks and dragging, notices broad desktop activity through **AmbiSense**, sleeps, chats, and mostly keeps to himself.

Mochi is currently an **early public alpha**. Fedora + GNOME on Wayland is the actively tested environment **(I plan to test on different setups, this is my first big application please be gentle)** ; XWayland is used where GNOME's native Wayland restrictions require it.

> Please note Mochi as an application is intentionally small feature wise. **There is no productivity score, streak, nagging assistant, or requirement to interact with him.**

---

## install

### Fedora + GNOME (Recommended Environment) 

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

The installer handles Fedora dependencies, creates Mochi's private Python environment, installs the GNOME helper, adds Mochi to the application grid, and installs `mochi` / `mochi-uninstall` launchers under `~/.local/bin`.

> [!NOTE]
> GNOME Wayland may require one logout/login after the first install before Mochi's desktop-awareness helper becomes active. You do not need to reinstall afterward.

### Fedora + Niri

The installer includes Fedora's `gtk4-layer-shell` package for Niri. After updating an existing installation, run `./install.sh` again and start Mochi once with:

```bash
mochi --reset-position
```

Niri support is still less extensively tested than Fedora + GNOME.

### run

Launch Mochi from the application grid or:

```bash
mochi
```

If `~/.local/bin` is not on your PATH:

```bash
~/.local/bin/mochi
```

### update

From the repository checkout:

```bash
git pull
./install.sh
```

Running the installer again refreshes Mochi's private environment, launchers, application entry, icon, and GNOME helper.

## typing / AmbiSense troubleshooting

Mochi's GNOME typing and desktop-awareness reactions depend on the GNOME Shell helper being active.

Check it with:

```bash
gnome-extensions info mochi-typing@miflow13 | grep State
```

You should see:

```text
State: ACTIVE
```

If the helper is installed but inactive, first **log out of GNOME and log back in once**. On a fresh GNOME Wayland install this is normally the only extra step required.

If it is still inactive afterward, try:

```bash
gnome-extensions enable mochi-typing@miflow13
```

Then launch Mochi again. If you recently updated the repository, also rerun:

```bash
git pull
./install.sh
```

### uninstall

```bash
~/.local/bin/mochi-uninstall
```

Remove saved settings too:

```bash
~/.local/bin/mochi-uninstall --purge
```

---

## current status

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — *Make Mochi Feel Alive*

Working now:

- idle / breathing + natural blink
- walking + persistent **Stay put**
- pickup, velocity-aware drag + drop
- bounce / squish / heart reactions
- click chirps + triple-click dialogue
- sleep / wake behavior
- typing + media companion states
- AmbiSense ambient dialogue
- multi-monitor / XWayland reliability work

Still growing:

- more ambient idle emotes
- animation-library polish
- broader Linux compatibility
- installation testing outside the dev machines
- more AmbiSense contexts

---

## known limitations !!

Mochi is an **alpha**, and the current support boundary is intentionally narrow while the interaction/state system is stabilized.

- **Fedora + GNOME + Wayland is the primary tested target.** Other Linux distributions may work, but automatic dependency installation currently supports Fedora only.
- **GNOME gets the fullest AmbiSense experience.** Typing, focused-app, file-browsing, and focused-media awareness rely on Mochi's GNOME Shell helper. On other desktops, Mochi can still run but desktop-awareness features may be reduced or unavailable.
- **A one-time GNOME logout/login may be required after first install.** GNOME may not load a newly installed Shell helper into the current session immediately.
- **Mochi uses XWayland for parts of desktop positioning and interaction on GNOME Wayland.** Compositor, monitor-layout, scaling, and workspace behavior can expose edge cases that do not appear on the primary development setup.
- **Workspace-switch reliability is still being watched.** An intermittent XWayland/workspace freeze was reported in [issue #45](https://github.com/miflow13/mochi-desktop/issues/45), but it has not been reproducible in the latest deliberate stress testing.
- **Niri support is experimental compared with GNOME.** The installer includes the required Fedora layer-shell package, but Niri does not yet receive the same breadth of regression testing.
- **Multi-monitor and fractional-scaling combinations are not exhaustively tested.** Please report the monitor layout and scale factors if placement, menus, bubbles, or dragging behave incorrectly.
- **No stable compatibility promise yet.** Alpha configuration, behavior, or installation details may change between prereleases.

If something fails quietly rather than crashing, that is still worth reporting. Ambient-awareness failures are intended to degrade gracefully, so missing reactions can be useful debugging information too.

---

## AmbiSense

"**AmbiSense**" (cool name huh?) is mochi's lightweight local awareness system. It turns privacy-reduced desktop signals into small behavior decisions: say something, react, perform an activity, or simply do nothing. 
This is achieved by using pulse detection logic within a Gnome Shell extension/plugin.
Basically:
```
GNOME Shell extension
→ sees keyboard activity
→ turns it into anonymous "Pulse"
→ sends Pulse over D-Bus
→ Mochi's Python side receives it
→ AmbiSense reacts
```

Depending on what is available on the system, Mochi can notice broad signals such as:

- anonymous typing activity and sustained typing intensity
- active vs. idle / returned presence
- coarse app categories such as editor, terminal, browser, media, or pixel-art software
- media playback
- battery / charging transitions
- network connection transitions
- file-browsing activity

> AmbiSense is a **local rule-based behavior engine**, NOT an LLM and not a cloud AI service.

### privacy

privacy comes first, so typing awareness is content-blind. Mochi does **NOT** store characters, inspect typed text, reconstruct words, log key values, or persist typing history. It uses **anonymous** activity timing and frequency only.

Application awareness is reduced to broad semantic categories before Mochi reacts. The goal is to notice the *shape* of desktop activity without reading your work.

---

## interactions

- **Left-click** — tactile bounce / squish + chirp
- **Three quick clicks** — occasional tiny dialogue
- **Double-click** — heart emote
- **Drag** — pick Mochi up and move him around
- **Right-click** — size, audio, sleep/wake, **Stay put**, and Quit
- **Stay put** — disables autonomous wandering without freezing other behavior
- **Mochi Lab** — developer controls for animations and AmbiSense tuning

Nothing requires a response. You can ignore Mochi completely and let him do his little thing.

---

## why Mochi?

Desktop pets already exist. i built mochi as an experiment in making one feel **native to the Linux desktop, expressive, context-aware, and pleasant to actually leave running** while being cute, polished and easy to use

Most of the work is in the small details: animation timing, squash and stretch, cursor reactions, movement, persistence, speech pacing, state transitions, and knowing when not to interrupt.

---

## art

ALL Mochi pixel art, animations, and audio are created by me.

The sprites are handcrafted frame by frame using [Pixelorama](https://github.com/orama-interactive/pixelorama) with attention to silhouette, timing, squash and stretch, and the tiny expressions that make Mochi feel alive.

Runtime artwork lives under `assets/mochi/` and is defined by `assets/mochi/manifest.json`.

See [`assets/mochi/README.md`](assets/mochi/README.md) for frame, naming, looping, export, and validation rules.


---

## engineering

Mochi is also a hands-on Linux software-engineering project. Current work includes:

- state-driven behavior for idle, movement, reactions, sleep, media, typing, and interaction transitions
- privacy-first event and context handling through AmbiSense
- manifest-driven sprite assets with runtime inventory validation
- per-frame animation timing with cached Cairo surfaces and nearest-neighbor rendering
- persistent configuration for placement and preferences
- GTK4 transparent desktop integration
- GNOME Wayland + XWayland compatibility work around positioning, input, menus, and multiple monitors
- D-Bus / event-driven system awareness where appropriate
- automated regression tests around interaction and animation behavior

### stack

Python 3 · GTK4 / PyGObject · Cairo · GNOME Shell helper · XWayland

The actively tested target is **Fedora Linux + GNOME + Wayland**. Other distributions may work, but they are not yet part of the supported one-command installation path.

---

## roadmap

| version | focus |
| --- | --- |
| **v0.1 — Exists** | core desktop buddy functionality |
| **v0.2 — Feels alive** | animation polish, AmbiSense, reactions, contextual behavior, reliability, public alpha |
| **v0.3 — Needs care** | lightweight care / progression without turning Mochi into a chore |
| **v0.4 — Develops personality** | more behaviors, expressions, traits, and cosmetic personality |
| **v0.5 — Lives on your desktop** | deeper Linux desktop interactions and broader environment support |

The roadmap is directional rather than a promise. Interaction quality comes first.

---

## reporting bugs

Bug reports are especially useful during the alpha. Open an issue at [GitHub Issues](https://github.com/miflow13/mochi-desktop/issues) and include as much of the following as you can:

- what you were doing immediately before the problem
- what you expected Mochi to do
- what Mochi actually did
- whether the problem is reproducible and the shortest sequence that reproduces it
- Fedora / distribution version
- desktop environment and session type
- number of monitors, layout, and scale factors if positioning is involved
- whether Mochi had just been clicked, dragged, put to sleep, switched between workspaces, or entered an AmbiSense state
- relevant terminal output or traceback

Useful environment checks:

```bash
echo "$XDG_CURRENT_DESKTOP"
echo "$XDG_SESSION_TYPE"
gnome-extensions info mochi-typing@miflow13 | grep State
```

For runtime debugging, launch Mochi from a terminal with:

```bash
mochi --debug
```

For intermittent interaction bugs, please capture the exact sequence immediately before the failure. A short reproducible sequence is more useful than a large log with no surrounding context.

---

## development

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
python -m pytest
mochi --debug
```

**Mochi Lab** can be opened with `Ctrl + Alt + Shift + M` when the GNOME helper is active.

Mochi is developed with the assistance of coding agents for implementation, debugging, code review, and investigation. I direct the architecture, product decisions, testing, releases, and overall development process.

---

## feedback

Bug reports, Linux compatibility notes, animation feedback, and feature ideas are welcome through [GitHub Issues](https://github.com/miflow13/mochi-desktop/issues).

If Mochi makes your desktop a little nicer, starring the repository helps other Linux users find him. 💚

MIT licensed.
