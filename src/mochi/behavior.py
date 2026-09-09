"""Mochi's small collection of v0.1 reactions."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

from mochi.animation import Animation
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


class OwnedTimer:
    """One replaceable timer source, independent of the GUI toolkit."""

    def __init__(
        self,
        add: Callable[[int, Callable[[], bool]], int],
        remove: Callable[[int], None],
    ) -> None:
        self._add = add
        self._remove = remove
        self.source_id: int | None = None

    def schedule(self, delay_ms: int, callback: Callable[[], bool]) -> None:
        self.cancel()

        def run() -> bool:
            self.source_id = None
            return callback()

        self.source_id = self._add(delay_ms, run)

    def cancel(self) -> None:
        if self.source_id is None:
            return
        self._remove(self.source_id)
        self.source_id = None


class SourceRegistry:
    """Own a set of GLib-style sources and cancel them together at shutdown."""

    def __init__(self, remove: Callable[[int], None]) -> None:
        self._remove = remove
        self._source_ids: set[int] = set()

    @property
    def count(self) -> int:
        return len(self._source_ids)

    def schedule(
        self,
        add: Callable[[int, Callable[[], bool]], int],
        delay: int,
        callback: Callable[[], bool],
    ) -> int:
        source_id = 0

        def run() -> bool:
            keep = callback()
            if not keep:
                self._source_ids.discard(source_id)
            return keep

        source_id = add(delay, run)
        self._source_ids.add(source_id)
        return source_id

    def cancel_all(self) -> None:
        for source_id in tuple(self._source_ids):
            self._remove(source_id)
        self._source_ids.clear()


@dataclass
class DragReleaseLatch:
    """Make drag completion idempotent across GTK's two release callbacks."""

    active: bool = False
    _click_release_pending: bool = False

    def prepare_press(self) -> None:
        self.active = False
        self._click_release_pending = False

    def begin(self) -> None:
        self.active = True
        self._click_release_pending = False

    def gesture_end(self) -> bool:
        if not self.active:
            return False
        self.active = False
        self._click_release_pending = True
        return True

    def click_release_consumed(self) -> bool:
        if self.active:
            self.active = False
            self._click_release_pending = False
            return True
        if self._click_release_pending:
            self._click_release_pending = False
            return True
        return False


class ClickGestureRouter:
    """Resolve one versus two clicks with one cancellable timer."""

    def __init__(
        self,
        timer: OwnedTimer,
        single_click: Callable[[], None],
        double_click: Callable[[], None],
        delay_ms: int,
    ) -> None:
        self._timer = timer
        self._single_click = single_click
        self._double_click = double_click
        self._delay_ms = delay_ms

    def press(self, presses: int) -> None:
        if presses >= 2:
            self._timer.cancel()

    def release(self, presses: int) -> None:
        if presses >= 2:
            self._timer.cancel()
            self._double_click()
            return

        def deliver_single_click() -> bool:
            self._single_click()
            return False

        self._timer.schedule(self._delay_ms, deliver_single_click)

    def cancel(self) -> None:
        self._timer.cancel()


CLICK_REACTION_STATES = frozenset(
    (MochiState.BOUNCING, MochiState.SQUISHING)
)
REACTION_STATES = CLICK_REACTION_STATES | frozenset((MochiState.EXCITED,))
EMOTE_ANIMATIONS = ("bounce", "squish", "excited", "heart", "idle_typing")
COMPUTER_EMOTE_DURATION_MS = (3_000, 4_000)
COMPUTER_IDLE_DELAY_MS = (45_000, 120_000)


def can_start_click_reaction(state: MochiState) -> bool:
    return state is MochiState.IDLE


def can_queue_click_reaction(state: MochiState) -> bool:
    return state in CLICK_REACTION_STATES


def can_start_heart(state: MochiState) -> bool:
    return state in (
        MochiState.IDLE,
        MochiState.BLINKING,
        MochiState.BOUNCING,
        MochiState.SQUISHING,
        MochiState.EXCITED,
        MochiState.TYPING,
    )


def can_start_typing(state: MochiState) -> bool:
    return state is MochiState.IDLE


def choose_emote(rng: random.Random | None = None) -> str:
    return (rng or random).choice(EMOTE_ANIMATIONS)


def choose_computer_emote_duration_ms(rng: random.Random | None = None) -> int:
    return (rng or random).randint(*COMPUTER_EMOTE_DURATION_MS)


