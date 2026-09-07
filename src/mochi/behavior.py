"""Mochi's small collection of v0.1 reactions."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from mochi.animation import Animation
from mochi.sprites import ANIMATIONS
from mochi.state import MochiState


CLICK_REACTION_STATES = frozenset(
    (MochiState.BOUNCING, MochiState.SQUISHING)
)
REACTION_STATES = CLICK_REACTION_STATES | frozenset((MochiState.EXCITED,))


def can_start_click_reaction(state: MochiState) -> bool:
    return state is MochiState.IDLE


def can_queue_click_reaction(state: MochiState) -> bool:
    return state in CLICK_REACTION_STATES


def can_begin_sleep(state: MochiState) -> bool:
    return state not in (MochiState.SLEEPING, MochiState.WAKING)


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
    if current is MochiState.WAKING:
        return False
    if requested is MochiState.WAKING:
        return current is MochiState.SLEEPING
    if current is MochiState.SLEEPING:
        return False
    if requested is MochiState.SLEEPING:
        return current in (
            MochiState.IDLE,
            MochiState.BLINKING,
            MochiState.WALKING,
            *REACTION_STATES,
        )
    if requested is MochiState.BLINKING:
        return current is MochiState.IDLE
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
