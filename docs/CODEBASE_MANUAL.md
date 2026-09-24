# Mochi Codebase Manual 🌱

> Deep onboarding guide for contributors who are new to Mochi's runtime.
>
> Verified against main at commit 2753736a0b6fa7d482da174c341c452e641f723b on 2026-09-23.
> Mochi is still an early public alpha, so GitHub main remains the source of truth when this guide and the implementation disagree.

## 1. What Mochi is

Mochi is a lightweight Linux desktop companion built primarily with Python, GTK4/PyGObject, Cairo, GNOME Shell integration, D-Bus, Wayland, and XWayland.

The important word is companion.

Mochi is not designed as a dashboard, chatbot, productivity tracker, or collection of unrelated animation triggers. The runtime tries to make one small character feel coherent while clicks, dragging, sleep, typing, application context, media playback, bond progression, Focus sessions, menus, speech, and autonomous behavior all compete for control.

That means most hard bugs in Mochi are not "how do I show this PNG?" bugs. They are lifecycle and ownership bugs:

- two systems think they own the animation;
- a stale callback fires after a feature was interrupted;
- the visible sprite says idle while the behavior state still says typing;
- a GTK menu closes visually before releasing its input grab;
- a GLib timer survives after the feature that created it has ended;
- an ambient detector repeatedly re-enters a state that is already active;
- a direct interaction does not correctly interrupt or resume a contextual state;
- a packaged build contains different art from the working tree.

When you change Mochi, think in transitions and ownership first.

## 2. The five rules to learn before touching runtime code

### Rule 1: There is one shared behavior-state path

Mochi has one authoritative behavior state machine.

Feature code should request behavior transitions through:

    Buddy._transition_to(next_state)

That delegates to BehaviorStateController, which applies the shared transition policy in behavior.can_transition() before StateMachine is mutated.

Do not call StateMachine.transition_to() directly from a new feature unless you are working inside the state infrastructure itself.

### Rule 2: State and animation are related, but they are not the same thing

The current behavior state might be TYPING while the visual animation moves through:

    terminal_intro
    → terminal_loop
    → terminal_outro

Likewise, Focus is a long-running domain session whose visual presentation may be temporarily interrupted by direct interaction without stopping the Focus clock.

Always ask two separate questions:

1. What does Mochi semantically own right now?
2. What visual is currently being rendered?

A correct feature keeps those answers compatible.

### Rule 3: Direct interaction outranks ambient behavior

Broadly, the priority model is:

1. direct user interaction
2. pickup/drop and sleep/wake transitions
3. deliberate movement
4. explicit one-shot emotes
5. contextual and ambient behavior
6. idle

The exact guard logic lives in behavior.py. Do not duplicate a slightly different priority table inside a new feature.

### Rule 4: Long-lived things need an owner and teardown

Anything that can outlive one callback needs lifecycle ownership:

- GLib timeout sources;
- monitors;
- GTK windows;
- D-Bus adapters;
- audio loops;
- Focus sessions;
- hover-preview animation sources;
- queued presentation callbacks.

Store the source/handle, cancel it when ownership ends, and tear it down during shutdown.

### Rule 5: A feature is not complete until Mochi recovers

The most important regression requirement is:

> Mochi must always become interactable again.

A new animation that looks perfect but breaks the next right-click, drag, wake, or contextual reaction is not complete.

---

# 3. First-time development setup

## Supported development target

The primary target is:

- Fedora Linux
- GNOME
- Wayland session
- XWayland for the buddy window where GNOME positioning restrictions require it
- Python 3.11+
- GTK4 / PyGObject
- Cairo

Other environments may work, but Fedora + GNOME + Wayland receives the strongest regression coverage.

## Install the runtime/helper first

From a checkout:

    git clone https://github.com/miflow13/mochi-desktop.git
    cd mochi-desktop
    ./install.sh

The installer creates the user-facing installation, installs the optional GNOME helper, and places launcher commands under ~/.local/bin.

On a first GNOME Wayland installation, a logout/login may be required before GNOME loads changed extension JavaScript.

## Create a separate editable development environment

    python3 -m venv --system-site-packages .venv
    source .venv/bin/activate
    python3 -m pip install -e .
    python3 -m pip install pytest

The --system-site-packages flag matters on Fedora because PyGObject and GTK bindings are commonly provided by the system Python environment.

## Useful launch modes

Normal launch:

    mochi

Debug logging:

    mochi --debug

Reset saved placement:

    mochi --reset-position

Cycle animation previews with left-click:

    mochi --preview-animations

If ~/.local/bin is not on PATH:

    ~/.local/bin/mochi

---

# 4. Repository map

The repository is easier to understand if you group it by responsibility rather than by filename.

## Top-level areas

