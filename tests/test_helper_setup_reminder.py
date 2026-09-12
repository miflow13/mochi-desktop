from __future__ import annotations

import logging

from mochi.presence.helper_setup_reminder import GnomeHelperSetupReminderMixin


class _FakeBubble:
    def __init__(self) -> None:
        self.shown: list[tuple[str, float]] = []

    def show(self, text: str, *, duration_seconds: float) -> bool:
        self.shown.append((text, duration_seconds))
        return True


class _FakeHelper:
    def __init__(self, *, available: bool = False) -> None:
        self.available = available


class _BaseHarness:
    def __init__(self) -> None:
        self._preview_mode = False
        self._presence_shutting_down = False
        self._presence_startup_source_id = 41
        self._presence_bubble = _FakeBubble()
        self._gnome_helper_lifecycle = _FakeHelper()
        self._logger = logging.getLogger("test-helper-setup-reminder")
        self.available_calls = 0
        self.unavailable_calls = 0
        self.shutdown_calls = 0
        self.startup_greeting_calls = 0
        self.attachment_ready = True

    def _on_gnome_helper_available(self) -> bool:
        self.available_calls += 1
        return self.attachment_ready

    def _on_gnome_helper_unavailable(self) -> None:
        self.unavailable_calls += 1

    def _show_startup_greeting(self) -> bool:
        self._presence_startup_source_id = None
        self.startup_greeting_calls += 1
        return False

    def _shutdown_presence(self) -> None:
        self.shutdown_calls += 1


class _Harness(GnomeHelperSetupReminderMixin, _BaseHarness):
    pass


def test_reminder_forwards_attachment_result_without_repeating_greeting(monkeypatch):
    scheduled, _removed = _fake_glib_timers(monkeypatch)
    buddy = _Harness()
    buddy.attachment_ready = False
    assert buddy._on_gnome_helper_available() is False
    before = len(scheduled)
    buddy.attachment_ready = True
    assert buddy._on_gnome_helper_available() is True
    assert len(scheduled) == before


def _fake_glib_timers(monkeypatch):
    scheduled: list[tuple[int, object]] = []
    removed: list[int] = []
    next_id = 100

    def timeout_add(delay_ms, callback):
        nonlocal next_id
        source_id = next_id
        next_id += 1
        scheduled.append((delay_ms, callback))
        return source_id

    def source_remove(source_id):
        removed.append(source_id)
        return True

    from mochi.presence import helper_setup_reminder as module

    monkeypatch.setattr(module.GLib, "timeout_add", timeout_add)
    monkeypatch.setattr(module.GLib, "source_remove", source_remove)
    return scheduled, removed


def test_missing_helper_suppresses_greeting_and_shows_setup_notice(monkeypatch):
    scheduled, removed = _fake_glib_timers(monkeypatch)

    buddy = _Harness()

    assert 41 in removed
    assert buddy._presence_startup_source_id is None
    assert buddy._gnome_helper_suppressed_startup_greeting is True
    assert len(scheduled) == 1
    assert scheduled[0][0] == buddy.HELPER_SETUP_REMINDER_DELAY_MS

    scheduled[0][1]()

    assert buddy._gnome_helper_reminder_shown is True
    assert buddy._presence_bubble.shown == [
        (buddy.HELPER_SETUP_MESSAGE, buddy.HELPER_SETUP_REMINDER_SECONDS)
    ]


def test_established_helper_disconnect_does_not_show_logout_instruction(monkeypatch):
    scheduled, _removed = _fake_glib_timers(monkeypatch)

    buddy = _Harness()
    scheduled[0][1]()
    assert buddy._gnome_helper_reminder_shown is True

    buddy._gnome_helper_lifecycle.available = True
    buddy._on_gnome_helper_available()
    assert buddy.available_calls == 1
    assert buddy._gnome_helper_seen_available is True

    before = len(scheduled)
    buddy._gnome_helper_lifecycle.available = False
    buddy._on_gnome_helper_unavailable()

    assert buddy.unavailable_calls == 1
    assert len(scheduled) == before


def test_helper_appearance_cancels_pending_setup_notice(monkeypatch):
    scheduled, removed = _fake_glib_timers(monkeypatch)

    buddy = _Harness()
    reminder_source_id = buddy._gnome_helper_reminder_source_id

    buddy._gnome_helper_lifecycle.available = True
    buddy._on_gnome_helper_available()

    assert reminder_source_id in removed
    assert buddy._gnome_helper_reminder_source_id is None
    assert buddy._gnome_helper_seen_available is True

    # The cancelled callback is harmless even if a test invokes it manually.
    scheduled[0][1]()
    assert buddy._presence_bubble.shown == []
