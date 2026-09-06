"""Time-based animation primitives independent from GTK drawing code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AnimationFrame:
    """One cached atlas sprite plus an optional whole-frame movement offset."""

    sprite: str
    vertical_offset: float = 0.0


@dataclass(frozen=True)
class Animation:
    name: str
    frames: tuple[AnimationFrame, ...]
    frame_duration_ms: int
    looping: bool = False
    next_state: str | None = "idle"


class AnimationPlayer:
    """Advances frames; GTK merely supplies the regular timer tick."""

    def __init__(self, on_finished: Callable[[], None] | None = None) -> None:
        self.animation: Animation | None = None
        self.frame_index = 0
        self._elapsed_ms = 0
        self._on_finished = on_finished

    @property
    def frame(self) -> AnimationFrame | None:
        if self.animation is None:
            return None
        return self.animation.frames[self.frame_index]

    def play(self, animation: Animation) -> None:
        if not animation.frames:
            raise ValueError("An animation needs at least one frame")
        self.animation = animation
        self.frame_index = 0
        self._elapsed_ms = 0

    def stop(self) -> None:
        self.animation = None
        self.frame_index = 0
        self._elapsed_ms = 0

    def tick(self, elapsed_ms: int) -> bool:
        """Advance by elapsed time and return True when a frame changed."""
        animation = self.animation
        if animation is None:
            return False

        self._elapsed_ms += elapsed_ms
        changed = False
        while self._elapsed_ms >= animation.frame_duration_ms:
            self._elapsed_ms -= animation.frame_duration_ms
            if self.frame_index + 1 < len(animation.frames):
                self.frame_index += 1
                changed = True
            elif animation.looping:
                self.frame_index = 0
                changed = True
            else:
                self.animation = None
                if self._on_finished is not None:
                    self._on_finished()
                return True
        return changed
