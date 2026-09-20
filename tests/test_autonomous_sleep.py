"""Unit coverage for Mochi's autonomous nap scheduler."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from mochi.autonomous_sleep import AutonomousSleepController
from mochi.state import MochiState, PresentationState


def _buddy():
    state = SimpleNamespace(
        current=MochiState.IDLE,
        presentation=PresentationState.NORMAL,
    )
    buddy = SimpleNamespace(
        state=state,
        _preview_mode=False,
        _presence_shutting_down=False,
        _user_idle=False,
        _context_menu_open=False,
        _hovered=False,
        _press=None,
        _current_animation="idle",
        _focus_session=None,
        _logger=Mock(),
    )

    def begin_sleep():
        buddy.state.current = MochiState.SLEEPING

    def wake_up():
        buddy.state.current = MochiState.WAKING

    buddy._begin_sleep = Mock(side_effect=begin_sleep)
    buddy._wake_up = Mock(side_effect=wake_up)
    return buddy


def _controller():
    buddy = _buddy()
    rng = Mock()
    controller = AutonomousSleepController(buddy, rng=rng)
    return controller, buddy, rng


def test_start_schedules_one_random_nap_opportunity() -> None:
    controller, buddy, rng = _controller()
    rng.randint.return_value = 900

    with patch(
        "mochi.autonomous_sleep.GLib.timeout_add_seconds",
        return_value=41,
    ) as timeout:
        controller.start()
        controller.start()

    timeout.assert_called_once_with(900, controller._try_start_nap)
    assert controller._nap_source_id == 41
    buddy._logger.debug.assert_called_once_with(
        "Autonomous nap opportunity scheduled in %d seconds",
        900,
    )


def test_trigger_now_replaces_pending_schedule_and_uses_normal_sleep_path() -> None:
    controller, buddy, rng = _controller()
    controller._nap_source_id = 41
    rng.randint.return_value = 75

    with (
        patch("mochi.autonomous_sleep.GLib.source_remove") as remove,
        patch(
            "mochi.autonomous_sleep.GLib.timeout_add_seconds",
            return_value=52,
        ) as timeout,
    ):
        result = controller.trigger_now_for_testing()

    assert result == 0
    remove.assert_called_once_with(41)
    buddy._begin_sleep.assert_called_once_with()
    assert controller.owns_sleep is True
    assert controller._nap_source_id is None
    assert controller._wake_source_id == 52
    timeout.assert_called_once_with(75, controller._wake_from_nap)


def test_nap_starts_through_existing_buddy_sleep_path() -> None:
    controller, buddy, rng = _controller()
    controller._nap_source_id = 41
    rng.randint.return_value = 75

    with patch(
        "mochi.autonomous_sleep.GLib.timeout_add_seconds",
        return_value=52,
    ) as timeout:
        result = controller._try_start_nap()

    assert result == 0
    buddy._begin_sleep.assert_called_once_with()
    assert buddy.state.current is MochiState.SLEEPING
    assert controller.owns_sleep is True
    assert controller._nap_source_id is None
    assert controller._wake_source_id == 52
    timeout.assert_called_once_with(75, controller._wake_from_nap)


def test_busy_state_defers_instead_of_forcing_sleep() -> None:
    controller, buddy, rng = _controller()
    controller._nap_source_id = 41
    buddy.state.current = MochiState.TYPING
    rng.randint.return_value = 1200

    with patch(
        "mochi.autonomous_sleep.GLib.timeout_add_seconds",
        return_value=53,
    ) as timeout:
        result = controller._try_start_nap()

    assert result == 0
    buddy._begin_sleep.assert_not_called()
    timeout.assert_called_once_with(1200, controller._try_start_nap)
    assert controller._nap_source_id == 53


def test_focus_and_presentation_ownership_block_autonomous_sleep() -> None:
    controller, buddy, _rng = _controller()

    buddy._focus_session = SimpleNamespace(active=True)
    assert controller._can_start_nap() is False

    buddy._focus_session = None
    buddy.state.presentation = PresentationState.LEVEL_UP
    assert controller._can_start_nap() is False

    buddy.state.presentation = PresentationState.NORMAL
    assert controller._can_start_nap() is True


def test_menu_hover_press_and_real_user_idle_block_nap() -> None:
    controller, buddy, _rng = _controller()

    buddy._context_menu_open = True
    assert controller._can_start_nap() is False
    buddy._context_menu_open = False

    buddy._hovered = True
    assert controller._can_start_nap() is False
    buddy._hovered = False

    buddy._press = (1.0, 2.0)
    assert controller._can_start_nap() is False
    buddy._press = None

    buddy._user_idle = True
    assert controller._can_start_nap() is False


def test_owned_nap_wakes_through_existing_buddy_wake_path() -> None:
    controller, buddy, rng = _controller()
    buddy.state.current = MochiState.SLEEPING
    controller._owns_sleep = True
    controller._wake_source_id = 52
    rng.randint.return_value = 1000

    with patch(
        "mochi.autonomous_sleep.GLib.timeout_add_seconds",
        return_value=61,
    ) as timeout:
        result = controller._wake_from_nap()

    assert result == 0
    buddy._wake_up.assert_called_once_with()
    assert controller.owns_sleep is False
    assert controller._wake_source_id is None
    assert controller._nap_source_id == 61
    timeout.assert_called_once_with(1000, controller._try_start_nap)


def test_scheduled_wake_releases_ownership_before_buddy_wake() -> None:
    controller, buddy, rng = _controller()
    buddy.state.current = MochiState.SLEEPING
    controller._owns_sleep = True
    controller._wake_source_id = 52
    rng.randint.return_value = 1000
    ownership_seen_during_wake = []

    def wake_up():
        ownership_seen_during_wake.append(controller.owns_sleep)
        buddy.state.current = MochiState.WAKING

    buddy._wake_up = Mock(side_effect=wake_up)

    with patch(
        "mochi.autonomous_sleep.GLib.timeout_add_seconds",
        return_value=61,
    ):
        controller._wake_from_nap()

    assert ownership_seen_during_wake == [False]
    assert controller.owns_sleep is False


def test_presence_idle_takes_over_instead_of_autonomous_wake() -> None:
    controller, buddy, rng = _controller()
    buddy.state.current = MochiState.SLEEPING
    buddy._user_idle = True
    controller._owns_sleep = True
    controller._wake_source_id = 52
    rng.randint.return_value = 1000

    with patch(
        "mochi.autonomous_sleep.GLib.timeout_add_seconds",
        return_value=62,
    ):
        controller._wake_from_nap()

    buddy._wake_up.assert_not_called()
    assert buddy.state.current is MochiState.SLEEPING
    assert controller.owns_sleep is False


def test_external_wake_cancels_stale_auto_wake_and_reschedules() -> None:
    controller, _buddy, rng = _controller()
    controller._owns_sleep = True
    controller._wake_source_id = 52
    rng.randint.return_value = 1000

    with (
        patch("mochi.autonomous_sleep.GLib.source_remove") as remove,
        patch(
            "mochi.autonomous_sleep.GLib.timeout_add_seconds",
            return_value=63,
        ),
    ):
        controller.note_external_wake()

    remove.assert_called_once_with(52)
    assert controller.owns_sleep is False
    assert controller._wake_source_id is None
    assert controller._nap_source_id == 63


def test_stop_removes_both_sources_and_releases_ownership() -> None:
    controller, _buddy, _rng = _controller()
    controller._nap_source_id = 41
    controller._wake_source_id = 52
    controller._owns_sleep = True

    with patch("mochi.autonomous_sleep.GLib.source_remove") as remove:
        controller.stop()

    assert remove.call_args_list == [call(41), call(52)]
    assert controller._nap_source_id is None
    assert controller._wake_source_id is None
    assert controller.owns_sleep is False
