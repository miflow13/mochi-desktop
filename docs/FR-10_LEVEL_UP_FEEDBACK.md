# FR-10: Level Up Feedback

## Goal

Make a bond level-up feel meaningful, rewarding, and distinctly like Mochi rather than a generic game notification.

The MVP should communicate that Mochi's relationship with the user has changed, not merely that a number increased. A level-up should create both an immediate celebration and a permanent behavioral change.

## MVP

- [ ] **Dedicated level-up emote**
  - Plays once when a new bond level is reached.
  - Should feel celebratory and character-driven.
  - Must not loop indefinitely or replay from repeated/stale level state.
  - Returns cleanly to the appropriate post-emote state.

- [ ] **Level-specific Mochi line**
  - Each bond level can provide its own one-time level-up line.
  - The line should reflect increasing familiarity/comfort as the bond grows.
  - Displayed as part of the same level-up moment rather than as an unrelated ambient message.
  - Provide a safe fallback line for levels without authored copy.

- [ ] **Permanent interaction unlocks**
  - Reaching defined bond milestones can permanently unlock a new Mochi interaction.
  - Unlocked interactions remain available on future launches because they derive from persisted bond level, not transient UI state.
  - The MVP must prove at least one real bond-gated interaction unlock end-to-end.
  - Do not require a unique new interaction for every unbounded bond level; additional interactions can be attached to authored milestone levels over time.

- [ ] **Bond-tier phrase banks**
  - Mochi's ongoing dialogue/voice-line pool changes as the relationship grows.
  - Phrase selection should use the current bond range so higher-bond Mochi sounds more familiar, comfortable, and expressive.
  - Phrase-bank changes are permanent consequences of bond progression, not just level-up messages.
  - Higher tiers may retain selected earlier neutral lines where appropriate; progression should expand/evolve Mochi rather than abruptly replacing the entire personality.
  - Keep one-time level-up lines separate from recurring bond-tier phrase banks.

## Initial Phrase-Bank Ranges

These ranges are an initial authoring structure and can be tuned as the bond system develops:

- **Levels 1-2 — New / Curious**
  - Friendly, slightly tentative, getting-to-know-you energy.
- **Levels 3-4 — Familiar**
  - More recognition, comfort, and recurring-person energy.
- **Levels 5-7 — Comfortable**
  - More playful lines, stronger personality, gentle callbacks, less formality.
- **Levels 8-10 — Close**
  - Affectionate/familiar lines and more confident interaction with the user.
- **Levels 11+ — Deep Bond**
  - Long-term companion energy, rare special lines, and future milestone content.

The phrase selector should make these ranges data-driven so later ranges can be added without rewriting interaction logic.

## Feedback / Progression Flow

`bond level changes → level-up emote → level-specific line → apply any milestone unlocks → resume appropriate state`

Afterward:

`current bond level → unlocked interaction set + matching phrase bank`

## Design Principles

- Keep the level-up moment short and non-intrusive.
- Favor Mochi reacting over large game-like UI.
- A level-up should feel like Mochi noticed the relationship changing.
- Progress should make Mochi feel increasingly expressive rather than simply increasing a number.
- Permanent rewards should come from persisted bond state so they survive restarts naturally.
- Avoid blocking dialogs or interaction-heavy reward screens for the MVP.
- Do not retrigger the feedback for a level the user already reached.

## Out of Scope for MVP

Potential follow-up ideas, but not required for FR-10 MVP:

- Unlock/reward reveal UI
- Confetti or additional particle effects beyond existing bond feedback
- Level-up sound
- Persistent memory/keepsake entry
- Rare alternate level-up animations
- A unique interaction for every possible bond level

## QA Targets

- Level-up feedback fires exactly once per newly reached level.
- Correct authored level-up line appears for the reached level.
- Emote finishes and Mochi returns to the correct state.
- Bond-gated interaction becomes available at the intended milestone.
- Locked interactions remain unavailable below their required bond level.
- Unlocked interactions remain available after restarting Mochi.
- Correct recurring phrase bank is selected for the current bond range.
- Crossing a phrase-bank boundary uses the new bank without requiring a restart.
- Restarting Mochi does not replay an already acknowledged level-up.
- Repeated bond updates at the same level do not retrigger feedback.
- Existing idle, interaction, context-menu, drag/pickup, and bond behavior remain intact.
