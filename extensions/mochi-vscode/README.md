# Mochi for VS Code 🌱

A little company while you build. Mochi lives in your sidebar, using the same original pixel artwork and animation language as [Mochi Desktop](https://github.com/miflow13/mochi-desktop).

## What v1 does

- Quiet breathing and occasional blinking.
- Click Mochi or select **Pet** for a little heart reaction.
- Drag him around his panel, with pickup, directional sway, settling and drop poses.
- Put him to sleep and wake him up. Placement and sleep preference survive reopening VS Code.
- Optionally let him type alongside you. This uses edit activity only, never your code or filenames.
- Respect system reduced motion, with an additional extension setting.

Mochi stays inside his sidebar panel. This extension runs independently of the Linux desktop app on desktop VS Code; it does not connect to GTK or require Mochi Desktop to be installed. Voice chat is not part of v1.

## Install

Download the VSIX from the **Mochi VS Code** GitHub Actions artifact after a successful workflow run. Extract the artifact, then in VS Code run **Extensions: Install from VSIX…** and select `mochi-vscode-1.0.0.vsix`.

Open the Mochi activity-bar icon or run **Mochi: Show**. The command palette also offers **Mochi: Pet**, **Mochi: Sleep / Wake**, and **Mochi: Reset Position**.

No Marketplace publication has been performed. The package uses `miflow13` as its local extension identity; Marketplace publisher ownership must be checked before any future publication.

## Settings

| Setting | Default | Behavior |
|---|---|---|
| `mochi.size` | `160` | Sprite canvas size, from 96 to 256 logical pixels; shrinks to fit narrow panels. |
| `mochi.typingReactions` | `false` | Animate on edits to the active text document. No document content is transmitted. |
| `mochi.reducedMotion` | `false` | Use still poses. System reduced-motion preference also enables this. |

Press **Enter** or **Space** on the focused pet canvas to pet him. Buttons also support normal keyboard navigation. The extension makes no network requests, reads no workspace files, and requests no microphone access. It does load its own bundled assets. Preference state is stored using VS Code globalState.

## Develop

From the **repository checkout**, with Node.js 22+:

```sh
cd extensions/mochi-vscode
npm ci
npm run build
npm test
npm run check
npm run package
```

`npm run build` reads `../../assets/mochi/manifest.json`, the source PNGs, and the runtime timing overrides in `../../src/mochi/`. It copies only the required original PNGs into `media/mochi/`. Generated assets are ignored by Git and included in the VSIX. No duplicate art source is maintained in this extension.

Open `extensions/mochi-vscode/` as a folder in VS Code and press **F5** using **Run Mochi extension** to launch the Extension Development Host. The prelaunch task builds the assets. This implementation uses plain JavaScript with no compilation step and no runtime npm dependencies.

Optional real-browser interaction checks:

```sh
npx playwright install chromium
npm run test:browser
```

See [MANUAL-QA.md](MANUAL-QA.md) for the live Extension Host checklist. The default test suite includes a Canvas adapter using real PNG decoding for rendering, pointer cancellation and lifecycle checks. Browser automation covers the rendered webview with a small VS Code message adapter; it does not replace live VS Code verification.

## Artwork consistency

The source of truth is the [artist kit](../../artist-kit/README.md), [master pose](../../assets/mochi/master/mochi_default.png), and [runtime manifest](../../assets/mochi/manifest.json). The build checks frame dimensions and copies byte-identical PNGs. Rendering uses nearest-neighbor scaling and a bottom-center character anchor. Per-frame timing overrides for breathing, blink, tactile and sleep transitions are read from the desktop runtime; directional drag poses are selected semantically instead of looped.

Design: [v1 spec](../../docs/superpowers/specs/2026-10-04-mochi-vscode-v1.md).

MIT license; original Mochi artwork and code retain the repository's attribution.
