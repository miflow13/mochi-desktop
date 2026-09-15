# AmbiSense

**AmbiSense** is Mochi's lightweight local ambient-awareness system.

It turns privacy-reduced desktop signals into small behavior decisions without reading the content of what the user types. The implementation continues to use `presence` internally (`PresenceEngine`, `PresenceBuddyMixin`, and related modules); **AmbiSense** is the user-facing subsystem name.

## Event flow

On GNOME, the desktop-awareness path is intentionally simple:

```text
GNOME Shell helper
→ observes coarse desktop activity
→ reduces it to anonymous / semantic signals
→ sends signals over D-Bus
→ Mochi's Python presence layer receives them
→ AmbiSense decides whether to react
```

The result may be a speech line, a contextual activity, a state transition, or no visible response at all. Repeated detection of an already-active context should not continuously restart its presentation.

## Signals

Depending on the desktop environment and available helpers, AmbiSense can work with broad signals such as:

- anonymous typing activity and sustained typing intensity
- active vs. idle / returned presence
- coarse app categories such as editor, terminal, browser, media, or pixel-art software
- focused media playback
- battery / charging transitions
- network connection transitions
- file-browsing activity

These signals are intentionally lower-resolution than the underlying desktop activity.

## Privacy model

Typing awareness is content-blind. Mochi does **not**:

- store characters
- inspect typed text
- reconstruct words
- log key values
- persist typing history

Application awareness is reduced to broad semantic categories before Mochi reacts. The goal is to notice the *shape* of desktop activity without reading the user's work.

AmbiSense is a **local rule-based behavior engine**, not an LLM and not a cloud AI service.

## Detection vs. presentation

The architecture aims to keep detection separate from visible character behavior.

A detector should report meaningful changes such as entering or leaving a context. The character/state layer then decides whether that event is allowed to interrupt the current behavior and which animation or dialogue, if any, should represent it.

This separation matters because Mochi can receive overlapping signals while the user is also clicking, dragging, sleeping/waking the character, or triggering another contextual state. Detection should not own animation state directly.

## Failure behavior

Ambient awareness is expected to degrade gracefully. If a helper or signal source is unavailable, Mochi should continue to function as a desktop companion with reduced contextual behavior rather than treating ambient detection as a fatal dependency.

For setup and failure diagnosis, see [Troubleshooting and Regressions](wiki/Troubleshooting-and-Regressions.md). For the broader internal structure, see [Architecture and Tech Stack](wiki/Architecture-and-Tech-Stack.md).
