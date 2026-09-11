
<div align="center">

# Mochi 🌱

> [!WARNING]
> Mochi is developed with the assistance of coding agents for implementation, debugging, code review, and investigation. I direct the architecture, product decisions, testing, releases, and overall development process.

All Mochi pixel art, animations, and audio are created by me.



### A tiny Deskling companion for Linux

<img width="2370" height="1782" alt="mochi-article-banner-upscaled" src="https://github.com/user-attachments/assets/5fe458e3-22fe-4575-92ee-6b2fdc53f39e" />

**A handcrafted pixel-art companion who wanders, reacts, chats, sleeps, and quietly lives on your desktop.**

</div>

Mochi is a lightweight Linux desktop companion built to make the desktop feel a little more alive. He responds to clicks and dragging, wanders when he feels like it, notices broad desktop activity through **Mochi Sense**, and occasionally has something small to say.

Mochi is currently available as an **early public alpha**. Fedora + GNOME on Wayland is the actively tested environment; Mochi uses XWayland where GNOME's native Wayland restrictions require it.

<table>
<tr>
<td>


</td>
<td width="80" align="center">
<img width="64" height="64" alt="fedora_mode_loop" src="https://github.com/user-attachments/assets/62b496da-69f8-4f7f-ab58-f09eb1d1874e" />
</td>
</tr>
</table>

### ⌨️ Types when you type

Mochi quietly joins in while you’re typing.

<p align="center">
  <img
    width="820"
    alt="Mochi typing alongside the user"
    src="https://github.com/user-attachments/assets/785ff1f5-d154-454a-896b-fec6e3664a40"
  />
</p>

<p align="center">
  <sub>Just a little typing buddy. 🌱</sub>
</p>

### 💬 Little observations

Mochi pays attention to what’s happening around your desktop and occasionally shares a small thought of its own.

<p align="center">
  <img
    width="820"
    alt="Mochi reacting to what is on screen"
    src="https://github.com/user-attachments/assets/d830ab6f-be30-47ba-86ae-63d46bd0c23c"

  />
</p>

<p align="center">
  <sub>Little observations, quiet company. 🌱</sub>
</p>




---

## Install Mochi
<img width="1280" height="803" alt="hellofrommochi" src="https://github.com/user-attachments/assets/d7cb090d-5fae-4315-8b10-d809eda3da39" />


### Recommended: Fedora + GNOME

