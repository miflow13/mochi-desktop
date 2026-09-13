"""Regression coverage for the user-triggered feeding interaction."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from mochi.behavior import can_transition
from mochi.presence.feeding import FeedMochiMixin
from mochi.state import MochiState


class _MenuBase:
    def _build_context_menu(self):
        return "menu"

    def _make_menu_button(self, label, icon, callback):
        self.button_args = (label, icon, callback)
        return "feed-button", "feed-label"

    def _register_context_menu_row(self, row_id, widget, **kwargs):
        self.registered_row = (row_id, widget, kwargs)


class _MenuHarness(FeedMochiMixin, _MenuBase):
    pass


class _FinishBase:
    def _finish_reaction(self, finished_animation) -> None:
        self.base_finish_calls.append(finished_animation)
        self.finish_order.append("base")


class _FinishHarness(FeedMochiMixin, _FinishBase):
    pass


class _CareHookBase:
    def _on_feed_animation_completed(self) -> None:
        self.care_hook_calls += 1


class _CareHookHarness(FeedMochiMixin, _CareHookBase):
    pass


def _runtime_harness(state: MochiState):
    harness = object.__new__(FeedMochiMixin)
    harness.state = SimpleNamespace(current=state)
    harness._logger = Mock()
    harness._cancel_walk = Mock()
    harness._cancel_active_emote = Mock()
    harness._transition_to = Mock(return_value=True)
    harness._play_animation = Mock()
    harness._on_feed_animation_started = Mock()
    harness._last_interaction = 0.0
    return harness


def test_feed_row_is_inserted_before_sleep() -> None:
    harness = _MenuHarness()

    assert harness._build_context_menu() == "menu"
    label, icon, callback = harness.button_args
    assert label == "Feed"
    assert icon == "emblem-favorite-symbolic"
    assert callback == harness._feed_from_context_menu
    assert harness.registered_row == (
        "feed",
        "feed-button",
        {"before": "sleep"},
    )


def test_feed_menu_action_closes_menu_before_starting_animation() -> None:
    harness = object.__new__(FeedMochiMixin)
    harness._close_context_menu_then = Mock()
    harness._start_feeding = Mock()

    harness._feed_from_context_menu(None)

    harness._close_context_menu_then.assert_called_once_with(harness._start_feeding)


def test_start_feeding_owns_state_and_plays_one_shot() -> None:
    harness = _runtime_harness(MochiState.IDLE)

    assert harness._start_feeding() is True

    harness._cancel_active_emote.assert_called_once_with()
    harness._cancel_walk.assert_not_called()
    harness._transition_to.assert_called_once_with(MochiState.EATING)
    harness._play_animation.assert_called_once_with("eat", after="idle")
    harness._on_feed_animation_started.assert_called_once_with()
    assert harness._last_interaction > 0


def test_walking_is_cancelled_before_feeding() -> None:
    harness = _runtime_harness(MochiState.WALKING)

    assert harness._start_feeding() is True

    harness._cancel_walk.assert_called_once_with()
    harness._transition_to.assert_called_once_with(MochiState.EATING)


def test_sleeping_mochi_cannot_feed() -> None:
    harness = _runtime_harness(MochiState.SLEEPING)

    assert harness._start_feeding() is False

    harness._cancel_active_emote.assert_not_called()
    harness._transition_to.assert_not_called()
    harness._play_animation.assert_not_called()
    harness._on_feed_animation_started.assert_not_called()


def test_rejected_transition_does_not_start_animation_or_hooks() -> None:
    harness = _runtime_harness(MochiState.IDLE)
    harness._transition_to.return_value = False

    assert harness._start_feeding() is False

    harness._play_animation.assert_not_called()
    harness._on_feed_animation_started.assert_not_called()


def test_completed_eat_forces_heart_before_future_care_hook() -> None:
    harness = object.__new__(_FinishHarness)
    animation = SimpleNamespace(name="eat")
    harness._active_animation = animation
    harness.state = SimpleNamespace(current=MochiState.EATING)
    harness.base_finish_calls = []
    harness.finish_order = []

    def start_heart(*, ignore_cooldown: bool) -> bool:
        assert ignore_cooldown is True
        harness.finish_order.append("heart")
        return True

    harness._start_heart_emote = Mock(side_effect=start_heart)
    harness._on_feed_animation_completed = Mock(
        side_effect=lambda: harness.finish_order.append("care")
    )
    harness._logger = Mock()

    harness._finish_reaction(animation)

    assert harness.base_finish_calls == [animation]
    assert harness.finish_order == ["base", "heart", "care"]
    harness._start_heart_emote.assert_called_once_with(ignore_cooldown=True)
    harness._on_feed_animation_completed.assert_called_once_with()
    harness._logger.warning.assert_not_called()


def test_completed_eat_logs_if_forced_heart_cannot_start() -> None:
    harness = object.__new__(_FinishHarness)
    animation = SimpleNamespace(name="eat")
    harness._active_animation = animation
    harness.state = SimpleNamespace(current=MochiState.EATING)
    harness.base_finish_calls = []
    harness.finish_order = []
    harness._start_heart_emote = Mock(return_value=False)
    harness._on_feed_animation_completed = Mock()
    harness._logger = Mock()

    harness._finish_reaction(animation)

    harness._start_heart_emote.assert_called_once_with(ignore_cooldown=True)
    harness._logger.warning.assert_called_once_with(
        "Post-feed heart could not start after eating completed"
    )
    harness._on_feed_animation_completed.assert_called_once_with()


def test_interrupted_eat_does_not_award_completion_hook_or_start_heart() -> None:
    harness = object.__new__(_FinishHarness)
    finished = SimpleNamespace(name="eat")
    harness._active_animation = SimpleNamespace(name="pickup")
    harness.state = SimpleNamespace(current=MochiState.PICKUP)
    harness.base_finish_calls = []
    harness.finish_order = []
    harness._start_heart_emote = Mock()
    harness._on_feed_animation_completed = Mock()
    harness._logger = Mock()

    harness._finish_reaction(finished)

    assert harness.base_finish_calls == [finished]
    harness._start_heart_emote.assert_not_called()
    harness._on_feed_animation_completed.assert_not_called()


def test_feed_completion_hook_delegates_to_later_care_mixins() -> None:
    harness = object.__new__(_CareHookHarness)
    harness.care_hook_calls = 0

    FeedMochiMixin._on_feed_animation_completed(harness)

    assert harness.care_hook_calls == 1


def test_eating_can_interrupt_ambient_but_not_critical_states() -> None:
    assert can_transition(MochiState.DANCING, MochiState.EATING)
    assert can_transition(MochiState.WATCHING, MochiState.EATING)
    assert can_transition(MochiState.BOUNCING, MochiState.EATING)
    assert not can_transition(MochiState.SLEEPING, MochiState.EATING)
    assert not can_transition(MochiState.DRAGGED, MochiState.EATING)
