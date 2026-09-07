"""Time-based animation primitives independent from GTK drawing code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AnimationFrame:
    """One cached manifest frame plus an optional whole-frame movement offset."""

    sprite: str
    vertical_offset: float = 0.0
    duration_ms: int | None = None
    horizontal_offset: float = 0.0


@dataclass(frozen=True)
class Animation:
    name: str
    frames: tuple[AnimationFrame, ...]
    frame_duration_ms: int
    looping: bool = False
    next_state: str | None = "idle"


class AnimationPlayer:
    """Advances frames; GTK merely supplies the regular timer tick."""

    def __init__(self, on_finished: Callable[[Animation], None] | None = None) -> None:
        self.animation: Animation | None = None
        self.frame_index = 0
        self._elapsed_ms = 0
        self._on_finished = on_finished

    @property
    def frame(self) -> AnimationFrame | None:
        if self.animation is None:
            return None
        return self.animation.frames[self.frame_index]

    @property
    def elapsed_ms(self) -> int:
        """Elapsed time within the current frame, useful when resuming a loop."""
        return self._elapsed_ms

    @property
    def frame_duration_ms(self) -> int:
        if self.animation is None:
            return 0
        return self.frame.duration_ms or self.animation.frame_duration_ms

    def play(
        self,
        animation: Animation,
        frame_index: int = 0,
        elapsed_ms: int = 0,
    ) -> None:
        if not animation.frames:
            raise ValueError("An animation needs at least one frame")
        if not 0 <= frame_index < len(animation.frames):
            raise ValueError("Frame index is outside the animation")
        self.animation = animation
        self.frame_index = frame_index
        self._elapsed_ms = elapsed_ms % self.frame_duration_ms

    def stop(self) -> None:
        self.animation = None
        self.frame_index = 0
        self._elapsed_ms = 0

    def seek_progress(self, progress: float) -> bool:
        """Seek a looping animation to a normalized position and report frame changes."""
        animation = self.animation
        if animation is None or not animation.frames:
            return False

        progress = max(0.0, min(progress, 1.0))
        if animation.looping:
            progress %= 1.0
        total_duration = sum(
            frame.duration_ms or animation.frame_duration_ms
            for frame in animation.frames
        )
        elapsed = progress * total_duration
        frame_index = len(animation.frames) - 1
        frame_elapsed = 0
        for index, frame in enumerate(animation.frames):
            duration = frame.duration_ms or animation.frame_duration_ms
            if elapsed < duration or index == len(animation.frames) - 1:
                frame_index = index
                frame_elapsed = round(elapsed)
                break
            elapsed -= duration

        changed = (
            frame_index != self.frame_index or frame_elapsed != self._elapsed_ms
        )
        self.frame_index = frame_index
        self._elapsed_ms = frame_elapsed
        return changed

    def tick(self, elapsed_ms: int) -> bool:
        """Advance by elapsed time and return True when a frame changed."""
        animation = self.animation
        if animation is None:
            return False

        self._elapsed_ms += elapsed_ms
        changed = False
        while self._elapsed_ms >= self.frame_duration_ms:
            self._elapsed_ms -= self.frame_duration_ms
            if self.frame_index + 1 < len(animation.frames):
                self.frame_index += 1
                changed = True
            elif animation.looping:
                self.frame_index = 0
                changed = True
            else:
                self.animation = None
                if self._on_finished is not None:
                    self._on_finished(animation)
                return True
        return changed
