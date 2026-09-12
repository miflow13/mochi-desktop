# Mochi Overlay — Figma Design Spec

## Source

Measurements below were read from the supplied Figma inspection screenshots.
Where a value is inferred rather than directly visible, it is explicitly marked.

---

## Main full overlay

### Overall footprint

- Full/default family wrapper: **220 × 72 px**
- Rounded panel inside wrapper: **220 × 64 px**
- The additional vertical footprint is associated with the speech-bubble tail /
  attachment area.

### Panel

- Width: **220 px**
- Height: **64 px**
- Auto-layout gap: **4 px**
- Horizontal padding: **12 px**
- Vertical padding: **8 px**
- Corner radius: **14 px**
- Fill: **#FFF8F0**
- Stroke: **#3D2B3A**
- Stroke width: **2 px**
- Opacity: **100%**

### Shadow

Observed in Figma:

- Drop shadow offset X: **0**
- Drop shadow offset Y: **4**
- Blur: **0**
- Spread: **0**

Use the exported reference for shadow color/visual weight if the exact shadow
color is not available in GTK styling.

---

## Name typography

The supplied Figma typography inspection shows:

- Font family: **Rubik**
- Style/weight: **ExtraBold**
- Size: **14 px**
- Text fill: **#4D384A**
- Text box observed: **43 × 17 px** for `Mochi`

Do not silently substitute a dramatically different typeface. If Rubik is not
available in the runtime environment, use the nearest project-approved fallback
and document the compromise.

---

## Known component variants

Observed in the Figma component set:

- **Full / Default**
- **Compact**
- **Minimal**
- **Hungry**
- **Low Health**
- **Extra Happy**
- **Sleeping**
- **Level Up**

Observed sizes:

- Full/default-style state family: **220 × 72 px**
- Compact: **180 × 44 px**
- Minimal: **144 × ~52.36 px** (export may round to 53 px)
- Reusable standalone status modules: **80 × 48 px**

Treat the PNG exports as the visual source of truth for the internal composition
of each variant.

---

## Reusable status module

Observed from the selected status module:

- Width: **80 px**
- Height: **48 px**
- Auto-layout gap: **2 px**
- Padding: **6 px**
- Corner radius: **8 px**
- Fill: **#FFF8F0**

The happiness module selection exposes the following design colors:

- Primary dark text: **#4D384A**
- Happiness green: **#72EF9F**
- Border/dark outline: **#3D2B3A**
- Warm neutral track/background: approximately **#EADDC9**
- Panel cream: **#FFF8F0**

Use the exports rather than guessing any colors not explicitly documented here.

---

## Layout intent

The overlay:

- floats directly above Mochi
- uses a speech-bubble-style tail pointing toward the character
- is compact relative to the sprite
- should feel like game UI rather than a desktop application card
- should not permanently dominate the desktop

The desktop mockup and exported full system sheet should be consulted before
final visual tuning.

---

## Runtime scaling

The existing Mochi renderer uses a fixed 128 × 128 sprite canvas. Do not assume
that Figma pixels automatically equal device pixels in every GTK scaling context.

Preserve the Figma proportions first, then account for:

- GTK scale factor
- Mochi's configured display scale
- Wayland/X11 behavior

Do not use filtering that softens the pixel-art sprite.