def choose_computer_idle_delay_ms(rng: random.Random | None = None) -> int:
    return (rng or random).randint(*COMPUTER_IDLE_DELAY_MS)


def can_begin_sleep(state: MochiState) -> bool:
    return state not in (
        MochiState.FALLING_ASLEEP,
        MochiState.SLEEPING,
        MochiState.WAKING,
    )


def can_begin_wake(state: MochiState) -> bool:
    return state is MochiState.SLEEPING


def can_transition(current: MochiState, requested: MochiState) -> bool:
    """Allow state changes that respect Mochi's behavior priority."""
    if current is requested or requested is MochiState.IDLE:
        return True
    if current is MochiState.DRAGGED:
        return False
    if requested is MochiState.DRAGGED:
        return True
    if current is MochiState.FALLING_ASLEEP:
        return requested is MochiState.SLEEPING
    if current is MochiState.WAKING:
        return False
    if requested is MochiState.WAKING:
        return current is MochiState.SLEEPING
    if current is MochiState.SLEEPING:
        return False
    if requested is MochiState.FALLING_ASLEEP:
        return current in (
            MochiState.IDLE,
            MochiState.BLINKING,
            MochiState.WALKING,
            MochiState.HEART,
            MochiState.TYPING,
            *REACTION_STATES,
        )
    if requested is MochiState.SLEEPING:
        return current is MochiState.FALLING_ASLEEP
    if requested is MochiState.BLINKING:
        return current is MochiState.IDLE
    if requested is MochiState.HEART:
        return can_start_heart(current)
    if requested is MochiState.TYPING:
        return can_start_typing(current)
    if requested is MochiState.WALKING:
        return current is MochiState.IDLE
    if requested in REACTION_STATES:
        return current in (MochiState.IDLE, MochiState.WALKING)
    return True


@dataclass
class ClickReactionBuffer:
    queued: bool = False

    def request(self, state: MochiState) -> bool:
        if can_queue_click_reaction(state):
            self.queued = True
            return False
        return can_start_click_reaction(state)

    def consume(self) -> bool:
        queued = self.queued
        self.queued = False
        return queued

    def clear(self) -> None:
        self.queued = False


def choose_walk_animation(origin: tuple[int, int], target: tuple[int, int]) -> str:
    return "walk_left" if target[0] < origin[0] else "walk"


@dataclass(frozen=True)
class WalkMotion:
    origin: tuple[int, int]
    target: tuple[int, int]
    cycle_duration_ms: int
    speed_px_per_second: float = 72.0

    MIN_DISTANCE = 24.0

    @property
    def distance(self) -> float:
        return math.hypot(
            self.target[0] - self.origin[0],
            self.target[1] - self.origin[1],
        )

    @property
    def cycles(self) -> int:
        return max(1, round(self.distance / self.pixels_per_cycle))

    @property
    def duration_ms(self) -> int:
        return self.cycles * self.cycle_duration_ms

    @property
    def pixels_per_cycle(self) -> float:
        return self.speed_px_per_second * self.cycle_duration_ms / 1_000

    def progress(self, elapsed_ms: int) -> float:
        return min(1.0, max(0.0, elapsed_ms / self.duration_ms))

    def eased_progress(self, elapsed_ms: int) -> float:
        progress = self.progress(elapsed_ms)
        return progress * progress * (3.0 - 2.0 * progress)

    def position_at(self, elapsed_ms: int) -> tuple[int, int]:
        progress = self.eased_progress(elapsed_ms)
        return (
            round(self.origin[0] + (self.target[0] - self.origin[0]) * progress),
            round(self.origin[1] + (self.target[1] - self.origin[1]) * progress),
        )

    def animation_progress(self, elapsed_ms: int) -> float:
        distance = self.distance * self.eased_progress(elapsed_ms)
        return (distance / self.pixels_per_cycle) % 1.0


def choose_click_reaction(
    recent: tuple[str, ...] = (), rng: random.Random | None = None
) -> Animation:
    """Choose a tactile reaction, gently discouraging three repeats in a row."""
    generator = rng or random
    bounce_probability = 0.55
    if len(recent) >= 2 and recent[-1] == recent[-2]:
        bounce_probability = 0.40 if recent[-1] == "bounce" else 0.60
    name = "bounce" if generator.random() < bounce_probability else "squish"
    return ANIMATIONS[name]
