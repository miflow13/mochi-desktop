"""Pocket hover dwell rules, driven by a deterministic clock."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mochi.pocket_hover import (
    DEFAULT_POCKET_HOVER_DELAY_MS,
    DwellPhase,
    PocketHoverDwell,
    normalize_hover_delay_ms,
)


class _Clock:
    """Stand-in for GLib.timeout_add/source_remove with manual time."""

    def __init__(self) -> None:
        self.now = 0
        self._next_id = 1
        self.pending: dict[int, tuple[int, Callable[[], bool]]] = {}

    def timeout_add(self, delay_ms: int, callback: Callable[[], bool]) -> int:
        source_id = self._next_id
        self._next_id += 1
        self.pending[source_id] = (self.now + delay_ms, callback)
        return source_id

    def source_remove(self, source_id: int) -> bool:
        assert source_id in self.pending, f"removed unknown source {source_id}"
        del self.pending[source_id]
        return True

    def advance(self, delta_ms: int) -> None:
        target = self.now + delta_ms
        while True:
            due = sorted(
                (when, source_id)
                for source_id, (when, _callback) in self.pending.items()
                if when <= target
            )
            if not due:
                break
            when, source_id = due[0]
            _when, callback = self.pending.pop(source_id)
            self.now = when
            assert callback() is False, "dwell timers are one-shot"
        self.now = target


class _Harness:
    def __init__(
        self,
        *,
        delay_ms: int = 2000,
        can_arm: bool = True,
        open_ok: bool = True,
    ) -> None:
        self.clock = _Clock()
        self.delay = delay_ms
        self.allowed = can_arm
        self.open_ok = open_ok
        self.events: list[str] = []
        self.dwell = PocketHoverDwell(
            delay_ms=lambda: self.delay,
            can_arm=lambda: self.allowed,
            show_peek=lambda fill_ms: self.events.append(f"peek:{fill_ms}"),
            hide_peek=lambda: self.events.append("hide-peek"),
            open_tray=self._open,
            close_tray=lambda: self.events.append("close"),
            timeout_add=self.clock.timeout_add,
            source_remove=self.clock.source_remove,
        )

    def _open(self, focus: bool) -> bool:
        self.events.append("open:focus" if focus else "open:hover")
        return self.open_ok

    def rest(self) -> None:
        self.dwell.pointer_entered()
        self.dwell.pointer_moved()

    def open_by_hover(self) -> None:
        self.rest()
        self.clock.advance(self.delay)
        assert self.dwell.phase is DwellPhase.OPEN
        self.events.clear()


def test_enter_without_motion_never_arms() -> None:
    harness = _Harness()
    harness.dwell.pointer_entered()

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.dwell.phase is DwellPhase.IDLE


def test_motion_peeks_at_600_ms_then_opens_at_the_dwell() -> None:
    harness = _Harness()
    harness.rest()

    harness.clock.advance(599)
    assert harness.events == []
    harness.clock.advance(1)
    assert harness.events == ["peek:1400"]
    assert harness.dwell.phase is DwellPhase.PEEK
    harness.clock.advance(1399)
    assert harness.events == ["peek:1400"]
    harness.clock.advance(1)

    assert harness.events == ["peek:1400", "open:hover"]
    assert harness.dwell.phase is DwellPhase.OPEN
    assert harness.dwell.pinned is False
    assert harness.clock.pending == {}


@pytest.mark.parametrize(("delay", "fill"), ((1500, 900), (3000, 2400)))
def test_peek_fills_for_the_rest_of_the_chosen_dwell(delay: int, fill: int) -> None:
    harness = _Harness(delay_ms=delay)
    harness.rest()

    harness.clock.advance(delay)

    assert harness.events == [f"peek:{fill}", "open:hover"]


def test_leaving_during_the_peek_hides_it_and_resets() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(1000)

    harness.dwell.pointer_left()
    harness.clock.advance(5000)

    assert harness.events == ["peek:1400", "hide-peek"]
    assert harness.dwell.phase is DwellPhase.IDLE
    assert harness.clock.pending == {}


def test_leaving_before_the_peek_resets_silently() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(300)

    harness.dwell.pointer_left()
    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.clock.pending == {}


def test_off_never_arms() -> None:
    harness = _Harness(delay_ms=0)
    harness.rest()

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.clock.pending == {}


def test_blocked_motion_never_arms() -> None:
    harness = _Harness(can_arm=False)
    harness.rest()

    harness.clock.advance(5000)

    assert harness.events == []


def test_condition_lost_before_the_peek_resets_without_showing_it() -> None:
    harness = _Harness()
    harness.rest()
    harness.allowed = False

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.dwell.phase is DwellPhase.IDLE
    assert harness.clock.pending == {}


def test_condition_lost_during_the_peek_hides_it_at_the_open_point() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(600)
    harness.allowed = False

    harness.clock.advance(1400)

    assert harness.events == ["peek:1400", "hide-peek"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_setting_turned_off_mid_dwell_cancels_at_the_next_due_point() -> None:
    harness = _Harness()
    harness.rest()
    harness.delay = 0

    harness.clock.advance(5000)

    assert harness.events == []
    assert harness.clock.pending == {}


def test_repeated_motion_does_not_restart_the_dwell() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(1000)
    for _ in range(3):
        harness.dwell.pointer_moved()

    harness.clock.advance(1000)

    assert harness.events == ["peek:1400", "open:hover"]


def test_no_reopen_loop_until_the_pointer_leaves() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.close()
    assert harness.events == ["close"]

    harness.dwell.pointer_moved()
    harness.clock.advance(5000)
    assert harness.events == ["close"]

    harness.dwell.pointer_left()
    harness.rest()
    harness.clock.advance(2000)
    assert harness.events == ["close", "peek:1400", "open:hover"]


def test_leaving_mochi_and_the_tray_closes_after_the_grace() -> None:
    harness = _Harness()
    harness.open_by_hover()

    harness.dwell.pointer_left()
    harness.clock.advance(449)
    assert harness.events == []
    harness.clock.advance(1)

    assert harness.events == ["close"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_crossing_into_the_tray_keeps_it_open() -> None:
    harness = _Harness()
    harness.open_by_hover()

    harness.dwell.pointer_left()
    harness.clock.advance(200)
    harness.dwell.tray_entered()
    harness.clock.advance(1000)
    assert harness.events == []

    harness.dwell.tray_left()
    harness.clock.advance(450)
    assert harness.events == ["close"]


def test_returning_to_mochi_cancels_the_grace_close() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.pointer_left()
    harness.clock.advance(200)

    harness.dwell.pointer_entered()
    harness.clock.advance(1000)

    assert harness.events == []
    assert harness.dwell.phase is DwellPhase.OPEN


def test_press_resets_arming_and_waits_for_leave() -> None:
    harness = _Harness()
    harness.rest()
    harness.clock.advance(1000)

    harness.dwell.interrupt()
    harness.dwell.pointer_moved()
    harness.clock.advance(3000)
    assert harness.events == ["peek:1400", "hide-peek"]

    harness.dwell.pointer_left()
    harness.rest()
    harness.clock.advance(2000)
    assert harness.events[-1] == "open:hover"


def test_press_closes_a_hover_tray() -> None:
    harness = _Harness()
    harness.open_by_hover()

    harness.dwell.interrupt()

    assert harness.events == ["close"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_drag_out_suppresses_the_grace_close() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.pointer_left()
    harness.dwell.tray_entered()

    harness.dwell.drag_started()
    harness.dwell.tray_left()
    harness.clock.advance(2000)
    assert harness.events == []

    harness.dwell.drag_finished(False)
    harness.clock.advance(450)
    assert harness.events == ["close"]


def test_delivered_drag_closes_the_tray() -> None:
    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.drag_started()

    harness.dwell.drag_finished(True)

    assert harness.events == ["close"]


def test_menu_tray_ignores_pointer_leave() -> None:
    harness = _Harness()

    assert harness.dwell.open_pinned() is True
    assert harness.events == ["open:focus"]
    assert harness.dwell.pinned is True
    harness.dwell.pointer_entered()
    harness.dwell.pointer_left()
    harness.dwell.tray_left()
    harness.clock.advance(5000)
    assert harness.events == ["open:focus"]

    harness.dwell.close()
    assert harness.events == ["open:focus", "close"]
    assert harness.dwell.pinned is False


def test_failed_open_hides_the_peek_and_waits_for_leave() -> None:
    harness = _Harness(open_ok=False)
    harness.rest()

    harness.clock.advance(2000)
    harness.dwell.pointer_moved()
    harness.clock.advance(3000)

    assert harness.events == ["peek:1400", "open:hover", "hide-peek"]
    assert harness.dwell.phase is DwellPhase.IDLE


def test_shutdown_cancels_every_timer() -> None:
    harness = _Harness()
    harness.rest()
    harness.dwell.shutdown()
    assert harness.clock.pending == {}

    harness = _Harness()
    harness.open_by_hover()
    harness.dwell.pointer_left()
    harness.dwell.shutdown()
    assert harness.clock.pending == {}
    assert harness.dwell.phase is DwellPhase.IDLE


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (0, 0),
        (1500, 1500),
        (2000, 2000),
        (3000, 3000),
        (2500, DEFAULT_POCKET_HOVER_DELAY_MS),
        (-1, DEFAULT_POCKET_HOVER_DELAY_MS),
        (True, DEFAULT_POCKET_HOVER_DELAY_MS),
        ("2000", DEFAULT_POCKET_HOVER_DELAY_MS),
        (None, DEFAULT_POCKET_HOVER_DELAY_MS),
    ),
)
def test_only_supported_delays_survive_normalization(raw, expected: int) -> None:
    assert normalize_hover_delay_ms(raw) == expected
