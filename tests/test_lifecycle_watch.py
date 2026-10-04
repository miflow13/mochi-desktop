"""Debug-only lifecycle watchdog: name the layer that stopped, change nothing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from mochi.animation import Animation, AnimationFrame
from mochi.lifecycle_watch import HANG_DUMP_SECONDS, LifecycleWatch, motion_budget_ms


@dataclass
class _Clock:
    now: float = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def watch(clock: _Clock) -> LifecycleWatch:
    return LifecycleWatch(
        logger=logging.getLogger("test.lifecycle"),
        snapshot=lambda: "state=IDLE_EMOTE anim=wave",
        clock=clock,
        arm_hang_dump=lambda _seconds: None,
        cancel_hang_dump=lambda: None,
    )


def _healthy_second(watch: LifecycleWatch, clock: _Clock) -> None:
    for _ in range(10):
        clock.advance(0.1)
        watch.tick(advanced=True, motion_budget_ms=100)
        watch.drew()
        watch.painted()


def test_healthy_playback_reports_nothing(watch, clock, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        for _ in range(5):
            _healthy_second(watch, clock)
            assert watch.check() == []

    assert "stall" not in caplog.text.lower()


def test_frames_advancing_without_drawing_is_a_draw_stall(watch, clock, caplog) -> None:
    _healthy_second(watch, clock)
    with caplog.at_level(logging.WARNING):
        for _ in range(25):
            clock.advance(0.1)
            watch.tick(advanced=True, motion_budget_ms=100)
        stalls = watch.check()

    assert stalls == ["draw"]
    assert "Lifecycle stall [draw]" in caplog.text
    assert "state=IDLE_EMOTE anim=wave" in caplog.text


def test_a_stall_is_reported_once_and_its_recovery_once(watch, clock, caplog) -> None:
    _healthy_second(watch, clock)
    for _ in range(25):
        clock.advance(0.1)
        watch.tick(advanced=True, motion_budget_ms=100)

    with caplog.at_level(logging.WARNING):
        assert watch.check() == ["draw"]
        clock.advance(1.0)
        watch.tick(advanced=True, motion_budget_ms=100)
        assert watch.check() == []
        watch.drew()
        watch.check()

    assert caplog.text.count("Lifecycle stall [draw]") == 1
    assert caplog.text.count("Lifecycle recovered [draw]") == 1


def test_animation_that_should_move_but_does_not_is_a_player_stall(
    watch, clock
) -> None:
    _healthy_second(watch, clock)
    for _ in range(25):
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=100)

    assert watch.check() == ["player"]


def test_slow_animations_get_a_proportionally_longer_budget(watch, clock) -> None:
    # A 1.5 s frame is not stalled after 2.5 s; it is after three frames' time.
    _healthy_second(watch, clock)
    for _ in range(25):
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=1_500)
    assert watch.check() == []

    for _ in range(25):
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=1_500)
    assert watch.check() == ["player"]


def test_held_presentation_is_not_a_player_stall(watch, clock) -> None:
    _healthy_second(watch, clock)
    for _ in range(100):
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=None)

    assert watch.check() == []


def test_animation_starting_after_a_held_pose_gets_a_fresh_budget(
    watch, clock
) -> None:
    # A held presentation never advances, so its time must not count against
    # the moving animation that follows it.
    _healthy_second(watch, clock)
    for _ in range(100):
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=None)

    clock.advance(0.1)
    watch.tick(advanced=False, motion_budget_ms=100)  # first tick of the new one
    assert watch.check() == []

    for _ in range(25):  # but it still has to move eventually
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=100)
    assert watch.check() == ["player"]


def test_missing_ticks_is_a_tick_stall(watch, clock) -> None:
    _healthy_second(watch, clock)
    clock.advance(3.0)

    assert watch.check() == ["ticks"]


def test_player_is_not_blamed_for_time_without_ticks(watch, clock) -> None:
    # A blocked main loop stops ticks; when they resume, the player gets a
    # fresh budget instead of inheriting the whole gap as a "player" stall.
    _healthy_second(watch, clock)
    clock.advance(9.0)
    watch.tick(advanced=False, motion_budget_ms=100)

    assert watch.check() == []
    for _ in range(25):
        clock.advance(0.1)
        watch.tick(advanced=False, motion_budget_ms=100)
    assert watch.check() == ["player"]


def test_stall_warning_says_whether_the_frame_clock_is_still_painting(
    watch, clock, caplog
) -> None:
    _healthy_second(watch, clock)
    for _ in range(25):
        clock.advance(0.1)
        watch.tick(advanced=True, motion_budget_ms=100)
        watch.painted()

    with caplog.at_level(logging.WARNING):
        watch.check()

    assert "last paint 0.0s ago" in caplog.text
    assert "last draw 2.5s ago" in caplog.text


def test_edges_are_logged_at_debug(watch, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        watch.edge("window unmap")

    assert "Lifecycle: window unmap" in caplog.text


def _animation(*durations: int, looping: bool = True) -> Animation:
    return Animation(
        name="test",
        frames=tuple(
            AnimationFrame(sprite=f"frame_{index}", duration_ms=duration)
            for index, duration in enumerate(durations)
        ),
        frame_duration_ms=100,
        looping=looping,
    )


def test_motion_budget_uses_the_longest_frame() -> None:
    assert motion_budget_ms(_animation(100, 400, 100), held=False) == 400


def test_single_frames_and_held_poses_have_no_motion_budget() -> None:
    assert motion_budget_ms(_animation(100), held=False) is None
    assert motion_budget_ms(_animation(100, 100), held=True) is None
    assert motion_budget_ms(None, held=False) is None


def test_every_check_rearms_the_hang_dump(clock) -> None:
    armed: list[float] = []
    watch = LifecycleWatch(
        logger=logging.getLogger("test.lifecycle"),
        snapshot=lambda: "",
        clock=clock,
        arm_hang_dump=armed.append,
        cancel_hang_dump=lambda: armed.append(-1.0),
    )

    watch.check()
    watch.check()
    watch.close()

    assert armed == [HANG_DUMP_SECONDS, HANG_DUMP_SECONDS, -1.0]


def test_debug_stack_dumps_register_sigusr1(monkeypatch) -> None:
    import faulthandler
    import signal

    from mochi import main as mochi_main

    calls = []
    monkeypatch.setattr(
        faulthandler, "register", lambda signum, **kwargs: calls.append((signum, kwargs))
    )

    mochi_main.enable_debug_stack_dumps()

    assert calls == [(signal.SIGUSR1, {"all_threads": True})]