**src/mochi/**  
Python runtime.

**src/mochi/presence/**  
AmbiSense integration and many cross-cutting character features layered around the core Buddy runtime.

**assets/mochi/**  
Production sprite library and manifest.

**assets/audio/**  
Short interaction cues and Focus ambience.

**gnome-extension/mochi-typing@miflow13/**  
Optional GNOME Shell helper that reduces desktop activity into privacy-safe semantic D-Bus signals.

**tests/**  
Unit and regression coverage. This is a major part of the architecture, not an afterthought.

**docs/**  
Architecture, feature requirements, QA notes, troubleshooting, and contributor documentation.

**scripts/**  
Installation/helper tooling.

**packaging/**  
Packaging-related files.

**tools/**  
Development utilities.

## Core runtime modules

### src/mochi/main.py

Command-line entry point.

Responsibilities:

- parse --debug, --preview-animations, and --reset-position;
- select the display backend;
- create ConfigStore;
- import GTK lazily;
- launch MochiApplication.

A major design detail lives here: on GNOME Wayland, when DISPLAY is available and MOCHI_NATIVE_WAYLAND is not set to 1, Mochi sets GDK_BACKEND=x11. That intentionally runs the pet window through XWayland because GNOME's native Wayland model does not allow the free top-level positioning Mochi needs.

### src/mochi/app.py

GTK application/window setup.

Responsibilities:

- Gtk.Application lifecycle;
- transparent undecorated buddy window;
- initial configured size;
- WindowPlacement construction;
- choosing PresenceBuddy versus PresenceX11Buddy;
- application-wide CSS;
- spawn/exit sound;
- shutdown handoff.

app.py should remain a shell around the runtime, not become the behavior engine.

### src/mochi/buddy.py

The central interaction coordinator.

Buddy owns or coordinates:

- the DrawingArea;
- rendering;
- the shared StateMachine;
- BehaviorStateController;
- AnimationPlayer;
- SpriteAtlas;
- pointer controllers;
- click behavior;
- drag lifecycle;
- autonomous walking;
- blink scheduling;
- idle action scheduling;
- core sleep/wake;
- context/developer menu compatibility hooks;
- ambient activity compatibility hooks;
- detector startup;
- animation completion and recovery.

This is one of the highest-risk files in the project. Changes here should be small and regression-tested.

### src/mochi/state.py

The small observable state record.

Current behavior states:

- IDLE
- BLINKING
- BOUNCING
- SQUISHING
- EXCITED
- IDLE_EMOTE
- WALKING
- SLEEPING
- WAKING
- HEART
- EATING
- COMPUTER
- TYPING
- WATCHING
- DANCING
- SEARCHING
- PICKUP
- DRAGGED
- DROPPING
- FEDORA

There is also a separate PresentationState:

- NORMAL
- LEVEL_UP
- EMOTE_UNLOCK

This separation matters. Bond level-up presentation can temporarily claim presentation space without inventing a second behavior state machine.

### src/mochi/state_controller.py

Single guarded entry point for behavior-state changes.

BehaviorStateController.request():

1. reads the current state;
2. asks behavior.can_transition(current, requested);
3. logs rejected transitions;
4. updates the StateMachine only if allowed.

### src/mochi/behavior.py

Shared behavior policy and small pure helpers.

Important responsibilities:

- can_transition();
- click reaction eligibility;
- sleep/wake eligibility;
- click reaction buffering;
- walk direction selection;
- WalkMotion interpolation and duration.

If a new feature needs a special state exception, first ask whether the rule belongs here instead of inside the feature.

### src/mochi/animation.py

GTK-independent animation primitives.

AnimationFrame contains:

- sprite path/key;
- vertical offset;
- optional per-frame duration;
- horizontal offset.

Animation contains:

- name;
- ordered frames;
- default frame duration;
- loop flag;
- optional next_state animation name.

AnimationPlayer owns:

- current animation;
- current frame;
- elapsed time inside the frame;
- play();
- stop();
- seek_progress();
- tick();
- completion callback.

GTK supplies time. AnimationPlayer supplies deterministic playback.

### src/mochi/sprite_loader.py

Loads and validates manifest-backed animation data.

The asset loader should be the only layer resolving runtime animation assets. Behavior code should ask for animation names, not construct PNG paths.

### src/mochi/sprites.py

Builds runtime animation definitions and cached drawing surfaces.

It also creates some derived runtime animations. For example, the computer source animation is sliced into intro, typing-loop, and outro variants without duplicating those assets on disk.

It also applies authored/per-frame timing adjustments.

### src/mochi/windowing.py

Window placement abstraction.

It handles:

- saved position;
- layer-shell capability;
- X11/XWayland fallback movement;
- pointer-relative dragging;
- monitor selection;
- edge clamping;
- scaling between GTK application pixels and X11 device pixels;
- position restoration and synchronization.

Window correctness and visual drag feel are separate concerns. Keep them separate.

### src/mochi/x11_buddy.py and src/mochi/x11.py

X11/XWayland-specific behavior.

These exist because GNOME Wayland's compositor rules differ from freely movable X11 top-level windows. Avoid spreading low-level X11 assumptions into generic feature code.

### src/mochi/config.py

JSON persistence under the user's XDG config directory.

ConfigStore currently persists things such as:

- window position;
- size;
- volume;
- mute;
- Stay put;
- edge roaming;
- bond state;
- first-start marker;
- intro-seen marker.

Persistence is intentionally separate from the behavior state machine. Do not save transient animation state.

### src/mochi/sound.py

Central audio ownership.

There are two important audio classes of behavior:

1. short semantic sound events, such as click, feed, pickup, drop, level-up, spawn, exit, and menu-open;
2. long-running Focus ambience, which has its own backend/handle lifecycle.

Do not treat long-running audio like a fire-and-forget click sound.

---

# 5. Startup flow

A simplified startup path is:

    mochi command
      ↓
    mochi.main.main()
      ↓
    configure_display_backend()
      ↓
    ConfigStore()
      ↓
    MochiApplication
      ↓
    Gtk.ApplicationWindow
      ↓
    WindowPlacement
      ↓
    choose PresenceBuddy or PresenceX11Buddy
      ↓
    Buddy + cooperative feature layers
      ↓
    StateMachine / AnimationPlayer / SpriteAtlas
      ↓
    input controllers + menus + monitors + timers
      ↓
    present window

On GNOME Wayland, the common production path is:

    Wayland desktop
      + XWayland available
      ↓
    GDK_BACKEND=x11
      ↓
    GTK buddy window runs through XWayland
      ↓
    GNOME helper still supplies Wayland/GNOME context through D-Bus

This hybrid architecture is deliberate.

---

# 6. The actual runtime object: Buddy plus feature layers

A newcomer can easily assume PresenceBuddy is one normal class. It is not.

The production PresenceBuddy is assembled through cooperative multiple inheritance.

Current layer order:

    ClickDialogueMixin
    IdleLookMixin
    QuickStartMixin
    FocusSessionMixin
    FedoraModeMixin
    TerminalCoworkMixin
    MusicDanceMixin
    EdgeRoamMixin
    EmoteCatalogueMixin
    BondMeterMixin
    FeedMochiMixin
    NameplateMixin
    PresenceBuddyMixin
    Buddy

The X11 production buddy uses the same feature layers and ends in the X11-flavored base.

## Why this matters

Methods such as these may participate in a cooperative super() chain:

- __init__()
- _tick()
- _draw()
- _build_context_menu()
- _build_developer_menu()
- _finish_reaction()
- _play_animation()
- _transition_to()
- ambient callbacks;
- shutdown_presence().

If you override one and forget super(), every layer after yours may silently stop running.

## But Mochi is moving away from "everything is a mixin"

The architecture intentionally prefers composition for subsystems with their own lifecycle.

Buddy already owns composition-based controllers including:

- BehaviorStateController;
- BuddyMenuController;
- AmbientActivityController;
- AutonomousSleepController.

Use a mixin only when the feature is genuinely narrow and intentionally needs to participate in the cooperative chain.

A subsystem with timers, cached state, monitors, windows, or many related methods usually deserves a composed controller.

Important current architecture note: FocusSessionMixin is explicitly recognized in the project documentation as composition debt. Do not use its size as a template for future mixins.

---

# 7. Behavior state, visual state, presentation state, and domain state

Mochi has several kinds of state. Mixing them together creates bugs.

## Behavior state

Stored in StateMachine.current.

This answers:

> What kind of behavior currently owns Mochi?

Examples:

- WALKING
- TYPING
- SLEEPING
- DRAGGED
- EATING

## Visual animation

Tracked through Buddy._current_animation, Buddy._active_animation, Buddy._pending_animation, and AnimationPlayer.

This answers:

> What exact authored animation is playing?

Examples:

- idle
- typing_intro
- typing_loop
- terminal_intro
- terminal_loop
- terminal_outro
- eat
- drop
- fedora_loop

One behavior state may use several visual animations.

## Presentation state

Stored in StateMachine.presentation.

This answers:

> Is a higher-level presentation sequence currently claiming speech/presentation space?

Examples:

- NORMAL
- LEVEL_UP
- EMOTE_UNLOCK

## Domain state

Feature-specific logic can have its own domain model as long as it does not become a competing behavior FSM.

Examples:

- FocusSession.phase;
- BondState level/xp;
- whether music is playing;
- whether the GNOME helper reports the user idle;
- whether terminal coworking is active;
- whether Fedora mode is held.

The pattern is:

    domain state
      ↓
    decides whether to request behavior
      ↓
    shared BehaviorStateController
      ↓
    shared StateMachine
      ↓
    visual animation

---

# 8. Transition policy

behavior.can_transition() is the main behavior priority gate.

Some important examples:

- requesting IDLE is always allowed;
- PICKUP can move to DRAGGED or DROPPING;
- DRAGGED normally moves to DROPPING;
- WAKING rejects competing transitions;
- SLEEPING rejects most competing transitions;
- WAKING can only start from SLEEPING;
- BLINKING and WALKING begin from IDLE;
- TYPING can replace several lower-priority ambient states;
- WATCHING can replace selected lower-priority ambient states;
- EATING is a direct interaction and may interrupt lower-priority reactions, but not sleep, wake, pickup, drag, drop, Fedora, or another eat;
- FEDORA protects held/sleep/drag ownership.

When adding a new MochiState:

1. add the enum value;
2. define transition policy centrally;
3. define entry behavior;
4. define completion/recovery;
5. define interruption behavior;
6. add tests for both accepted and rejected transitions;
7. test interaction with sleep, drag, menu actions, and ambient contexts.

Do not add a state simply because an animation has a name. Many visual sub-phases should remain animations under an existing semantic state.

---

# 9. Animation lifecycle

## Loading

assets/mochi/manifest.json is the asset source of truth.

At import/runtime setup:

    manifest
      ↓
    AnimationAssetSet
      ↓
    ANIMATIONS dictionary
      ↓
    SpriteAtlas / AnimationPlayer

## Starting an animation

Buddy._play_animation(name, after=None):

- preserves semantic animation naming even when a mood-specific asset is rendered;
- stores the active animation object;
- determines the pending next animation;
- starts AnimationPlayer;
- queues a redraw.

The default pending animation can come from Animation.next_state.

## Ticking

Buddy runs at a nominal 16 ms tick.

It measures real elapsed time instead of assuming every GTK callback arrived exactly on schedule, while capping catch-up to avoid giant jumps.

The tick coordinates:

- walking progress;
- pickup/drag sampling;
- held drag sway;
- animation-player advancement;
- redraws.

Feature layers may cooperatively extend _tick() for things such as feed sound timing, bond particles, or nameplate updates.

## Completion

AnimationPlayer calls the registered completion callback.

Buddy._finish_reaction() first checks:

    finished_animation is self._active_animation

If not, the completion is stale and is ignored.

This is one of Mochi's most important race-condition protections.

A stale callback must not:

- award bond XP;
- advance a feature sequence;
- force idle;
- play a follow-up emote;
- overwrite a newer animation.

Feature mixins that extend _finish_reaction() should perform the same kind of ownership check before acting.

## Recovery

Normal one-shot completion returns to IDLE and idle visuals unless the feature intentionally owns a sequence such as:

    typing_intro → typing_loop → typing_outro → idle

or:

    sleep → sleeping
    sleeping → wake → idle

or:

    feed → heart → idle

or a Focus/level-up/Fedora-specific chain.

---

# 10. Sprite and art pipeline

## Production asset rules

The runtime animation library lives under assets/mochi/.

manifest.json is authoritative.

Every production frame should be:

- declared in the manifest;
- present on disk;
- transparent PNG;
- on the canonical 256 × 256 runtime canvas, unless a smaller authored source cell size is explicitly declared;
- bottom-center anchored;
- nearest-neighbor scaled.

Do not store authoring clutter in the runtime asset directory.

Avoid:

- ZIP handoffs;
- Pixelorama source files;
- temporary renders;
- old superseded frames;
- undeclared loose PNGs;
- duplicate exports.

## Current asset roles

Core/locomotion includes:

- default;
- idle;
- sad_idle;
- blink;
- walk / walk_left;
- pickup;
- dragged;
- drop;
- sleep / sleeping / wake.

Direct interaction/catalogue examples include:

- bounce;
- squish;
- heart;
- wave;
- coffee;
- vs_code;
- mochi_exe;
- Fedora intro/loop/outro.

Contextual examples include:

- computer;
- focus start/loop/stop;
- focus thinking start/loop/end;
- typing intro/loop/outro;
- terminal intro/loop/outro;
- watch;
- searching;
- sway_idle.

## Adding a new animation

1. finish/clean the source art;
2. export only final runtime PNGs;
3. place them in one clearly named folder;
4. update manifest.json;
5. add the directory to pyproject.toml package data if it is new;
6. preview in Mochi Lab or preview mode;
7. verify the transition into and out of the animation;
8. run:

       python -m pytest tests/test_sprite_loader.py
       python -m pytest -q

9. build a wheel and verify the asset actually ships.

The working tree being correct is not enough. Packaging is a separate verification step.

---

# 11. Pointer interaction

Buddy installs separate GTK controllers for separate interaction responsibilities.

## Primary click

Gtk.GestureClick handles press/release.

Click behavior includes:

- click sound;
- normal tactile reaction;
- click buffering;
- sleep wake-up;
- higher-level click burst logic from ClickDialogueMixin.

## Secondary click

A separate Gtk.GestureClick opens the context menu on press.

This separation helps avoid context-menu behavior being entangled with primary drag state.

## Hover/motion

Gtk.EventControllerMotion handles enter, leave, and motion.

Hover behavior must remain independent from click/drag/right-click hit testing.

## Drag

Gtk.GestureDrag handles:

    drag-begin
    → drag-update
    → drag-end

The conceptual lifecycle is:

    IDLE
      ↓
    PICKUP
      ↓
    DRAGGED
      ↓
    DROPPING
      ↓
    IDLE

Immediate release during pickup is a valid path and must recover.

---

# 12. Drag architecture

Dragging has two deliberately separate concepts:

1. real window position;
2. visual body inertia/pose.

WindowPlacement and X11 movement own the real position.

DragMotionModel and DragPoseSelector own visual feel.

Do not make visual lag change the final drop coordinates.

## XWayland behavior

While held, the X11/XWayland path can sample the real pointer/window position at the normal tick rate. This helps avoid event-coalescing gaps and makes screen-edge clamping feel solid.

## Visual drag states

Velocity/intensity can select authored directional poses.

When movement settles to neutral, Mochi may transition into sway_idle while still semantically DRAGGED.

That is a good example of why semantic state and exact animation name are different.

## Required drag tests

Always exercise:

    idle → pickup → immediate release
    idle → pickup → long drag → release
    idle → pickup → fast drag → release
    release settle → immediate re-grab
    context action → drag
    heart → recover → drag
    Focus visual → drag → resume Focus presentation

Also check direction reversal because it is a known sensitivity area.

---

# 13. Context menu lifecycle

The context menu has historically been a high-risk GTK surface.

The core rule is:

> Closing visually is not the same as releasing the GTK input grab.

A safe menu action sequence is:

    select action
      ↓
    clear context state
      ↓
    request close
      ↓
    wait for closed
      ↓
    defer one main-loop turn
      ↓
    start behavior

Do not start a window-moving behavior immediately after calling popdown()/close.

That can leave an invisible stale surface intercepting later input.

Use the existing deferred helpers such as _close_context_menu_then() rather than inventing a new close-and-run pattern.

When adding a context-menu row:

- participate in the cooperative _build_context_menu() chain;
- use BuddyMenuController helpers;
- register row placement intentionally;
- preserve menu lifecycle;
- test repeated open/close;
- test right-click and drag afterward.

---

# 14. AmbiSense: context, not content

AmbiSense is Mochi's local rule-based ambient-awareness system.

It is not an LLM and does not use a cloud AI service.

The design goal is to react to broad semantic desktop context without collecting content.

## GNOME event path

    GNOME Shell helper
      ↓
    observes coarse local desktop activity
      ↓
    reduces it to semantic/anonymous signals
      ↓
    D-Bus
      ↓
    Python monitor/adapter
      ↓
    Presence/AmbiSense layer
      ↓
    behavior request, speech, or no response

Repeated detection of an already-active context should not continuously restart its presentation.

## GNOME helper signals

The optional helper currently exposes semantic events such as:

- anonymous typing Pulse;
- UserIdle;
- UserActive;
- FileBrowsingStarted / FileBrowsingStopped;
- YouTubeFocusedStarted / YouTubeFocusedStopped;
- AppCategoryChanged;
- EmoteCatalogueRequested;
- developer-menu shortcut request.

App categories are coarse values such as:

- vscode;
- editor;
- terminal;
- browser;
- media;
- pixel_art;
- unknown.

## Privacy boundary

The helper is intentionally designed not to transmit or store:

- typed characters;
- keycodes;
- Unicode values;
- passwords;
- typed text;
- pointer coordinates;
- file names;
- folder names;
- paths;
- general application window titles;
- document content;
- screen content.

The YouTube focus helper may transiently inspect a focused browser title only to reduce it to a yes/no YouTube semantic state; the title itself is not retained or sent to Mochi.

When adding a new detector, reduce raw desktop information to the smallest semantic event before it enters the character runtime.

---

# 15. Ambient activity routing

Core ambient detector events are translated into behavior by AmbientActivityController.

This keeps detector-specific orchestration out of Buddy.

Examples:

## Typing

Anonymous typing activity can request TYPING.

The visual sequence may be:

    typing_intro
      → typing_loop
      → typing_outro
      → idle

Typing does not inspect content.

## Watching

Recognized YouTube/video activity can request WATCHING.

When watching ends, Mochi resolves the next live context instead of blindly returning to an empty idle if another context is already active.

## File activity

Supported file-browsing activity can request SEARCHING.

Again, stop logic resolves the next active ambient context.

## Context restoration

After a direct interaction ends, the runtime may call a "resume ambient activity" path.

This is a critical design pattern:

> Direct interaction temporarily wins, then the current live context is reevaluated.

Do not store a naive "previous animation" and replay it later. The real context may have changed during the interruption.

---

# 16. VS Code and terminal coworking

Mochi has contextual coworking behavior for development activity.

Terminal coworking is a useful example of correct event/state separation.

Terminal focus is a semantic context. The terminal art sequence uses the existing TYPING semantic state rather than inventing a second near-duplicate state machine.

Typical visual flow:

    terminal focused
      ↓
    debounce
      ↓
    TYPING behavior state
      ↓
    terminal_intro
      ↓
    terminal_loop

When terminal focus ends:

    terminal_loop
      ↓
    terminal_outro
      ↓
    resolve destination context
      ↓
    VS Code / terminal again / sleep / media / file / idle

A fast refocus during terminal_outro does not snap backward. The authored close can finish, then the intro reopens.

That is the level of lifecycle detail new contextual features should aim for.

---

# 17. Music and media priority

MusicDanceMixin adds recognized music playback without taking over pointer logic.

A simplified contextual priority is:

    explicit watchable video
      >
    coding/terminal coworking where applicable
      >
    music
      >
    file browsing
      >
    ordinary idle

Direct interaction and typing can still temporarily outrank music.

MPRIS/browser detection can be ambiguous, so the code distinguishes confident music/video context from broad browser-focus fallbacks where possible.

When a detector becomes more specific, fix the detector or semantic routing. Do not merely hide the visible animation.

---

# 18. Sleep and autonomous sleep

Sleep is a lifecycle, not a repeating "fall asleep" GIF.

    IDLE-ish state
      ↓
    sleep transition
      ↓
    SLEEPING hold/loop
      ↓
    WAKING
      ↓
    wake animation
      ↓
    IDLE
      ↓
    resolve live context

User presence idle is primarily driven by GNOME's server-global idle signal when the helper is available.

AutonomousSleepController can also own occasional naps without creating another sleep FSM.

Ownership matters: the controller tracks whether a sleep belongs to it so an external/manual wake is not confused with the controller's scheduled wake.

Features such as Focus and Fedora mode can intentionally defer automatic sleep.

---

# 19. Bond progression

Bond is persistent relationship progress.

It is deliberately non-punitive:

- no streaks;
- no decay;
- no missed-day penalty.

## Pure domain layer

src/mochi/care.py contains the pure bond rules.

BondState is immutable and normalizes XP overflow across level boundaries.

The current level requirement curve is:

    480 + round(90 * sqrt(level - 1))

Typing currently awards bond progress at one XP per qualifying second.

Feed rewards are intentionally bounded inside a reward window so repeatedly spamming Feed does not become the dominant progression mechanic.

## Persistence

ConfigStore saves:

- bond_level;
- bond_xp.

It also migrates an earlier preview representation if old bond_points/bond_phases data is present.

## Presentation/integration

presence/bond_meter.py connects runtime activities to bond state and owns level-up/unlock presentation.

It does not own a second behavior state machine.

A real level crossing can trigger an authoritative presentation sequence such as:

    level changes
      ↓
    level-up animation + sound
      ↓
    level card
      ↓
    optional unlock card
      ↓
    learned-emote demo
      ↓
    recover

A refresh of the same saved level must not replay the celebration.

---

# 20. Feeding

presence/feeding.py is a good example of keeping care rules and animation separate.

Flow:

    user chooses Feed
      ↓
    close context menu safely
      ↓
    verify current state can accept feeding
      ↓
    cancel lower-priority movement/ambient behavior
      ↓
    request EATING
      ↓
    play eat
      ↓
    authored frame crossing triggers eat sound
      ↓
    only current owned eat completion is accepted
      ↓
    heart
      ↓
    bond completion hook
      ↓
    recover

The completion hook validates both active-animation ownership and EATING state.

That prevents an interrupted or stale eat callback from awarding progress later.

---

# 21. Emote Catalogue

The Emote Catalogue is a user-facing collection of Mochi behaviors.

It includes:

- bond-gated unlocks;
- rarity tiers;
- locked states;
- hover previews;
- catalogue actions;
- unlocked emotes that can join autonomous idle variety.

The catalogue reflects bond state. It does not own bond progression.

The GNOME helper shortcut is:

    Ctrl + Alt + E

When changing catalogue behavior, test:

- locked/unlocked correctness;
- hover preview cleanup;
- repeated open/close;
- newly unlocked refresh;
- shortcut and normal UI entering the same lifecycle;
- no leaked GTK windows or timer sources.

---

# 22. Focus with Mochi

Focus is one of the most important systems to understand because it demonstrates the difference between domain time and visual ownership.

## Pure domain model

src/mochi/focus.py contains FocusPlan and FocusSession without GTK dependencies.

FocusPlan clamps:

- focus: 5–120 minutes;
- break: 1–30 minutes;
- rounds: 1–8.

FocusSession owns:

- FOCUS / BREAK / COMPLETE phase;
- remaining time;
- current round;
- pause state;
- completed focus minutes;
- reward boundaries;
- sparse encouragement marks.

Current rewards:

- 1 bond XP per completed focus minute;
- +10 XP once for full configured completion;
- no break XP;
- no punishment for stopping early;
- already-earned whole-minute XP is retained.

## GTK/runtime integration

presence/focus_session.py owns the user-facing Focus integration:

- setup window;
- timer window;
- setup "thinking" presentation;
- focus writing presentation;
- focus source/tick lifecycle;
- pause/resume/stop;
- rain ambience;
- bond reward handoff;
- shutdown settlement.

## Critical mental model

The Focus clock remains authoritative even when the visual is temporarily interrupted.

For example:

    Focus active
      ↓
    user drags Mochi
      ↓
    drag presentation temporarily wins
      ↓
    Focus clock keeps correct domain ownership
      ↓
    direct interaction ends
      ↓
    Focus visual can resume

Do not implement Focus-like systems by stopping/restarting domain time every time a visual reaction occurs.

## Reward boundary safety

Elapsed/reward time must be settled before:

- pause;
- stop;
- manual sleep;
- shutdown.

The pure model also reconciles the exact end of a configured focus block so floating-point drift does not lose the final minute's XP.

---

# 23. Audio

SoundManager maps semantic short events to replaceable audio files and global settings.

Short sounds should be requested semantically, not by sprinkling subprocess calls throughout feature code.

Focus rain is different.

It is a long-running loop with a persistent handle that supports:

- start;
- pause;
- resume;
- set volume;
- stop.

Rules for long-running audio:

- one owner;
- one active handle;
- volume changes should not needlessly create new loops;
- pause/stop/shutdown must leave the backend in a known state;
- missing audio support should fail safely.

---

# 24. Persistence

Default config path follows XDG_CONFIG_HOME, falling back to:

    ~/.config/mochi/config.json

Config writes use a temporary file and replace pattern.

When adding persistent state:

1. keep it small;
2. choose a safe default;
3. validate types on load;
4. clamp or normalize external values;
5. avoid persisting transient behavior/animation ownership;
6. consider migration from prior keys;
7. add tests for malformed/missing config;
8. ensure persistence failure cannot strand the behavior state.

---

# 25. GTK windows and overlays

Mochi uses more than one type of GTK surface:

- the buddy window;
- context menu;
- Mochi Lab;
- speech bubble;
- nameplate;
- Emote Catalogue;
- Focus setup/timer;
- bond/level-up presentation surfaces.

Each extra window introduces lifecycle questions:

- Who owns it?
- Can it survive the buddy moving?
- Does it follow Mochi?
- Can it intercept input?
- What destroys it?
- What happens during shutdown?
- What happens if it is opened twice?
- What happens if state changes while it is visible?

Do not create a GTK window without answering those questions.

---

# 26. The GNOME helper

The extension under gnome-extension/mochi-typing@miflow13 is optional but provides the richest GNOME integration.

Local install:

    ./scripts/install-typing-extension.sh

Enable/check:

    gnome-extensions enable mochi-typing@miflow13
    gnome-extensions info mochi-typing@miflow13

Expected state:

    ACTIVE

Developer shortcut:

    Ctrl + Alt + Shift + M

This opens Mochi Lab through a zero-payload semantic helper signal.

After changing GNOME extension JavaScript, logout/login may be necessary because GNOME Shell can retain a previously loaded module.

---

# 27. Testing strategy

Mochi needs several layers of verification.

## Layer 1: focused tests

Run the smallest relevant regression test first.

Examples:

- animation/state;
- context menu;
- drag/pickup;
- feeding;
- bond;
- emote catalogue;
- Focus;
- audio;
- helper lifecycle;
- window placement.

A strong bug fix starts by reproducing the failure in a focused test when practical.

## Layer 2: full suite

    python -m pytest -q

## Layer 3: Python compilation

    python -m compileall -q src tests

## Layer 4: diff validation

    git diff --check

## Layer 5: package build

    python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mochi-wheel

If assets or packaging changed, inspect the wheel contents.

## Layer 6: optional real D-Bus helper integration

    MOCHI_RUN_DBUS_TESTS=1 python -m pytest tests/test_helper_dbus_integration.py

Report environment-dependent skips honestly.

## Layer 7: live Fedora/GNOME/Wayland/XWayland QA

This is required for interaction-heavy changes because unit tests cannot prove compositor/input behavior.

---

# 28. Interaction torture test

For runtime changes, deliberately try to break Mochi.

A useful sequence is:

    idle
    → click
    → double-click
    → triple-click
    → drag/drop
    → drag again
    → right-click → Feed
    → heart/recover
    → open Emote Catalogue
    → hover entries
    → close/reopen
    → right-click → Focus
    → start
    → pause
    → resume
    → drag during Focus
    → right-click during Focus
    → Feed during Focus
    → Stop
    → Start again
    → manual Sleep during Focus
    → wake
    → complete a short Focus session
    → cross a bond level if practical
    → right-click
    → drag

Also test messy timing:

- immediate release after pickup;
- rapid reversal while dragging;
- repeated right-click open/close;
- click/double-click bursts;
- feed spam;
- catalogue open/close loops;
- Focus start/stop/start;
- Focus hide/reopen;
- Rain volume changes;
- shutdown during active Focus;
- shutdown with pending bond reward;
- workspace/Overview transitions.

Pass conditions:

- no freeze;
- no invisible input interception;
- no Python traceback;
- no stuck behavior state;
- no stuck presentation state;
- no duplicate timers;
- no duplicate audio;
- correct persistence;
- correct reward boundaries;
- right-click still works;
- drag still works.

---

# 29. Debugging playbook

## Symptom: Mochi looks idle but rejects actions

Check the semantic state.

A prior historical failure mode was visually returning to idle without restoring StateMachine.current to IDLE.

Debug both:

- state.current;
- _current_animation.

They should tell a compatible story.

## Symptom: an old reaction fires after a newer one

Suspect a stale completion callback or timer.

Check ownership:

- Is the callback tied to the current active animation?
- Is the GLib source still owned?
- Was the source cancelled on interruption?
- Did the feature compare the object/token/generation it originally started?

## Symptom: right-click stops working after a menu action

Suspect the menu-close lifecycle.

Do not "fix" this by reopening/resetting the menu elsewhere. Verify the close → closed → idle_add/deferred action sequence.

## Symptom: contextual animation is wrong

Trace the detector first.

Ask:

- What semantic event arrived?
- Did the helper send stale state?
- Did a monitor fail to clear state?
- Did repeated snapshots retrigger an already-active context?
- Did an interruption resume an obsolete context instead of reevaluating the live one?

Fix the event source/routing before suppressing presentation.

## Symptom: animation art suddenly looks old

Audit the asset migration.

Do not replace all of assets/mochi when adding one animation.

Compare:

- manifest entries;
- frame counts;
- hashes if needed;
- packaged wheel contents.

## Symptom: installed app differs from checkout

Remember:

    git pull

does not update an already-installed app-grid copy by itself, and a running process keeps loaded Python code.

Quit Mochi, reinstall with ./install.sh when appropriate, then relaunch.

---

# 30. Common change recipes

## Recipe A: add a new one-shot emote

Likely files:

- assets/mochi/<name>/;
- assets/mochi/manifest.json;
- pyproject.toml if new folder;
- catalogue metadata/UI if user-facing;
- behavior entry method;
- tests.

Questions to answer:

- Is this direct, contextual, or idle?
- Does it need a new MochiState, or can it use IDLE_EMOTE?
- What interrupts it?
- What does it return to?
- Can it be unlocked?
- Can it appear autonomously?
- Is the authored animation looping?
- Does it need sound?

Prefer reusing IDLE_EMOTE for finite autonomous catalogue reactions instead of creating a state for every emote.

## Recipe B: add a new contextual desktop reaction

Prefer this pipeline:

    detector/helper
      ↓
    privacy reduction
      ↓
    semantic start/stop event
      ↓
    monitor/adapter
      ↓
    ambient/context routing
      ↓
    shared state transition
      ↓
    authored presentation

Do not continuously emit "still active" events if a start/stop edge is sufficient.

Make repeated detection idempotent.

## Recipe C: add a context-menu action

- extend the cooperative menu builder or owned menu controller;
- register placement intentionally;
- close through the existing deferred action helper;
- enter behavior only after close completes;
- verify the next right-click and drag.

## Recipe D: add a persistent setting

- add ConfigStore load/save methods;
- validate/clamp on load;
- choose a non-destructive default;
- expose UI;
- update behavior from one owner;
- test malformed config;
- test restart.

## Recipe E: add a long-running subsystem

Prefer composition.

Give it:

- one owner;
- explicit start;
- explicit stop;
- idempotent teardown;
- source IDs/handles;
- shutdown hook;
- focused tests.

Do not make it a mixin only because that is the shortest way to access Buddy internals.

## Recipe F: add a new behavior state

Only do this if the new feature represents a genuinely distinct semantic ownership mode.

Then update:

- MochiState;
- behavior.can_transition();
- entry logic;
- completion logic;
- interruption rules;
- tests;
- docs.

A visual phase alone is not enough reason for a new state.

---

# 31. Anti-patterns

Avoid these even if they appear to solve the immediate bug.

## Directly swapping sprites from an input callback

Use the behavior + animation lifecycle.

## Calling StateMachine.transition_to() from feature code

Use Buddy._transition_to().

## Starting an unmanaged GLib timeout every time an event arrives

Keep one owned source ID and cancel/reschedule intentionally.

## Replaying the "previous animation" after interruption

Reevaluate the current live context instead. The user's desktop state may have changed while the reaction was active.

## Adding a second state machine for one feature

Use domain state plus the shared behavior state.

## Putting persistence in animation callbacks

Persist through domain/integration ownership after validating the callback still belongs to the current action.

## Copying an entire external art pack into assets/mochi

Migrate only the intended animation.

## Assuming pytest proves GTK/XWayland behavior

It does not.

## Refactoring Buddy while adding an unrelated feature

Keep the feature scoped. Note architectural debt separately.

---

# 32. Known high-risk areas

Treat these systems as regression-sensitive:

- context menu and developer menu;
- cooperative super() chains;
- drag/pickup/drop;
- XWayland positioning;
- multi-monitor/fractional scaling;
- animation completion;
- state/visual agreement;
- autonomous sleep;
- detector start/stop edges;
- D-Bus helper lifecycle;
- Focus clock/reward settlement;
- bond level-up presentation;
- long-running audio;
- catalogue hover timers;
- GTK window teardown.

Current public README also calls out workspace/Overview freezing during some XWayland emotes and drag direction-reversal responsiveness as known issues.

Do not silently claim these fixed without targeted verification.

---

# 33. Shutdown

Application shutdown is part of normal lifecycle design.

MochiApplication.do_shutdown() calls:

    buddy.shutdown_presence()

before the final exit sound and GTK shutdown.

Because many feature layers extend shutdown_presence() cooperatively, every override should:

1. tear down its own sources/windows/monitors;
2. clear ownership flags;
3. call super().shutdown_presence().

Shutdown is also a reward boundary for Focus/bond systems. Earned progress should be settled/persisted before teardown.

---

# 34. Git workflow for Mochi

Use:

    request
    → branch
    → implement
    → focused tests
    → full tests
    → commit
    → push
    → local Fedora/Wayland QA
    → fixes on the same branch
    → merge when approved

Branch from current main.

Keep one question per branch.

Examples:

    feat/music-dance-emote
    feat/focus-session
    fix/context-menu-freeze
    fix/typing-feedback-loop
    docs/codebase-manual
    chore/animation-assets

Conventional commit prefixes:

- feat:
- fix:
- test:
- docs:
- ci:
- chore:
- refactor:

Do not use main as the experimentation branch.

---

# 35. Definition of done

A runtime change is not done when the happy-path animation plays.

Before handoff:

- implementation is scoped;
- focused tests pass;
- full pytest passes;
- compileall passes;
- git diff --check passes;
- wheel builds when relevant;
- packaged assets are audited when relevant;
- no unrelated behavior changed;
- persistence/reward boundaries are correct;
- sources/timers/audio are cleaned up;
- direct interaction still works;
- docs are updated;
- a clean Git checkpoint exists;
- real Fedora/GNOME/Wayland/XWayland behavior is tested when relevant.

The maintainer's real desktop QA is part of the development loop.

---

# 36. Recommended reading order for a new contributor

If you are brand new, read in this order:

1. README.md
2. docs/CODEBASE_MANUAL.md
3. docs/wiki/Architecture-and-Tech-Stack.md
4. src/mochi/main.py
5. src/mochi/app.py
6. src/mochi/state.py
7. src/mochi/state_controller.py
8. src/mochi/behavior.py
9. src/mochi/animation.py
10. src/mochi/buddy.py
11. src/mochi/presence/click_dialogue.py to understand the production composition
12. src/mochi/ambient_activity.py
13. docs/ambisense.md
14. the feature module you are changing
15. its tests
16. REGRESSION_WATCHLIST.md
17. docs/wiki/Troubleshooting-and-Regressions.md

Do not begin by reading every presence mixin linearly. First understand Buddy, state ownership, animation ownership, and cooperative super() behavior.

---

# 37. "Where should I look?" quick reference

| Goal | Start here |
| --- | --- |
| App will not launch | src/mochi/main.py, src/mochi/app.py |
| Positioning / monitor issue | src/mochi/windowing.py, src/mochi/x11.py, src/mochi/x11_buddy.py |
| Wrong state transition | src/mochi/behavior.py, src/mochi/state_controller.py |
| Looks idle but input blocked | src/mochi/buddy.py completion path, state logs |
| Animation timing | src/mochi/animation.py, src/mochi/sprites.py |
| Missing/wrong sprite | assets/mochi/manifest.json, src/mochi/sprite_loader.py |
| Click behavior | src/mochi/buddy.py, presence/click_dialogue.py |
| Drag/pickup/drop | src/mochi/buddy.py, drag_motion.py, x11_buddy.py |
| Context menu | src/mochi/buddy_menu.py |
| Typing/video/files ambient behavior | src/mochi/ambient_activity.py |
| GNOME semantic signals | gnome-extension/mochi-typing@miflow13/ |
| AmbiSense speech/context | src/mochi/presence/integration.py, presence/engine.py |
| Terminal coworking | presence/terminal_cowork.py |
| Music dance | presence/music_dance.py |
| Feeding | presence/feeding.py |
| Bond progression | care.py, presence/bond_meter.py |
| Emote Catalogue | presence/emote_catalogue.py |
| Focus timing | focus.py |
| Focus GTK/runtime | presence/focus_session.py |
| Sounds | sound.py, assets/audio/ |
| Saved preferences | config.py |
| Regression history | docs/wiki/Troubleshooting-and-Regressions.md |
| Merge confidence | REGRESSION_WATCHLIST.md |

---

# 38. A final mental model

When you are unsure how to implement something, draw this chain:

    external event or user input
      ↓
    semantic intent
      ↓
    current domain/context state
      ↓
    shared transition policy
      ↓
    authoritative behavior state
      ↓
    authored animation/presentation
      ↓
    completion or interruption
      ↓
    validate ownership
      ↓
    resolve the current live context
      ↓
    recover

If a proposed feature skips several boxes, it is probably taking ownership that belongs somewhere else.

Mochi feels coherent when every system agrees about one question:

> Who owns the little guy right now, and what is the safe next state?

Keep that answer explicit, and most of the codebase becomes much easier to reason about. 🌱


---

# 39. State-machine audit companion guide

Mochi's state system is small on purpose. The complexity comes from several domains asking for presentation at the same time. When auditing a bug, trace ownership rather than only the visible animation.

For every behavior, write down five facts:

1. **Trigger** — what event requested the behavior?
2. **Domain owner** — which subsystem still considers itself active?
3. **Behavior owner** — what is `StateMachine.current`?
4. **Visual owner** — which animation object is active now?
5. **Recovery decision** — when the interruption ends, which *live* context should win next?

A useful debugging record looks like:

    trigger: user begins typing
    domain: typing monitor active
    behavior: TYPING
    visual: typing_loop
    interruption: PICKUP → DRAGGED → DROPPING
    recovery: reevaluate typing context; resume typing only if still active

The final line is important. Avoid blindly restoring a saved "previous animation." Desktop context can change while Mochi is interrupted.

## Transition review questions

When reviewing a state transition, ask:

- Is the request routed through `Buddy._transition_to()`?
- Does `behavior.can_transition()` express the priority rule centrally?
- Is repeated entry idempotent when the context has not changed?
- Does the state have an explicit normal exit?
- Does interruption cancel or invalidate callbacks owned by the old action?
- Does completion verify that it still owns the active animation/action?
- Does recovery reevaluate current context rather than stale context?
- Can sleep, drag, menus, Focus, or shutdown occur safely from here?

## High-value transition scenarios

The following sequences catch more lifecycle bugs than testing states in isolation:

    typing → pickup → drag → drop → contextual reevaluation
    watching → music → pause → contextual reevaluation
    walking → context menu → close → recovery
    sleeping → context menu → close → still sleeping
    Focus → drag → drop → Focus presentation recovery
    Focus → feed → heart → Focus presentation recovery
    context A → context B without an idle gap
    old animation completion → newer owned animation
    detector/helper disappears while contextual behavior is active
    shutdown while Focus/audio/timers are active

The regression watchlist should be used alongside these sequences rather than replaced by them.

---

# 40. Timer, callback, and monitor ownership

A timer is state.

Every long-lived callback source should have an answer to:

> Who owns this source, and what exact event removes it?

Common owners include:

- Buddy idle/blink scheduling;
- AutonomousSleepController;
- ambient activity monitors;
- typing/presence/media/file monitors;
- Focus session ticks;
- catalogue hover previews;
- speech/nameplate presentation;
- long-running audio;
- delayed click/double-click resolution;
- deferred menu actions.

## Safe source pattern

A long-lived subsystem should generally follow:

    start()
      ↓
    if source already exists: do not duplicate it
      ↓
    store source ID / handle
      ↓
    callback checks current ownership
      ↓
    stop()
      ↓
    remove source / stop handle
      ↓
    clear stored ownership

`stop()` should be safe to call more than once.

## Generation/token pattern

For delayed work that cannot simply be cancelled, use an ownership token or compare against the object that originally started the work.

The animation system already demonstrates this idea by ignoring completion for an animation that is no longer `_active_animation`.

The same principle applies to delayed feature callbacks:

> A callback being scheduled does not guarantee it still has permission to act when it finally runs.

---

# 41. How to read a contextual detector

Do not begin with the animation when a contextual reaction is wrong.

Read the feature from outside inward:

    desktop/application activity
      ↓
    GNOME helper or fallback detector
      ↓
    semantic monitor event
      ↓
    ambient/context controller
      ↓
    feature/domain state
      ↓
    behavior transition request
      ↓
    animation/presentation

For every detector, identify:

- what counts as "started";
- what counts as "stopped";
- whether the detector sends edges or repeated snapshots;
- how duplicate snapshots are suppressed;
- how stale state is cleared if the helper disappears;
- what fallback exists when helper integration is unavailable;
- whether shutdown disconnects the source;
- whether current context can be reconstructed after helper restart.

A detector should ideally communicate semantic changes such as:

    TerminalFocusedStarted
    TerminalFocusedStopped

rather than continuously requesting the terminal animation while the terminal remains focused.

Presentation should react to context changes; it should not be used as the context database.

---

# 42. Adding tests that protect architecture

Mochi tests should protect invariants, not only screenshots of today's implementation.

Strong regression tests answer questions such as:

- Does a rejected transition leave the previous state unchanged?
- Does repeated contextual activation avoid restarting the same behavior?
- Does an interrupted animation's stale completion do nothing?
- Does drag always reach a recoverable post-drop state?
- Does stopping a subsystem remove its timer exactly once?
- Does start → stop → start still create one live source?
- Does a helper outage clear only helper-owned context?
- Does Focus retain domain time while presentation is interrupted?
- Does shutdown settle/persist domain state before tearing down sources?

Prefer small deterministic tests for policy and lifecycle. Reserve live GTK/Fedora QA for compositor behavior that cannot be represented honestly in unit tests.

## Test naming

Names should describe the invariant or regression:

    test_repeated_typing_start_does_not_restart_active_typing
    test_stale_animation_completion_cannot_force_idle
    test_drop_reevaluates_active_context
    test_focus_drag_interruption_keeps_session_running
    test_monitor_stop_is_idempotent

A future contributor should be able to understand *why the test exists* without reading the original bug report.

---

# 43. Documentation maintenance contract

This manual is useful only if it tracks the runtime.

Update it when a change alters:

- startup architecture;
- production Buddy composition/MRO;
- behavior states or transition policy;
- animation ownership/recovery;
- detector/helper architecture;
- asset manifest rules;
- persistent configuration;
- user-facing long-running subsystems;
- test/release commands;
- known high-risk lifecycle areas.

Do not update this manual for every frame-timing tweak or phrase change.

When documentation and implementation disagree:

1. treat current GitHub code as authoritative;
2. verify the behavior with tests where practical;
3. update the manual on the feature/fix branch;
4. mention environment-dependent behavior that still needs Fedora/Wayland QA.

For major architecture changes, update both this manual and the narrower wiki page that owns the topic rather than allowing two contradictory explanations to survive.

---

# 44. Contributor handoff checklist

Before handing a branch to another developer or to Mika for local QA, record:

- branch name;
- one-sentence purpose;
- files/systems intentionally changed;
- tests run and their result;
- tests not run and why;
- known limitations;
- Fedora/Wayland behaviors that require real-machine verification;
- exact manual QA steps;
- whether docs changed;
- whether packaging/assets changed.

For stateful changes, also include:

- entry state;
- trigger;
- expected active state;
- interruption behavior;
- expected recovery state.

A good handoff makes a failure reproducible. "Seems fixed" is not enough information to debug a regression later.

---

# 45. What not to learn from Mochi accidentally

Mochi contains pragmatic decisions made for a small Linux desktop companion. Some are deliberate tradeoffs, not universal Python/GTK patterns.

Do not generalize these without context:

- cooperative multiple inheritance is useful here but should not be the default architecture for every feature;
- XWayland is an intentional compatibility path for free positioning on GNOME, not a claim that X11 is generally preferable to Wayland;
- a global behavior FSM works because Mochi is one character with one visible body;
- GTK timers are appropriate for UI lifecycle work but should not become an unmanaged job system;
- runtime-derived animations are useful when they represent authored subranges, but should not replace a clear asset pipeline;
- compatibility seams are valuable during architectural migration, but they should not become permanent excuses for duplicate ownership.

The transferable lesson is not "copy Mochi's classes." It is:

> make ownership explicit, keep transitions centralized, keep long-lived resources cancellable, and test recovery as seriously as entry.