Clone the repository and run the installer:

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
./install.sh
```

The installer checks/installs Mochi's Fedora dependencies, creates a private Python environment under your user account, installs the GNOME helper, and adds **Mochi** to the GNOME application grid.

The repository checkout is not required to *run* Mochi after installation.

> [!NOTE]
> GNOME Wayland may require one logout/login after the first install before Mochi's desktop-awareness helper becomes active. The installer will tell you if that is needed.

### Fedora + Niri

Niri uses Wayland layer-shell for explicitly positioned desktop surfaces. The
installer includes Fedora's `gtk4-layer-shell` package so Mochi can use that
path. After updating an existing installation, run `./install.sh` again and
start Mochi with `mochi --reset-position` once to discard coordinates saved
under another desktop layout.

### Open Mochi

Search for **Mochi** in the GNOME app grid and launch him like a normal application.

You can also launch from a terminal:

```bash
mochi
```

If `~/.local/bin` is not on your shell PATH, use:

```bash
~/.local/bin/mochi
```

### Close Mochi

Right-click Mochi and choose **Quit Mochi**.

### Update Mochi

From your repository checkout:

```bash
git pull
./install.sh
```

Running the installer again replaces the private installed environment with the current checkout while preserving Mochi's user settings.

### Uninstall Mochi

After installation, you can uninstall without keeping the repository:

```bash
~/.local/bin/mochi-uninstall
```

Mochi's saved settings are preserved by default. To remove those too:

```bash
~/.local/bin/mochi-uninstall --purge
```

---

<h2><img width="48" height="48" alt="Mochi being picked up" src="https://github.com/user-attachments/assets/dee6a7c8-2f70-475a-ae3b-74f1b959dbc6" /> Current Status</h2>

**Version:** `0.2.0-alpha`  
**Stage:** Phase 2 — *Make Mochi Feel Alive*

| Working now | Still growing |
| --- | --- |
| ✅ Idle / breathing + natural blink | 🌱 More ambient idle emotes |
| ✅ Walking + persistent Stay put | 🌱 Animation-library polish |
| ✅ Pickup, velocity-aware drag + drop | 🌱 Broader Linux compatibility |
| ✅ Bounce / squish / heart reactions | 🌱 Installation testing outside the dev machines |
| ✅ Click chirps + playful triple-click dialogue | 🌱 More Mochi Sense contexts |
| ✅ Sleep / wake behavior | |
| ✅ Typing + media companion states | |
| ✅ Mochi Sense ambient dialogue | |
| ✅ Multi-monitor/XWayland reliability work | |

<p align="center">
  <img width="738" height="592" alt="Mochi desktop demo" src="https://github.com/user-attachments/assets/79e7eb9b-8c14-4c22-86eb-fc7ea9878451" />
</p>

---

## Why Mochi?

Desktop pets already exist. Mochi is an experiment in making one feel **native to the Linux desktop, expressive, context-aware, and pleasant to actually leave running**.

The project focuses heavily on the tiny interaction details that create that feeling: animation timing, squash and stretch, cursor reactions, movement, persistence, speech pacing, state transitions, and knowing when not to interrupt.

Mochi is intentionally small. There is no productivity score, streak, nagging assistant, or requirement to interact with him.

---

## Mochi Sense 🌱

**Mochi Sense** is Mochi's lightweight local awareness system. It turns privacy-reduced desktop signals into small behavior decisions: say something, react, perform an activity, or simply do nothing.

Depending on what is available on the system, Mochi can notice broad signals such as:

- anonymous typing activity and sustained typing intensity
- active vs. idle/returned presence
- coarse application categories such as editor, terminal, browser, media, or pixel-art software
- media playback
- battery/charging transitions
- network connection transitions
- file-browsing activity

Mochi Sense is a **local rule-based behavior engine**, not an LLM and not a cloud AI service.

### Privacy

Mochi's typing awareness is deliberately content-blind. It does **not** store characters, inspect typed text, reconstruct words, log key values, or persist typing history. The system uses anonymous activity timing/frequency only.

Application awareness is similarly reduced to broad semantic categories before Mochi reacts. The goal is for Mochi to notice the *shape* of desktop activity without reading your work.

---

## Handcrafted With Love

<div align="center">

<img width="800" alt="Mochi animation being handcrafted in Pixelorama" src="https://github.com/user-attachments/assets/8c3492d7-7be7-4d9a-9a0d-9028dd75154b" />

*Every pixel. Every frame. A little bit of personality.*

</div>

Mochi's sprites and animations are **handcrafted frame by frame** with attention to silhouette, timing, squash and stretch, and the tiny expressions that make him feel alive.

The runtime animation library is manifest-driven and validated by tests so artwork can evolve without silently leaving stale assets behind.

---

## Interactions

Mochi currently supports a small set of direct and ambient interactions:

- **Left-click** — tactile bounce/squish reaction + chirp
- **Three quick left-clicks** — Mochi may object with a tiny speech bubble
- **Double-click** — heart emote
- **Drag** — pick Mochi up and move him around; he may say `wheee!`
- **Right-click** — user controls including size, audio, sleep/wake, **Stay put**, and Quit
- **Stay put** — disables autonomous wandering without freezing Mochi's other behavior
- **Mochi Lab** — developer/testing controls for animation and Mochi Sense tuning

Nothing requires a response. You can ignore Mochi completely and let him do his little thing.

---

## Engineering Highlights

Mochi is also a hands-on Linux software-engineering project. Current work includes:

- **State-driven behavior** for idle, movement, reactions, sleep, media, typing, and interaction transitions
- **Mochi Sense**, a privacy-first event/context decision system
- **Manifest-driven sprite assets** with runtime inventory validation
- **Per-frame animation timing** with cached Cairo surfaces and nearest-neighbor rendering
- **Persistent configuration** for placement and user preferences
- **GTK4 desktop integration** with transparent companion windows
- **GNOME Wayland + XWayland compatibility work** around positioning, input, menus, and multiple monitors
- **DBus/event-driven system awareness** where appropriate instead of expensive polling
- **Automated regression tests** around interaction and animation behavior

---

## Tech Stack & Support

The actively tested target is **Fedora Linux + GNOME + Wayland**.

Mochi is built with:

- Python 3
- GTK4 / PyGObject
- Cairo
- GNOME Shell helper extension
- XWayland where GNOME's Wayland restrictions require desktop-window functionality

The current `install.sh` automates dependencies on Fedora. Other distributions may work, but they are not yet part of the supported one-command installation path.

---

## Animation Library

Runtime artwork lives under `assets/mochi/` and is defined by `assets/mochi/manifest.json`. The manifest is the source of truth for production animation frames.

See [`assets/mochi/README.md`](assets/mochi/README.md) for the frame, naming, looping, export, and validation rules used when adding or replacing an emote.

---

## Roadmap

| Version | Focus |
| --- | --- |
| **v0.1 — Exists** | Core desktop buddy functionality |
| **v0.2 — Feels alive** | Animation polish, Mochi Sense, reactions, contextual behavior, reliability, and public alpha |
| **v0.3 — Needs care** | Explore lightweight care/progression mechanics without turning Mochi into a chore |
| **v0.4 — Develops personality** | More behaviors, expressions, traits, and cosmetic personality |
| **v0.5 — Lives on your desktop** | Deeper Linux desktop interactions and broader environment support |

The roadmap is directional rather than a promise; Mochi's core interaction quality comes first.

---

## Development

For development, clone the repository and use a system-site-packages virtual environment so Fedora's PyGObject installation remains visible:

```bash
git clone https://github.com/miflow13/mochi-desktop.git
cd mochi-desktop
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
python -m pytest
mochi --debug
```

The private developer window, **Mochi Lab**, can be opened with `Ctrl + Alt + Shift + M` when the GNOME helper is active.

---

## Contributing & Feedback

Mochi is early-stage software. Bug reports, Linux compatibility notes, animation feedback, and feature ideas are welcome through [GitHub Issues](https://github.com/miflow13/mochi-desktop/issues).

If Mochi makes your desktop a little nicer, starring the repository helps other Linux users find him. 💚

Licensed under the **MIT License**.
