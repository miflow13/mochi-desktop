# FR-11: Bond Phases & Relationship Dialogue

## Purpose

Bond phase describes how familiar Mochi is with the user. It is derived from
the existing persistent bond level and changes dialogue only; it does not alter
XP, care, emotes, or mood.

## Phases

| Levels | Phase | Relationship tone |
| --- | --- | --- |
| 1–2 | New | Curious and playful |
| 3–4 | Familiar | Recognizes the user's routine |
| 5–7 | Comfortable | Relaxed, warm companionship |
| 8–10 | Close | Trusted desktop-companion familiarity |
| 11+ | Deep Bond | Long-established, restrained warmth |

Invalid or low levels safely resolve to New.

## Dialogue rules

- Triple-click is the MVP relationship-dialogue interaction.
- Lines unlock at exact levels and accumulate only within the current phase.
- When a phase changes, older phase-specific relationship lines are not
  selected, so the relationship voice does not regress.
- AmbiSense contextual categories remain independent and can still speak at
  any bond level.
- Mood remains a separate interpretation of current activity/emotion; it is
  never used as a bond phase.

## Writing principles

Relationship dialogue is short, warm, playful, and non-punitive. It does not
guilt the user for leaving, imply dependency or exclusivity, claim private
knowledge, or use romantic framing.

## Extension seam

`BondPhase` and `bond_phase_for_level()` own phase classification. The
immutable `BondDialogueLine` data set owns exact-level dialogue availability,
so future bond-aware behavior can reuse the same phase model without changing
progression or AmbiSense selection.
