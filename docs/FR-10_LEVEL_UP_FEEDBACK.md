# FR-10: Level Up Feedback

## Goal

Make the moment of a bond level-up feel satisfying, readable, and distinctly like Mochi.

This branch is presentation-only. It does not add new bond progression rules, permanent unlocks, phrase-bank progression, or other gameplay consequences.

## MVP

- [x] **Dedicated level-up emote**
  - Plays once when a new bond level is reached.
  - Should feel celebratory and character-driven.
  - Must not loop indefinitely or replay from repeated/stale level state.
  - Returns cleanly to the appropriate post-emote state.
  - Uses the authored 16-frame default celebration unless a future legendary level-up explicitly supersedes it.

- [ ] **Immediate level-up line**
  - Show a short Mochi line as part of the level-up moment.
  - The line is presentation feedback only; recurring bond-tier phrase banks are not part of this branch.
  - Keep the treatment visually integrated with Mochi rather than using a blocking dialog.

- [ ] **Polished visual timing**
  - Coordinate the existing level-up bloom, emote, and line so they read as one intentional sequence.
  - Avoid overlapping feedback that makes the moment noisy or difficult to read.
  - Keep the total moment short and non-intrusive.

## Feedback Flow

`bond level changes → visual bloom → default/legendary level-up emote → short line/card → optional emote-unlock card → perform the newly learned emote once → resume appropriate state`

The exact overlap/timing between bloom, emote, and line can be tuned during implementation to produce the best visual feel.

## Design Principles

- Mochi should appear to react to the level-up, not merely display a system notification.
- Keep the feedback compact enough that it does not interrupt normal desktop use.
- Favor character animation and subtle in-world feedback over large game-like UI.
- The visual hierarchy should make the level-up immediately noticeable without becoming flashy or noisy.
- Reuse the existing state/animation systems rather than creating a parallel feedback system.
- Do not alter the underlying bond progression model as part of FR-10.

## Explicitly Out of Scope

These ideas remain valid for later bond-system work, but are not part of this branch:

- Permanent interaction unlocks
- Bond-tier phrase banks
- New recurring voice-line pools
- Reward/unlock reveal UI
- Changes to bond XP or level progression
- Persistent keepsakes or memory entries
- New care mechanics
- A unique reward for every level
- Rare alternate level-up animations
- Level-up sound unless it becomes necessary for visual timing QA

## QA Targets

- A real level-up triggers the visual feedback once.
- The default level-up animation plays once before the level-up card.
- A newly unlocked emote performs one automatic demonstration pass after its unlock card.
- The bloom, emote, and line feel like one coherent sequence.
- The emote finishes and Mochi returns to the correct prior/idle behavior.
- Repeated bond updates at the same level do not replay the level-up feedback.
- Restarting Mochi does not incorrectly replay an already-seen level-up.
- Existing idle, interaction, context-menu, drag/pickup, and bond behavior remain intact.
- No bond XP thresholds, progression rates, or permanent behavior unlocks change in this branch.
