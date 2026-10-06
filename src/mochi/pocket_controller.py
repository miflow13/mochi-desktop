"""GTK-independent orchestration for Mochi's Pocket interactions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging

from mochi.behavior import can_start_pocket_offer, can_start_pocket_receive
from mochi.pocket import PocketItem
from mochi.pocket_store import PocketStore
from mochi.state import MochiState


class PocketController:
    """Own the live Pocket list and one persistence-first receive transaction."""

    def __init__(
        self,
        store: PocketStore,
        *,
        current_state: Callable[[], MochiState],
        cancel_walk: Callable[[], None],
        cancel_ambient: Callable[[], None],
        transition: Callable[[MochiState], bool],
        play_animation: Callable[[str, str | None], None],
        mark_interaction: Callable[[], None],
        resume_ambient: Callable[[], object],
        show_feedback: Callable[[str], None],
        on_changed: Callable[[tuple[PocketItem, ...]], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._store = store
        self._current_state = current_state
        self._cancel_walk = cancel_walk
        self._cancel_ambient = cancel_ambient
        self._transition = transition
        self._play_animation = play_animation
        self._mark_interaction = mark_interaction
        self._resume_ambient = resume_ambient
        self._show_feedback = show_feedback
        self._on_changed = on_changed or (lambda _items: None)
        self._logger = logger or logging.getLogger(__name__)
        self._items = tuple(store.load())
        self._busy = False
        self._hover_active = False

    @property
    def items(self) -> tuple[PocketItem, ...]:
        return self._items

    @property
    def count(self) -> int:
        return len(self._items)

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def hover_active(self) -> bool:
        return self._hover_active

    def can_receive(self) -> bool:
        if self._busy:
            return False
        if self._hover_active:
            return self._current_state() is MochiState.EXCITED
        return can_start_pocket_receive(self._current_state())

    def begin_hover(self) -> bool:
        """Claim presentation for one supported drag without restarting it."""
        if self._hover_active:
            if self._current_state() is MochiState.EXCITED:
                return True
            self._hover_active = False
            return False
        if not self.can_receive():
            return False

        state = self._current_state()
        if state is MochiState.WALKING:
            self._cancel_walk()
        else:
            self._cancel_ambient()
        if not self._transition(MochiState.EXCITED):
            self._logger.warning(
                "Pocket hover presentation was rejected from %s",
                self._current_state().name,
            )
            self._resume_normal_presentation()
            return False

        self._hover_active = True
        self._play_animation("pocket_hover", None)
        return True

    def end_hover(self) -> None:
        """Release hover presentation after leave, cancellation, or failure."""
        if not self._hover_active:
            return
        self._hover_active = False
        self._resume_normal_presentation()

    def begin_offer(self) -> bool:
        """Play the short mouth-open reaction as the Pocket tray comes out.

        Presentation only: the caller opens the tray whether or not this
        succeeds, and nothing is written.
        """
        if self._busy or self._hover_active:
            return False
        state = self._current_state()
        if not can_start_pocket_offer(state):
            return False
        if state is MochiState.WALKING:
            self._cancel_walk()
        else:
            self._cancel_ambient()
        if not self._transition(MochiState.EXCITED):
            self._logger.warning(
                "Pocket offer presentation was rejected from %s",
                self._current_state().name,
            )
            return False
        self._mark_interaction()
        self._play_animation("pocket_offer", "idle")
        return True

    def receive(self, incoming: Iterable[PocketItem]) -> bool:
        candidates = tuple(incoming)
        if not candidates:
            self.reject_unsupported()
            self.end_hover()
            return False
        if not self.can_receive():
            self._show_feedback("My paws are full")
            self.end_hover()
            return False

        self._busy = True
        try:
            return self._persist_and_react(candidates)
        finally:
            self._busy = False

    def receive_image(self, png_bytes: bytes) -> bool:
        """Save transient texture data and commit it as one Pocket transaction."""
        if not self.can_receive():
            self._show_feedback("My paws are full")
            self.end_hover()
            return False
        self._busy = True
        try:
            try:
                item = self._store.save_raw_image(png_bytes)
            except (OSError, ValueError) as error:
                self._logger.warning("Could not save Pocket image: %s", error)
                self._show_feedback("I couldn't hold that")
                self.end_hover()
                return False
            return self._persist_and_react((item,))
        finally:
            self._busy = False

    def reject_unsupported(self) -> None:
        self._show_feedback("I can't hold that yet")

    def reject_busy(self) -> None:
        self._show_feedback("My paws are full")

    def remove(self, item_id: str) -> bool:
        if not any(item.id == item_id for item in self._items):
            return False
        try:
            remaining = self._store.remove(self._items, item_id)
        except OSError as error:
            self._logger.warning("Could not persist Pocket removal: %s", error)
            self._show_feedback("I couldn't update Pocket")
            return False
        self._items = tuple(remaining)
        self._on_changed(self._items)
        return True

    def clear_all(self) -> bool:
        """Clear Pocket metadata without ever deleting original user files."""
        if not self._items:
            return True
        try:
            remaining = self._store.clear(self._items)
        except OSError as error:
            self._logger.warning("Could not clear Pocket: %s", error)
            self._show_feedback("I couldn't update Pocket")
            return False
        self._items = tuple(remaining)
        self._on_changed(self._items)
        return True

    def _persist_and_react(self, candidates: tuple[PocketItem, ...]) -> bool:
        try:
            mutation = self._store.add_items(self._items, candidates)
        except OSError as error:
            self._logger.warning("Could not persist Pocket drop: %s", error)
            self._show_feedback("I couldn't hold that")
            self.end_hover()
            return False

        self._items = mutation.items
        self._on_changed(self._items)

        if self._hover_active:
            self._hover_active = False
            self._mark_interaction()
            self._play_animation("pocket_finish", "idle")
            self._show_feedback(
                self._held_message(len(candidates), len(mutation.evicted))
            )
            return True

        state = self._current_state()
        if state is MochiState.WALKING:
            self._cancel_walk()
        else:
            self._cancel_ambient()

        if not self._transition(MochiState.EXCITED):
            # Persistence is already authoritative. A transition rejection
            # cannot safely roll back the accepted content, so retain it and
            # report the presentation fault without replaying the animation.
            self._logger.warning(
                "Pocket persisted but receive presentation was rejected from %s",
                self._current_state().name,
            )
            self._show_feedback(
                self._held_message(len(candidates), len(mutation.evicted))
            )
            return True

        self._mark_interaction()
        self._play_animation("pocket_grab", "idle")
        self._show_feedback(
            self._held_message(len(candidates), len(mutation.evicted))
        )
        return True

    def _resume_normal_presentation(self) -> None:
        if self._current_state() is not MochiState.EXCITED:
            return
        if not self._transition(MochiState.IDLE):
            return
        self._play_animation("idle", None)
        self._resume_ambient()

    @staticmethod
    def _held_message(received: int, evicted: int) -> str:
        noun = "item" if received == 1 else "items"
        message = f"Held {received} {noun}"
        if evicted:
            removed = "item" if evicted == 1 else "items"
            message += f" · removed the oldest {evicted} {removed}"
        return message
