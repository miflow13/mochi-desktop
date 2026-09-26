"""Runtime update-check, notification, and menu integration tests."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock

from mochi.update.model import (
    InstalledBuild,
    UpdateCheckResult,
    UpdateMetadata,
    UpdateStatus,
    UpdateTarget,
)
from mochi.presence.click_dialogue import PresenceBuddy, PresenceX11Buddy
from mochi.presence.update_controls import UpdateControlsMixin


def _target(commit: str = "new-sha") -> UpdateTarget:
    return UpdateTarget(
        commit=commit,
        metadata=UpdateMetadata(
            version="0.4.0a1",
            channel="main",
            highlights=("one", "two"),
        ),
    )


class _Config:
    def __init__(self) -> None:
        self.dismissed: str | None = None

    def save_dismissed_update_commit(self, commit: str | None) -> None:
        self.dismissed = commit


class _Base:
    def __init__(self, *, preview_mode: bool = False) -> None:
        self._preview_mode = preview_mode
        self._config = _Config()
        self._logger = Mock()
        self._presence_bubble = Mock()
        self._presence_bubble.show.return_value = True
        self.state = SimpleNamespace(dialogue_allowed=True)
        self.transition_calls = 0
        self.shutdown_calls = 0
        self.registered = None
        self._made_button = object()
        self._made_label = Mock()

    def _transition_to(self, *_args, **_kwargs):
        self.transition_calls += 1

    def _make_menu_button(self, label, icon, callback):
        self.menu_button_args = (label, icon, callback)
        return self._made_button, self._made_label

    def _register_context_menu_row(self, row_id, widget, **kwargs):
        self.registered = (row_id, widget, kwargs)

    def _build_context_menu(self):
        return "menu"

    def shutdown_presence(self) -> None:
        self.shutdown_calls += 1


class _Harness(UpdateControlsMixin, _Base):
    def __init__(self, *, preview_mode: bool = False) -> None:
        self.scheduled = 0
        self.manual_checks: list[bool] = []
        self.opened_targets: list[UpdateTarget] = []
        self.destroyed = 0
        super().__init__(preview_mode=preview_mode)

    def _schedule_update_startup_check(self) -> None:
        self.scheduled += 1

    def _start_update_check(self, *, manual: bool) -> None:
        self.manual_checks.append(manual)

    def _show_update_window(self, target: UpdateTarget) -> None:
        self.opened_targets.append(target)

    def _destroy_update_window(self) -> None:
        self.destroyed += 1


def test_preview_mode_does_not_schedule_automatic_update_check() -> None:
    buddy = _Harness(preview_mode=True)
    assert buddy.scheduled == 0


def test_normal_runtime_schedules_one_delayed_update_check() -> None:
    buddy = _Harness(preview_mode=False)
    assert buddy.scheduled == 1


def test_context_menu_adds_update_row_after_quick_start() -> None:
    buddy = _Harness()

    assert buddy._build_context_menu() == "menu"
    assert buddy.menu_button_args[0] == "Check for updates"
    assert buddy.registered == (
        "update",
        buddy._made_button,
        {"after": "quick-start"},
    )


def test_available_update_changes_menu_label_and_shows_one_bubble_without_state_change() -> None:
    buddy = _Harness()
    buddy._build_context_menu()
    result = UpdateCheckResult(
        status=UpdateStatus.UPDATE_AVAILABLE,
        target=_target(),
        announce=True,
    )

    assert buddy._apply_update_check_result(result, manual=False) is False
    assert buddy._update_menu_label.set_text.call_args.args[0] == "Update available"
    buddy._presence_bubble.show.assert_called_once()
    assert "psst" in buddy._presence_bubble.show.call_args.args[0]
    assert buddy.transition_calls == 0

    buddy._apply_update_check_result(result, manual=False)
    buddy._presence_bubble.show.assert_called_once()


def test_busy_dialogue_state_does_not_force_notification_or_state_transition() -> None:
    buddy = _Harness()
    buddy.state.dialogue_allowed = False

    buddy._apply_update_check_result(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            target=_target(),
            announce=True,
        ),
        manual=False,
    )

    buddy._presence_bubble.show.assert_not_called()
    assert buddy.transition_calls == 0


def test_dismissed_target_is_saved_and_not_reannounced() -> None:
    buddy = _Harness()
    target = _target()
    buddy._update_target = target

    buddy._dismiss_update_target()

    assert buddy._config.dismissed == "new-sha"
    assert "new-sha" in buddy._update_announced_commits


def test_manual_available_result_opens_update_window() -> None:
    buddy = _Harness()
    target = _target()

    buddy._apply_update_check_result(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            target=target,
            announce=False,
        ),
        manual=True,
    )

    assert buddy.opened_targets == [target]


def test_menu_action_checks_manually_when_no_target_and_opens_known_target() -> None:
    buddy = _Harness()
    buddy._handle_update_menu_action()
    assert buddy.manual_checks == [True]

    target = _target()
    buddy._update_target = target
    buddy._handle_update_menu_action()
    assert buddy.opened_targets == [target]


def test_update_restart_bootstraps_exact_target_then_quits_application(monkeypatch) -> None:
    buddy = _Harness()
    target = _target()
    buddy._update_target = target
    bootstrap = Mock()
    application = Mock()
    monkeypatch.setattr(
        "mochi.presence.update_controls.bootstrap_updater",
        bootstrap,
    )
    monkeypatch.setattr(
        "mochi.presence.update_controls.Gtk.Application.get_default",
        lambda: application,
    )

    buddy._begin_update_restart()

    bootstrap.assert_called_once_with(target, gui=True, wait_pid=os.getpid())
    application.quit.assert_called_once()


def test_shutdown_invalidates_update_callbacks_and_destroys_window() -> None:
    buddy = _Harness()
    generation = buddy._update_callback_generation

    buddy.shutdown_presence()

    assert buddy._update_shutting_down is True
    assert buddy._update_callback_generation == generation + 1
    assert buddy.destroyed == 1
    assert buddy.shutdown_calls == 1


def test_late_result_after_shutdown_is_ignored() -> None:
    buddy = _Harness()
    buddy._build_context_menu()
    buddy.shutdown_presence()
    buddy._made_label.reset_mock()

    result = UpdateCheckResult(
        status=UpdateStatus.UPDATE_AVAILABLE,
        target=_target(),
        announce=True,
    )
    assert buddy._apply_update_check_result(result, manual=False) is False
    buddy._made_label.set_text.assert_not_called()
    buddy._presence_bubble.show.assert_not_called()


def test_update_mixin_never_transitions_mochi_state() -> None:
    buddy = _Harness()
    buddy._apply_update_check_result(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            target=_target(),
            announce=True,
        ),
        manual=False,
    )

    assert buddy.transition_calls == 0


def test_update_controls_are_composed_into_both_production_buddies() -> None:
    for buddy_type in (PresenceBuddy, PresenceX11Buddy):
        assert UpdateControlsMixin in buddy_type.__mro__, (
            f"{buddy_type.__name__} must include UpdateControlsMixin"
        )
