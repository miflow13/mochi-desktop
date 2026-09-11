"""Exercise real Buddy state/animation callbacks without a desktop surface."""
import logging
from types import SimpleNamespace

from mochi.buddy import Buddy
from mochi.behavior import ClickReactionBuffer
from mochi.state import MochiState, StateMachine


class Lifecycle:
    def __init__(self):
        self.state = StateMachine()
        self._logger = logging.getLogger(__name__)
        self._preview_mode = False
        self._user_idle = False
        self._context_menu_open = False
        self._media_monitor = None
        self._file_activity_monitor = None
        self._current_animation = "idle"
        self._typing_monitor = SimpleNamespace(active=False)
        self._computer_idle_source_id = None
        self._click_reactions = ClickReactionBuffer()
        self._idle_resume_position = None
        self.player = SimpleNamespace(animation=None, play=self.play)
        self.played = []
        self._play_animation("idle")

    def __getattr__(self, name):
        return getattr(Buddy, name).__get__(self)

    def play(self, animation, **kwargs):
        self.player.animation = animation
        self.played.append(animation.name)

    def queue_draw(self):
        pass

    def _reschedule_computer_idle_emote(self):
        pass

    def _schedule_idle_action(self):
        pass

    def complete(self):
        self._finish_reaction(self._active_animation)


def test_typing_wakes_once_and_resumes_typing_after_wake():
    buddy = Lifecycle()
    buddy._on_user_idle()
    buddy.complete()
    buddy._typing_monitor.active = True
    buddy._on_typing_activity()
    buddy._on_typing_activity()
    assert buddy.state.current is MochiState.WAKING
    assert buddy.played.count("wake") == 1
    buddy.complete()
    assert buddy.state.current is MochiState.TYPING


def test_direct_activity_clears_deferred_idle_and_repeats_cycles():
    buddy = Lifecycle()
    for _ in range(2):
        buddy._on_user_idle()
        buddy._on_user_idle()
        assert buddy.state.current is MochiState.SLEEPING
        buddy.complete()
        buddy._mark_interaction()
        assert not buddy._user_idle
        assert buddy.state.current is MochiState.WAKING
        buddy.complete()
        assert buddy.state.current is MochiState.IDLE
    assert buddy.played.count("sleep") == 2
    assert buddy.played.count("wake") == 2


def test_idle_defers_context_and_retries_after_context_ends():
    buddy = Lifecycle()
    buddy.state.current = MochiState.TYPING
    buddy._on_user_idle()
    assert buddy.state.current is MochiState.TYPING
    buddy.state.current = MochiState.IDLE
    buddy._play_animation("idle")
    buddy._choose_idle_action()
    assert buddy.state.current is MochiState.SLEEPING


def test_activity_cancels_menu_deferred_sleep():
    buddy = Lifecycle()
    buddy._context_menu_open = True
    buddy._on_user_idle()
    buddy._mark_interaction()
    buddy._context_menu_open = False
    assert not buddy._user_idle
    assert buddy.state.current is MochiState.IDLE


def test_wake_during_sleep_intro_ignores_stale_completion():
    buddy = Lifecycle()
    buddy._on_user_idle()
    sleep = buddy._active_animation
    buddy._on_user_active()
    buddy._finish_reaction(sleep)
    assert buddy.state.current is MochiState.WAKING
    buddy.complete()
    assert buddy.state.current is MochiState.IDLE
    assert "sleeping" not in buddy.played


def test_stopped_typing_during_wake_returns_to_idle():
    buddy = Lifecycle()
    buddy._on_user_idle()
    buddy._typing_monitor.active = True
    buddy._on_typing_activity()
    buddy._typing_monitor.active = False
    buddy._on_typing_stopped()
    buddy.complete()
    assert buddy.state.current is MochiState.IDLE
