from __future__ import annotations

import json
from pathlib import Path

from mochi.presence.clicks import ClickBurstDetector
from mochi.presence.click_dialogue import FEDORA_CLICK_PITCH_RATIOS


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "mochi" / "manifest.json"


def test_fedora_secret_requires_six_rapid_clicks() -> None:
    detector = ClickBurstDetector(required_clicks=6, window_seconds=2.4)

    for timestamp in (1.0, 1.2, 1.4, 1.6, 1.8):
        assert detector.record(now=timestamp) is False

    assert detector.record(now=2.0) is True


def test_fedora_click_positions_climb_to_six_then_reset() -> None:
    detector = ClickBurstDetector(required_clicks=6, window_seconds=2.4)

    positions = []
    for timestamp in (1.0, 1.2, 1.4, 1.6, 1.8, 2.0):
        detector.record(now=timestamp)
        positions.append(detector.last_position)

    assert positions == [1, 2, 3, 4, 5, 6]
    assert detector.record(now=5.0) is False
    assert detector.last_position == 1


def test_fedora_secret_resets_when_clicks_are_not_rapid() -> None:
    detector = ClickBurstDetector(required_clicks=6, window_seconds=2.4)

    for timestamp in (1.0, 1.5, 2.0, 2.5, 3.0):
        assert detector.record(now=timestamp) is False

    assert detector.record(now=4.0) is False


def test_fedora_click_pitch_ramp_ends_highest() -> None:
    assert len(FEDORA_CLICK_PITCH_RATIOS) == 6
    assert FEDORA_CLICK_PITCH_RATIOS[0] == 1.0
    assert all(
        current < following
        for current, following in zip(
            FEDORA_CLICK_PITCH_RATIOS, FEDORA_CLICK_PITCH_RATIOS[1:]
        )
    )


def test_fedora_manifest_preserves_handoff_timing_and_sequence() -> None:
    animations = json.loads(MANIFEST.read_text())["animations"]

    intro = animations["fedora_intro"]
    loop = animations["fedora_loop"]
    outro = animations["fedora_outro"]

    assert intro["frame_count"] == 16
    assert intro["loop"] is False
    assert abs(intro["fps"] - (1000 / 120)) < 0.01

    assert loop["frame_count"] == 12
    assert loop["loop"] is True
    assert loop["source_cell_size"] == [64, 64]
    assert abs(loop["fps"] - (1000 / 120)) < 0.01

    assert outro["frame_count"] == 13
    assert outro["loop"] is False
    assert abs(outro["fps"] - (1000 / 120)) < 0.01

    for name in ("fedora_intro", "fedora_loop", "fedora_outro"):
        for relative_path in animations[name]["frames"]:
            assert (ROOT / "assets" / "mochi" / relative_path).exists()


class _State:
    def __init__(self) -> None:
        self.current = None


class _FedoraHarnessBase:
    def _finish_reaction(self, finished_animation) -> None:
        self.base_finished = finished_animation

    def _maybe_resume_ambient_activity(self) -> bool:
        self.base_resume_called = True
        return False

    def _schedule_computer_idle_emote(self) -> None:
        self.computer_idle_scheduled = True

    def shutdown_presence(self) -> None:
        pass

    def _begin_sleep(self) -> None:
        self.base_sleep_called = True


from mochi.presence.fedora_mode import FedoraModeMixin
from mochi.state import MochiState


class _FedoraHarness(FedoraModeMixin, _FedoraHarnessBase):
    def __init__(self) -> None:
        self._fedora_mode_active = True
        self._fedora_mode_exiting = False
        self._preview_mode = False
        self._context_menu_open = False
        self._pending_animation = "idle"
        self._current_animation = self.FEDORA_INTRO_ANIMATION
        self._active_animation = object()
        self.state = _State()
        self.state.current = MochiState.FEDORA
        self.played: list[tuple[str, object]] = []
        self.transitions: list[MochiState] = []
        self.computer_idle_scheduled = False
        self.base_resume_called = False

    def _play_animation(self, name: str, after=None) -> None:
        self.played.append((name, after))
        self._current_animation = name
        self._active_animation = object()

    def _transition_to(self, state: MochiState) -> bool:
        self.transitions.append(state)
        self.state.current = state
        return True


def test_fedora_lifecycle_advances_intro_loop_outro_idle() -> None:
    buddy = _FedoraHarness()

    intro = buddy._active_animation
    buddy._finish_reaction(intro)
    assert buddy.played[-1] == ("fedora_loop", None)
    assert buddy.state.current is MochiState.FEDORA

    assert buddy._stop_fedora_mode() is True
    assert buddy._fedora_mode_active is False
    assert buddy._fedora_mode_exiting is True
    assert buddy.played[-1] == ("fedora_outro", None)

    outro = buddy._active_animation
    buddy._finish_reaction(outro)
    assert buddy._fedora_mode_exiting is False
    assert buddy.transitions[-1] is MochiState.IDLE
    assert buddy.played[-1] == ("idle", None)
    assert buddy.base_resume_called is True


def test_fedora_engaged_phrase_matches_easter_egg_copy() -> None:
    assert FedoraModeMixin.FEDORA_ENGAGED_TEXT == "fedora mode engaged"
