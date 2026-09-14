from __future__ import annotations

from types import SimpleNamespace

from mochi.presence import click_dialogue as dialogue
from mochi.presence.click_dialogue import ClickDialogueMixin


class FakeLogger:
    def __init__(self) -> None:
        self.debug_calls: list[tuple] = []
        self.info_calls: list[tuple] = []

    def debug(self, *args) -> None:
        self.debug_calls.append(args)

    def info(self, *args) -> None:
        self.info_calls.append(args)


class FakePhrases:
    def __init__(self, text: str = "welcome back") -> None:
        self.text = text
        self.choose_calls: list[tuple[str, bool]] = []
        self.remembered: list[str] = []

    def choose(self, category: str, *, exclude_recent: bool) -> str:
        self.choose_calls.append((category, exclude_recent))
        return self.text

    def remember(self, text: str) -> None:
        self.remembered.append(str(text))


class FakeConfig:
    def __init__(self, *, seen: bool) -> None:
        self.seen = seen
        self.saved: list[bool] = []

    def load_first_startup_dialogue_seen(self) -> bool:
        return self.seen

    def save_first_startup_dialogue_seen(self, seen: bool) -> None:
        self.seen = seen
        self.saved.append(seen)


class FakeBubble:
    def __init__(self, *, visible: bool = False) -> None:
        self.visible = visible
        self.calls: list[tuple[str, float, bool]] = []

    def show(self, text: str, *, duration_seconds: float) -> bool:
        if self.visible:
            return False
        self.visible = True
        self.calls.append(
            (
                str(text),
                duration_seconds,
                bool(getattr(text, "typing_preview", False)),
            )
        )
        return True


class StartupHarness:
    _show_startup_greeting = ClickDialogueMixin._show_startup_greeting
    _schedule_startup_greeting_retry = (
        ClickDialogueMixin._schedule_startup_greeting_retry
    )

    def __init__(
        self,
        *,
        seen: bool,
        bubble_visible: bool = False,
        user_idle: bool = False,
        ambient_reactions_enabled: bool = True,
    ) -> None:
        self._presence_startup_source_id = 99
        self._presence_shutting_down = False
        self._preview_mode = False
        self._user_idle = user_idle
        self._startup_greeting_attempts = 0
        self._config = FakeConfig(seen=seen)
        self._presence_bubble = FakeBubble(visible=bubble_visible)
        self._ambient_presence_engine = SimpleNamespace(
            tuning=SimpleNamespace(
                speech_enabled=True,
                ambient_reactions_enabled=ambient_reactions_enabled,
                quiet_mode=False,
            ),
            phrases=FakePhrases(),
        )
        self._logger = FakeLogger()


def test_later_launch_uses_welcome_back_phrase_bank() -> None:
    buddy = StartupHarness(seen=True)

    result = buddy._show_startup_greeting()

    assert result == dialogue.GLib.SOURCE_REMOVE
    assert buddy._ambient_presence_engine.phrases.choose_calls == [
        ("return_from_idle", True)
    ]
    assert buddy._presence_bubble.calls == [("welcome back", 3.5, True)]
    assert buddy._ambient_presence_engine.phrases.remembered == ["welcome back"]
    assert buddy._config.saved == []


def test_session_greeting_ignores_stale_idle_and_ambient_reaction_gate() -> None:
    buddy = StartupHarness(
        seen=True,
        user_idle=True,
        ambient_reactions_enabled=False,
    )

    buddy._show_startup_greeting()

    assert buddy._presence_bubble.calls == [("welcome back", 3.5, True)]
    assert buddy._startup_greeting_attempts == 0


def test_busy_startup_bubble_retries_then_delivers_session_greeting(monkeypatch) -> None:
    buddy = StartupHarness(seen=True, bubble_visible=True)
    scheduled: list[tuple[int, object]] = []

    def fake_timeout_add(delay_ms: int, callback):
        scheduled.append((delay_ms, callback))
        return 123

    monkeypatch.setattr(dialogue.GLib, "timeout_add", fake_timeout_add)

    result = buddy._show_startup_greeting()

    assert result == dialogue.GLib.SOURCE_REMOVE
    assert buddy._presence_startup_source_id == 123
    assert buddy._startup_greeting_attempts == 1
    assert buddy._ambient_presence_engine.phrases.choose_calls == []
    assert scheduled[0][0] == dialogue.STARTUP_GREETING_RETRY_MS

    buddy._presence_bubble.visible = False
    retry_callback = scheduled[0][1]
    retry_callback()

    assert buddy._presence_bubble.calls == [("welcome back", 3.5, True)]
    assert buddy._ambient_presence_engine.phrases.remembered == ["welcome back"]
    assert buddy._startup_greeting_attempts == 0


def test_first_startup_flag_is_saved_only_after_intro_is_visible(monkeypatch) -> None:
    buddy = StartupHarness(seen=False, bubble_visible=True)
    scheduled: list[object] = []

    def fake_timeout_add(_delay_ms: int, callback):
        scheduled.append(callback)
        return 456

    monkeypatch.setattr(dialogue.GLib, "timeout_add", fake_timeout_add)

    buddy._show_startup_greeting()
    assert buddy._config.saved == []

    buddy._presence_bubble.visible = False
    scheduled[0]()

    assert buddy._presence_bubble.calls[0][0] == dialogue.FIRST_STARTUP_GREETING
    assert buddy._presence_bubble.calls[0][1] == dialogue.FIRST_STARTUP_GREETING_SECONDS
    assert buddy._config.saved == [True]
