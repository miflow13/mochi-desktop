"""User-triggered feeding interaction for Mochi's v0.3 care loop."""

from __future__ import annotations

import time

from gi.repository import Gtk

from mochi.sound import SoundEvent
from mochi.state import MochiState


class FeedMochiMixin:
    """Add a small Feed action without owning future care/progression data.

    This slice intentionally keeps presentation separate from care mechanics:

    - the menu action closes through Buddy's proven deferred-action path;
    - EATING owns the one-shot animation while it is active;
    - a completed feed immediately chains into the existing heart emote;
    - the existing animation tick plays the sound as the candy approaches his mouth;
    - `_on_feed_animation_completed()` is the extension seam for future
      fullness/XP/progression updates.

    A later care model can override `_can_feed()` and the two hooks without
    teaching the animation state machine about hunger values or persistence.
    """

    def _build_context_menu(self):
        menu = super()._build_context_menu()
        feed_button, _ = self._make_menu_button(
            "Feed",
            "emblem-favorite-symbolic",
            self._feed_from_context_menu,
        )
        self._register_context_menu_row(
            "feed",
            feed_button,
            before="sleep",
        )
        return menu

    def _feed_from_context_menu(self, _button: Gtk.Button) -> None:
        """Close the menu first so the feeding animation owns the next frame."""
        self._close_context_menu_then(self._start_feeding)

    def _can_feed(self) -> bool:
        """Return whether the current behavioral state can accept feeding.

        Fullness, cooldowns, food inventory, or other future care rules belong
        here (or in an override), not in the menu callback or animation player.
        """
        return self.state.current not in (
            MochiState.SLEEPING,
            MochiState.WAKING,
            MochiState.PICKUP,
            MochiState.DRAGGED,
            MochiState.DROPPING,
            MochiState.FEDORA,
            MochiState.EATING,
        )

    def _start_feeding(self) -> bool:
        if not self._can_feed():
            self._logger.debug(
                "Feed ignored while Mochi is %s",
                self.state.current.name,
            )
            return False

        # Feeding is a direct user interaction. Stop lower-priority movement or
        # ambient emotes before taking ownership, then let the central state
        # guard make the final decision.
        if self.state.current is MochiState.WALKING:
            self._cancel_walk()
        self._cancel_active_emote()

        if not self._transition_to(MochiState.EATING):
            return False

        self._last_interaction = time.monotonic()
        self._play_animation("eat", after="idle")
        self._on_feed_animation_started()
        return True

    def _finish_reaction(self, finished_animation) -> None:
        # Capture completion before Buddy clears/replaces the active animation.
        # Stale callbacks from an interrupted feed must never award future care
        # progress, fire completion sounds, or trigger the post-feed heart.
        completed_feed = (
            finished_animation is getattr(self, "_active_animation", None)
            and getattr(finished_animation, "name", None) == "eat"
            and self.state.current is MochiState.EATING
        )
        super()._finish_reaction(finished_animation)
        if completed_feed:
            # Buddy's normal one-shot completion path has already restored the
            # idle state/animation here. Reuse the existing heart entry point,
            # but bypass its hover cooldown so feeding always gets immediate
            # positive feedback before ambient behavior can resume.
            if not self._start_heart_emote(ignore_cooldown=True):
                self._logger.warning(
                    "Post-feed heart could not start after eating completed"
                )
            self._on_feed_animation_completed()

    def _tick(self) -> bool:
        animation = self.player.animation
        previous_frame = self.player.frame_index
        result = super()._tick()
        # Authored frame 2 starts the cue as the candy approaches his mouth.
        # Detect crossing it instead of using a wall-clock timer: interrupted
        # feeds stay silent and a held frame cannot repeat the cue.
        if (
            animation is not None
            and animation.name == "eat"
            and self.player.animation is animation
            and self.state.current is MochiState.EATING
            and previous_frame < 1 <= self.player.frame_index
        ):
            self._sound.play(SoundEvent.EAT)
        return result

    def _on_feed_animation_started(self) -> None:
        """Extension hook for future feeding entry behavior."""

    def _on_feed_animation_completed(self) -> None:
        """Extension hook for care/progression layers composed after feeding."""
        next_hook = getattr(super(), "_on_feed_animation_completed", None)
        if callable(next_hook):
            next_hook()
