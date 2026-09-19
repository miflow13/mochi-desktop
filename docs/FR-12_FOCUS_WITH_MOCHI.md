# FR-12 — Focus With Mochi

## Goal

Turn Mochi into a gentle study/work companion without turning the desktop pet
into a productivity coach.

The interaction should feel like spending focused time with Mochi:

right-click Mochi → Focus with Mochi → configure a session → work together →
take a break → earn bond XP for focused time.

## MVP

- Adjustable focus duration: 5–120 minutes.
- Adjustable break duration: 1–30 minutes.
- Adjustable rounds: 1–8.
- Optional gentle encouragement.
- A compact timer window that may be hidden while the session continues.
- Mochi uses the dedicated low-energy writing loop while the focus block is active.
- Breaks return Mochi to normal behavior.
- Pause/resume and stop are non-punitive.
- Focus time earns 1 bond XP per completed focus minute.
- Completing the whole configured session grants one +10 bond XP completion bonus.
- Break time does not earn XP.
- Existing FR-10 level-up behavior remains authoritative if focus XP crosses a level boundary.

## Character behavior

Opening the right-click menu or setup window starts Mochi's dedicated thinking
loop. The loop continues without restarting while moving from the menu into
setup. Closing both surfaces returns Mochi to ordinary behavior, while starting
a session plays the authored thinking exit before the writing sequence begins.

During a live focus block Mochi settles into the dedicated looping writing
animation. The authored `focus_start`, `focus_loop`, and `focus_stop` phases are
still a session mode layered over the existing behavior architecture rather
than a new competing animation controller.

Direct interaction may temporarily interrupt the visual. Focus time continues,
and Mochi resumes working when the ordinary interaction returns to idle.

Automatic sleep is deferred while an unpaused focus block is active. Choosing
Sleep manually pauses the focus session first.

## Encouragement

Encouragement is intentionally sparse: two candidate moments per focus block,
at roughly 35% and 72% completion.

Lines come from the existing deterministic Focus phrase category and reuse the
existing speech bubble. They do not create a second dialogue engine.

Speech-disabled and Quiet Mode configurations remain respected.

## Reward rules

Focus rewards are relationship progress, not a score.

- +1 bond XP per completed focus minute.
- +10 bond XP once when the full multi-round session completes.
- No XP for breaks.
- No penalty for pausing.
- No penalty for stopping early.
- Already-earned whole-minute XP is kept when stopping early.
- No streaks, failure states, missed-session penalties, or daily obligations.

## State ownership

Focus does not introduce a new MochiState.

The active work visual deliberately reuses MochiState.COMPUTER with the
focus-specific writing animation. The focus-session clock is separate from
behavioral animation state, allowing click, drag, feed, level-up presentation,
and similar temporary interactions to occur without destroying the timer.

## Audio follow-up

Nature sounds and focus soundscapes are intentionally not bundled in this first
slice because the repository does not currently contain approved looping focus
audio assets.

The follow-up should add optional local soundscapes through a separate
long-running audio channel from Mochi's short interaction sounds. It must remain
fully local, optional, independently volume-controlled, and safe when an audio
backend or asset is unavailable.

Approved `.ogg` or `.wav` loops can be added to `assets/audio/focus/` later.
No soundscape chooser is shown until at least one approved asset is present.
The supplied `mochi_rain.wav` enables a Rain sounds toggle and independent
volume control in setup and during a live session.

## QA

Verify on Fedora/GNOME/Wayland/XWayland:

- Focus with Mochi opens from right-click.
- Mochi thinks while the right-click menu is open and exits cleanly when it closes.
- Mochi thinks while the setup window is open and exits cleanly when it closes.
- Setup values are adjustable.
- Starting transitions from thinking into the looping writing animation.
- Closing the timer window does not stop the session.
- Reopening Focus with Mochi returns to the live timer.
- Pause freezes time and XP.
- Resume restarts the work visual.
- Stop keeps already-earned XP and gives no completion bonus.
- Breaks give no XP.
- Completing all rounds gives the completion bonus exactly once.
- Click/drag/feed interactions recover back into the work visual.
- Right-click/context menu remains reliable during a session.
- Level-up presentation remains coherent if focus XP crosses a threshold.
- Manual Sleep pauses the focus session.
- Application shutdown removes the timer source and persists pending XP.
