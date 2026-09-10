"""Decision engine for Mochi's quiet ambient presence."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import random
import time

from .context import AmbientContext, TypingIntensity
from .cooldowns import CooldownTracker
from .phrases import EVENT_PHRASES, PhraseBank
from .signals import TypingIntensityTracker


@dataclass(slots=True)
class PresenceTuning:
    # Still intentionally quiet, but a little more present than the first pass.
    ambient_min_seconds: float = 7 * 60.0
    ambient_max_seconds: float = 16 * 60.0
    ambient_silence_probability: float = 0.65
    global_cooldown_seconds: float = 5 * 60.0
    same_category_min_seconds: float = 20 * 60.0
    same_category_max_seconds: float = 40 * 60.0
    body_care_cooldown_seconds: float = 60 * 60.0
    system_event_cooldown_seconds: float = 30 * 60.0
    max_phrases_per_hour: int = 4
    # Sustained typing should be noticeable in a normal work session without
    # making Mochi comment on every short message or search query.
    typing_medium_sustain_seconds: float = 35.0
    typing_high_sustain_seconds: float = 25.0
    typing_comment_probability: float = 0.70
    return_probability: float = 0.45
    media_probability: float = 0.30
    system_event_probability: float = 0.55
    build_event_probability: float = 0.65
    speech_enabled: bool = True
    ambient_reactions_enabled: bool = True
    quiet_mode: bool = False
    category_weights: dict[str, float] = field(default_factory=lambda: {
        "ambient": 55.0,
        "encouragement": 12.0,
        "developer": 6.0,
        "creative": 6.0,
        "focus": 10.0,
        "companionship": 5.0,
        "body_care": 3.0,
        "rest": 3.0,
    })


@dataclass(frozen=True, slots=True)
class PresenceAction:
    type: str
    category: str
    text: str
    priority: int
    event: str | None = None
    display_seconds: float = 3.5


@dataclass(frozen=True, slots=True)
class _QueuedEvent:
    name: str
    created_at: float


_EVENT_PRIORITY = {
    "force_ambient": 20,
    "force_contextual": 30,
    "user_returned": 30,
    "media_started": 30,
    "battery_low": 40,
    "charging_started": 40,
    "network_lost": 40,
    "network_restored": 40,
    "build_failed": 30,
    "build_succeeded": 30,
}
_EVENT_CATEGORY = {
    "user_returned": "return_from_idle",
    "media_started": "media",
    "battery_low": "battery",
    "charging_started": "battery",
    "network_lost": "network",
    "network_restored": "network",
    "build_failed": "frustration",
    "build_succeeded": "developer",
}


def speech_display_seconds(text: str) -> float:
    length = len(text.strip())
    if length <= 28:
        return 3.5
    if length <= 52:
        return 5.0
    return 6.5


class PresenceEngine:
    """Choose at most one subtle action; silence is the normal result."""

    def __init__(
        self,
        *,
        tuning: PresenceTuning | None = None,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        self.tuning = tuning or PresenceTuning()
        self._rng = rng or random.Random()
        self._clock = clock
        self._logger = logger or logging.getLogger(__name__)
        self.phrases = PhraseBank(rng=self._rng)
        self.cooldowns = CooldownTracker(
            global_gap_seconds=self.tuning.global_cooldown_seconds,
            max_per_hour=self.tuning.max_phrases_per_hour,
            clock=clock,
        )
        self.typing = TypingIntensityTracker(clock=clock)
        now = self._clock()
        self._next_ambient_at = now + self._ambient_delay()
        self._events: deque[_QueuedEvent] = deque(maxlen=16)
        self._user_idle_since: float | None = None
        self._bubble_dismissed_until = 0.0
        self._forced_context_category: str | None = None
        # The presence layer receives activity only after TypingActivityMonitor
        # has recognized a real typing burst. Track that session independently
        # of LOW/MEDIUM/HIGH pace changes so normal fluctuations do not reset
        # the sustained-typing clock.
        self._typing_session_started_at: float | None = None
        self._typing_comment_attempted = False

    def set_quiet_mode(self, enabled: bool) -> None:
        self.tuning.quiet_mode = bool(enabled)

    def set_speech_enabled(self, enabled: bool) -> None:
        self.tuning.speech_enabled = bool(enabled)

    def set_ambient_reactions_enabled(self, enabled: bool) -> None:
        self.tuning.ambient_reactions_enabled = bool(enabled)

    def emit(self, name: str, *, now: float | None = None) -> bool:
        if name not in _EVENT_PRIORITY:
            self._logger.debug("[presence] ignored unknown event=%s", name)
            return False
        timestamp = self._clock() if now is None else now
        if not any(event.name == name for event in self._events):
            self._events.append(_QueuedEvent(name, timestamp))
            self._logger.debug("[presence] event=%s queued", name)
        return True

    def force_ambient(self) -> None:
        self.emit("force_ambient")

    def force_contextual(self, category: str) -> None:
        self._forced_context_category = category
        self.emit("force_contextual")

    def record_typing_activity(self, *, now: float | None = None) -> TypingIntensity:
        timestamp = self._clock() if now is None else now
        if self._typing_session_started_at is None:
            self._typing_session_started_at = timestamp
            self._typing_comment_attempted = False
            self._logger.debug("[presence] sustained typing session started")
        intensity = self.typing.record(timestamp)
        self._logger.debug("[presence] typing intensity -> %s", intensity.value)
        return intensity

    def record_typing_stopped(self, *, now: float | None = None) -> None:
        timestamp = self._clock() if now is None else now
        self.typing.stopped(timestamp)
        self._typing_session_started_at = None
        self._typing_comment_attempted = False
        self._logger.debug("[presence] sustained typing session stopped")

    def note_user_idle(self, *, now: float | None = None) -> None:
        self._user_idle_since = self._clock() if now is None else now

    def note_user_active(self, *, now: float | None = None) -> None:
        timestamp = self._clock() if now is None else now
        idle_since = self._user_idle_since
        self._user_idle_since = None
        if idle_since is not None and timestamp - idle_since >= 10 * 60.0:
            self.emit("user_returned", now=timestamp)

    def note_bubble_dismissed(self, *, now: float | None = None) -> None:
        timestamp = self._clock() if now is None else now
        self._bubble_dismissed_until = timestamp + 120.0

    def typing_snapshot(self, *, now: float | None = None) -> tuple[TypingIntensity, float]:
        timestamp = self._clock() if now is None else now
        intensity, _level_sustained = self.typing.snapshot(timestamp)
        sustained = (
            0.0
            if self._typing_session_started_at is None
            else max(0.0, timestamp - self._typing_session_started_at)
        )
        return intensity, sustained

    def evaluate(
        self, context: AmbientContext, *, now: float | None = None
    ) -> PresenceAction | None:
        timestamp = self._clock() if now is None else now
        self._prune_events(timestamp)
        reason = self._suppression_reason(context, timestamp)
        if reason is not None:
            self._logger.debug("[presence] suppressed: %s", reason)
            return None

        if self._peek_forced_event() is None:
            allowed, reason = self.cooldowns.can_speak(timestamp)
            if not allowed:
                self._logger.debug("[presence] suppressed: %s", reason)
                return None

        action = self._evaluate_events(timestamp)
        if action is not None:
            return action
        action = self._evaluate_typing(context, timestamp)
        if action is not None:
            return action

        if timestamp < self._next_ambient_at:
            return None
        self._next_ambient_at = timestamp + self._ambient_delay()
        if self._rng.random() < self.tuning.ambient_silence_probability:
            self._logger.debug("[presence] candidate=ambient suppressed: silence roll")
            return None

        category = self._select_unsolicited_category(context)
        if category is None:
            return None
        ready, reason = self.cooldowns.category_ready(category, timestamp)
        if not ready:
            self._logger.debug("[presence] candidate=%s suppressed: %s", category, reason)
            return None
        text = self.phrases.choose(category, exclude_recent=True)
        self._logger.debug("[presence] candidate=%s selected=%r", category, text)
        return PresenceAction("speech", category, text, 10, display_seconds=speech_display_seconds(text))

    def record_delivered(
        self, action: PresenceAction, *, now: float | None = None
    ) -> None:
        timestamp = self._clock() if now is None else now
        self.phrases.remember(action.text)
        self.cooldowns.record(
            action.category,
            now=timestamp,
            category_cooldown_seconds=self._category_cooldown(action.category),
        )
        self._logger.debug(
            "[presence] delivered category=%s event=%s text=%r",
            action.category,
            action.event,
            action.text,
        )

    def _evaluate_events(self, now: float) -> PresenceAction | None:
        if not self._events:
            return None
        ordered = sorted(
            self._events,
            key=lambda event: (_EVENT_PRIORITY[event.name], -event.created_at),
            reverse=True,
        )
        for event in ordered:
            self._events.remove(event)
            if event.name == "force_ambient":
                text = self.phrases.choose("ambient", exclude_recent=True)
                self._events.clear()
                return PresenceAction("speech", "ambient", text, 20, event.name, speech_display_seconds(text))
            if event.name == "force_contextual":
                category = self._forced_context_category or "ambient"
                self._forced_context_category = None
                try:
                    text = self.phrases.choose(category, exclude_recent=True)
                except KeyError:
                    category = "ambient"
                    text = self.phrases.choose(category, exclude_recent=True)
                self._events.clear()
                return PresenceAction("speech", category, text, 30, event.name, speech_display_seconds(text))

            category = _EVENT_CATEGORY[event.name]
            ready, reason = self.cooldowns.category_ready(category, now)
            if not ready:
                self._logger.debug("[presence] event=%s suppressed: %s", event.name, reason)
                continue
            if self._rng.random() >= self._event_probability(event.name):
                self._logger.debug("[presence] event=%s suppressed: silence roll", event.name)
                continue
            choices = EVENT_PHRASES.get(event.name)
            text = (
                self.phrases.choose_from(choices, exclude_recent=True)
                if choices
                else self.phrases.choose(category, exclude_recent=True)
            )
            self._logger.debug("[presence] event=%s selected=%r", event.name, text)
            self._events.clear()
            return PresenceAction(
                "speech", category, text, _EVENT_PRIORITY[event.name], event.name,
                speech_display_seconds(text),
            )
        return None

    def _evaluate_typing(self, context: AmbientContext, now: float) -> PresenceAction | None:
        intensity = context.typing_intensity
        sustained = context.typing_sustained_seconds
        threshold = None
        if intensity is TypingIntensity.HIGH:
            threshold = self.tuning.typing_high_sustain_seconds
        elif intensity is TypingIntensity.MEDIUM:
            threshold = self.tuning.typing_medium_sustain_seconds
        if threshold is None or sustained < threshold:
            return None
        if self._typing_comment_attempted:
            return None
        ready, reason = self.cooldowns.category_ready("typing", now)
        if not ready:
            self._logger.debug("[presence] candidate=typing suppressed: %s", reason)
            return None
        self._typing_comment_attempted = True
        if self._rng.random() >= self.tuning.typing_comment_probability:
            self._logger.debug("[presence] candidate=typing suppressed: silence roll")
            return None
        text = self.phrases.choose("typing", exclude_recent=True)
        self._logger.debug(
            "[presence] candidate=typing selected=%r intensity=%s sustained=%.1fs",
            text,
            intensity.value,
            sustained,
        )
        return PresenceAction("speech", "typing", text, 30, "typing_sustained", speech_display_seconds(text))

    def _select_unsolicited_category(self, context: AmbientContext) -> str | None:
        weights = dict(self.tuning.category_weights)
        if context.current_app_category not in ("editor", "terminal"):
            weights.pop("developer", None)
        if context.current_app_category != "pixel_art":
            weights.pop("creative", None)
        if context.typing_intensity is TypingIntensity.LOW:
            weights.pop("focus", None)
        if context.session_duration < 60 * 60.0:
            weights.pop("body_care", None)
            weights.pop("rest", None)
        positive = [(category, weight) for category, weight in weights.items() if weight > 0]
        if not positive:
            return None
        categories, values = zip(*positive)
        return self._rng.choices(categories, weights=values, k=1)[0]

    def _suppression_reason(self, context: AmbientContext, now: float) -> str | None:
        if not self.tuning.speech_enabled:
            return "speech disabled"
        if not self.tuning.ambient_reactions_enabled:
            return "ambient reactions disabled"
        if self.tuning.quiet_mode:
            return "quiet mode"
        if not context.user_active:
            return "user inactive"
        if context.application_shutting_down:
            return "application shutting down"
        if context.context_menu_open:
            return "context menu open"
        if context.interaction_active:
            return "interaction underway"
        if context.transition_active:
            return "animation transition underway"
        if context.overlay_visible:
            return "speech overlay already visible"
        if now < self._bubble_dismissed_until:
            return "bubble recently dismissed"
        state = context.mochi_state.lower()
        if state in {"sleeping", "pickup", "dragged", "dropping", "waking"}:
            return f"state={state}"
        if context.media_playing and not any(
            event.name == "media_started" for event in self._events
        ):
            return "media playback quiet bias"
        return None

    def _category_cooldown(self, category: str) -> float:
        if category == "body_care":
            return self.tuning.body_care_cooldown_seconds
        if category in ("battery", "network"):
            return self.tuning.system_event_cooldown_seconds
        return self._rng.uniform(
            self.tuning.same_category_min_seconds,
            self.tuning.same_category_max_seconds,
        )

    def _event_probability(self, name: str) -> float:
        if name == "user_returned":
            return self.tuning.return_probability
        if name == "media_started":
            return self.tuning.media_probability
        if name in ("battery_low", "charging_started", "network_lost", "network_restored"):
            return self.tuning.system_event_probability
        if name in ("build_failed", "build_succeeded"):
            return self.tuning.build_event_probability
        return 1.0

    def _prune_events(self, now: float) -> None:
        self._events = deque(
            (event for event in self._events if now - event.created_at <= 120.0),
            maxlen=16,
        )

    def _ambient_delay(self) -> float:
        low = min(self.tuning.ambient_min_seconds, self.tuning.ambient_max_seconds)
        high = max(self.tuning.ambient_min_seconds, self.tuning.ambient_max_seconds)
        return self._rng.uniform(low, high)

    def _peek_forced_event(self) -> _QueuedEvent | None:
        return next((event for event in self._events if event.name.startswith("force_")), None)
