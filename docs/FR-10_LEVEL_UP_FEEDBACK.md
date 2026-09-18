# FR-10: Level Up Feedback

## Goal

Make a bond level-up feel meaningful, rewarding, and distinctly like Mochi rather than a generic game notification.

The MVP should communicate that Mochi's relationship with the user has changed, not merely that a number increased.

## MVP

- [ ] **Dedicated level-up emote**
  - Plays once when a new bond level is reached.
  - Should feel celebratory and character-driven.
  - Must not loop indefinitely or replay from repeated/stale level state.
  - Returns cleanly to the appropriate post-emote state.

- [ ] **Level-specific Mochi line**
  - Each bond level can provide its own line of dialogue.
  - The line should reflect increasing familiarity/comfort as the bond grows.
  - Displayed as part of the same level-up moment rather than as an unrelated ambient message.
  - Provide a safe fallback line for levels without authored copy.

## Initial Feedback Flow

`bond level changes → level-up emote → level-specific line → resume appropriate state`

## Design Principles

- Keep the moment short and non-intrusive.
- Favor Mochi reacting over large game-like UI.
- A level-up should feel like Mochi noticed the relationship changing.
- Avoid blocking dialogs or interaction-heavy reward screens for the MVP.
- Do not retrigger the feedback for a level the user already reached.

## Out of Scope for MVP

Potential follow-up ideas, but not required for FR-10 MVP:

- Unlock/reward reveal UI
- Confetti or particle effects
- Level-up sound
- Persistent memory/keepsake entry
- Rare alternate level-up animations
- Expanded unlock systems

## QA Targets

- Level-up feedback fires exactly once per newly reached level.
- Correct authored line appears for the reached level.
- Emote finishes and Mochi returns to the correct state.
- Restarting Mochi does not replay an already acknowledged level-up.
- Repeated bond updates at the same level do not retrigger feedback.
- Existing idle, interaction, context-menu, drag/pickup, and bond behavior remain intact.
