# Mochi 🌱
>⚠️ **First install on GNOME Wayland**
>
> **Log out and back in once after installing Mochi.**
>
> This activates Mochi’s desktop-awareness helper for typing, app, file, and focused media reactions. Mochi will finish enabling it automatically after you sign back in.
*A tiny Deskling companion for Linux.*

[website](https://miflow13.github.io/mochi-desktop/) · [issues](https://github.com/miflow13/mochi-desktop/issues) · [animation guide](assets/mochi/README.md)

Mochi is a lightweight Linux desktop companion designed to make the desktop feel a little more alive. He wanders, reacts to clicks and dragging, notices broad desktop activity through **Mochi Sense**, sleeps, chats, and mostly keeps to himself.

Mochi is currently an **early public alpha**. Fedora + GNOME on Wayland is the actively tested environment; XWayland is used where GNOME's native Wayland restrictions require it.

> Mochi is intentionally small. There is no productivity score, streak, nagging assistant, or requirement to interact with him.

---

## install

### Fedora + GNOME

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

The installer handles Fedora dependencies, creates Mochi's private Python environment, installs the GNOME helper, and adds Mochi to the application grid.

> [!NOTE]
> GNOME Wayland may require one logout/login after the first install before Mochi's desktop-awareness helper becomes active.

### Fedora + Niri

The installer includes Fedora's `gtk4-layer-shell` package for Niri. After updating an existing installation, run `./install.sh` again and start Mochi once with:

```bash
mochi --reset-position
```

### run

Launch Mochi from the application grid or:

```bash
mochi
```

If `~/.local/bin` is not on your PATH:

```bash
~/.local/bin/mochi
```
## Why isn't Mochi typing when I type?

Mochi's typing reactions depend on the GNOME Shell helper being enabled.

If typing reactions are not working, try enabling the extension manually:

```bash
gnome-extensions enable mochi-typing@miflow13
```

```
git pull
./install.sh
```
Then verify that it is active:

`gnome-extensions info mochi-typing@miflow13 | grep State`

You should see:

`State: ACTIVE`

> 💡 On a fresh GNOME Wayland install, you may need to log out and back in once before the extension can be enabled.

---

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
- Mochi Sense ambient dialogue
- multi-monitor / XWayland reliability work

Still growing:

- more ambient idle emotes
- animation-library polish
- broader Linux compatibility
- installation testing outside the dev machines
- more Mochi Sense contexts

---

## Mochi Sense

**Mochi Sense** is Mochi's lightweight local awareness system. It turns privacy-reduced desktop signals into small behavior decisions: say something, react, perform an activity, or simply do nothing.

Depending on what is available on the system, Mochi can notice broad signals such as:

- anonymous typing activity and sustained typing intensity
- active vs. idle / returned presence
- coarse app categories such as editor, terminal, browser, media, or pixel-art software
- media playback
- battery / charging transitions
- network connection transitions
- file-browsing activity

Mochi Sense is a **local rule-based behavior engine**, not an LLM and not a cloud AI service.

### privacy

Typing awareness is content-blind. Mochi does **not** store characters, inspect typed text, reconstruct words, log key values, or persist typing history. It uses anonymous activity timing and frequency only.

Application awareness is reduced to broad semantic categories before Mochi reacts. The goal is to notice the *shape* of desktop activity without reading your work.

---

## interactions

- **Left-click** — tactile bounce / squish + chirp
- **Three quick clicks** — occasional tiny dialogue
- **Double-click** — heart emote
- **Drag** — pick Mochi up and move him around
- **Right-click** — size, audio, sleep/wake, **Stay put**, and Quit
- **Stay put** — disables autonomous wandering without freezing other behavior
- **Mochi Lab** — developer controls for animations and Mochi Sense tuning

Nothing requires a response. You can ignore Mochi completely and let him do his little thing.

---

## why Mochi?

Desktop pets already exist. Mochi is an experiment in making one feel **native to the Linux desktop, expressive, context-aware, and pleasant to actually leave running**.

Most of the work is in the small details: animation timing, squash and stretch, cursor reactions, movement, persistence, speech pacing, state transitions, and knowing when not to interrupt.

---

## art

All Mochi pixel art, animations, and audio are created by me.

The sprites are handcrafted frame by frame with attention to silhouette, timing, squash and stretch, and the tiny expressions that make Mochi feel alive.

Runtime artwork lives under `assets/mochi/` and is defined by `assets/mochi/manifest.json`.

See [`assets/mochi/README.md`](assets/mochi/README.md) for frame, naming, looping, export, and validation rules.

---

## engineering

Mochi is also a hands-on Linux software-engineering project. Current work includes:

- state-driven behavior for idle, movement, reactions, sleep, media, typing, and interaction transitions
- privacy-first event and context handling through Mochi Sense
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
| **v0.2 — Feels alive** | animation polish, Mochi Sense, reactions, contextual behavior, reliability, public alpha |
| **v0.3 — Needs care** | lightweight care / progression without turning Mochi into a chore |
| **v0.4 — Develops personality** | more behaviors, expressions, traits, and cosmetic personality |
| **v0.5 — Lives on your desktop** | deeper Linux desktop interactions and broader environment support |

The roadmap is directional rather than a promise. Interaction quality comes first.

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
