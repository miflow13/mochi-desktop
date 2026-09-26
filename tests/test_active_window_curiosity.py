"""Regression coverage for active-window curiosity presentation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import cairo

from mochi.presence.curiosity import ActiveWindowCuriosityMixin
from mochi.state import MochiState, StateMachine


class _CuriosityBase:
    def __init__(self) -> None:
        self._presence_app_category = "browser"
        self._preview_mode = False
        self._presence_shutting_down = False
        self._user_idle = False
        self._context_menu_open = False
        self._press = None
        self._drag_started = False
        self._ambient_presence_engine = SimpleNamespace(
            tuning=SimpleNamespace(
                ambient_reactions_enabled=True,
                quiet_mode=False,
            )
        )
        self.state = StateMachine()
        self.queue_draw = Mock()
        self._logger = Mock()
        self._placement = None
        self.base_shutdown_called = False
        self.base_press_args = None

    def _on_presence_app_category_changed(self, category: str) -> None:
        self._presence_app_category = category

    def _on_presence_app_focus_changed(self, _category: str) -> None:
        pass

    def _draw(self, _area, context, _width: int, _height: int) -> None:
        context.rectangle(48, 78, 16, 24)
        context.set_source_rgba(0.2, 0.6, 0.3, 1.0)
        context.fill()

    def _tick(self) -> bool:
        return True

    def _on_pressed(self, *args) -> None:
        self.base_press_args = args

    def shutdown_presence(self) -> None:
        self.base_shutdown_called = True


class CuriosityHarness(ActiveWindowCuriosityMixin, _CuriosityBase):
    pass


def _render(buddy: CuriosityHarness, *, now: float) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 112, 112)
    context = cairo.Context(surface)
    with patch("mochi.presence.curiosity.time.monotonic", return_value=now):
        buddy._draw(None, context, 112, 112)
    surface.flush()
    return bytes(surface.get_data())


def test_category_reclassification_does_not_trigger_curiosity() -> None:
    buddy = CuriosityHarness()

    with patch("mochi.presence.curiosity.GLib.timeout_add") as timeout_add:
        buddy._on_presence_app_category_changed("terminal")

    assert buddy._presence_app_category == "terminal"
    assert buddy._curiosity_pending_category is None
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_category is None
    timeout_add.assert_not_called()


def test_unknown_category_uses_generic_question_cue() -> None:
    buddy = CuriosityHarness()

    with patch(
        "mochi.presence.curiosity.GLib.timeout_add",
        return_value=22,
    ) as timeout_add:
        buddy._schedule_curiosity_cue("unknown")

    assert buddy._curiosity_pending_category == "unknown"
    assert buddy._curiosity_source_id == 22
    timeout_add.assert_called_once_with(
        buddy.CURIOSITY_DEBOUNCE_MS,
        buddy._show_scheduled_curiosity,
    )



def test_same_category_focus_pulse_still_schedules_curiosity() -> None:
    buddy = CuriosityHarness()
    buddy._presence_app_category = "browser"

    with patch(
        "mochi.presence.curiosity.GLib.timeout_add",
        return_value=77,
    ) as timeout_add:
        buddy._on_presence_app_focus_changed("browser")

    assert buddy._presence_app_category == "browser"
    assert buddy._curiosity_pending_category == "browser"
    assert buddy._curiosity_source_id == 77
    timeout_add.assert_called_once()


def test_curiosity_can_start_while_contextual_work_state_is_active() -> None:
    buddy = CuriosityHarness()
    buddy.state.transition_to(MochiState.TYPING)

    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is True

    assert buddy._curiosity_category == "browser"



def test_same_category_curiosity_has_longer_cooldown() -> None:
    buddy = CuriosityHarness()

    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is True

    buddy._clear_curiosity_cue()
    with patch("mochi.presence.curiosity.time.monotonic", return_value=20.0):
        assert buddy._begin_curiosity_cue("browser") is False

    with patch("mochi.presence.curiosity.time.monotonic", return_value=40.1):
        assert buddy._begin_curiosity_cue("browser") is True


def test_different_category_can_react_after_short_global_gap() -> None:
    buddy = CuriosityHarness()

    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is True

    buddy._clear_curiosity_cue()
    with patch("mochi.presence.curiosity.time.monotonic", return_value=13.0):
        assert buddy._begin_curiosity_cue("terminal") is True


def test_curiosity_respects_state_and_ambisense_suppression() -> None:
    buddy = CuriosityHarness()
    buddy.state.transition_to(MochiState.SLEEPING)

    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is False

    buddy.state.transition_to(MochiState.IDLE)
    buddy._ambient_presence_engine.tuning.quiet_mode = True
    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is False

    buddy._ambient_presence_engine.tuning.quiet_mode = False
    buddy._ambient_presence_engine.tuning.ambient_reactions_enabled = False
    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is False


def test_cowork_state_may_finish_an_already_started_curiosity_cue() -> None:
    buddy = CuriosityHarness()

    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("vscode") is True

    buddy.state.transition_to(MochiState.TYPING)
    buddy.queue_draw.reset_mock()
    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.7):
        assert buddy._tick() is True

    assert buddy._curiosity_category == "vscode"
    buddy.queue_draw.assert_called_once_with()


def test_direct_interaction_clears_an_active_curiosity_cue() -> None:
    buddy = CuriosityHarness()

    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.0):
        assert buddy._begin_curiosity_cue("browser") is True

    buddy._press = object()
    buddy.queue_draw.reset_mock()
    with patch("mochi.presence.curiosity.time.monotonic", return_value=10.2):
        assert buddy._tick() is True

    assert buddy._curiosity_category is None
    buddy.queue_draw.assert_called_once_with()


def test_direct_press_immediately_cancels_pending_and_active_curiosity() -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 42
    buddy._curiosity_pending_category = "terminal"
    buddy._curiosity_category = "browser"

    with patch("mochi.presence.curiosity.GLib.source_remove") as source_remove:
        buddy._on_pressed("gesture", 1, 12.0, 18.0)

    source_remove.assert_called_once_with(42)
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_category is None
    assert buddy._curiosity_category is None
    assert buddy.base_press_args == ("gesture", 1, 12.0, 18.0)


def test_curiosity_draw_adds_bubble_and_temporary_body_lean() -> None:
    buddy = CuriosityHarness()
    baseline = _render(buddy, now=10.0)

    buddy._curiosity_category = "terminal"
    buddy._curiosity_started_at = 10.0
    curious = _render(buddy, now=10.6)

    assert curious != baseline


def test_expired_curiosity_clears_without_changing_behavior_state() -> None:
    buddy = CuriosityHarness()
    original_state = buddy.state.current
    buddy._curiosity_category = "browser"
    buddy._curiosity_started_at = 10.0

    with patch("mochi.presence.curiosity.time.monotonic", return_value=12.0):
        assert buddy._tick() is True

    assert buddy._curiosity_category is None
    assert buddy.state.current is original_state


def test_shutdown_cancels_pending_curiosity_and_preserves_chain() -> None:
    buddy = CuriosityHarness()
    buddy._curiosity_source_id = 42
    buddy._curiosity_pending_category = "terminal"
    buddy._curiosity_category = "terminal"

    with patch("mochi.presence.curiosity.GLib.source_remove") as source_remove:
        buddy.shutdown_presence()

    source_remove.assert_called_once_with(42)
    assert buddy._curiosity_source_id is None
    assert buddy._curiosity_pending_category is None
    assert buddy._curiosity_category is None
    assert buddy.base_shutdown_called is True
