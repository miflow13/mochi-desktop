"""Canonical lowercase phrase bank for Mochi's ambient presence."""

from __future__ import annotations

from collections import deque
import random
from collections.abc import Iterable


PHRASES: dict[str, tuple[str, ...]] = {
    "startup": (
        "oh, hi :)",
        "hello from down here",
        "i'm here 🌱",
        "sprout operational 🌱",
        "mochi online",
        "ready to loaf",
        "all systems leafy",
        "tiny desktop. big world.",
    ),
    "ambient": (
        "just hanging out 🌱", "i'm here", "no rush", "hmm...", "cozy.",
        "i'm just vibing", "carry on :)", "still here", "tiny desktop. big world.",
        "nice day to exist", "we persist 🌱", "doing my little thing", "this is a good spot",
        "i'm keeping watch", "nothing to report", "peaceful...", "very desktop",
        "optimal loafing conditions", "currently: blob", "status: cozy", "mood: green",
        "today's forecast: mochi", "sprout operational 🌱", "all systems leafy",
        "just a little guy", "occupying several pixels", "being round is hard work",
        "deeply considering nothing", "hmm. yes. computer.", "important blob business",
        "quietly existing", "hello from down here",
    ),
    "encouragement": (
        "tiny progress counts", "one thing at a time", "no rush",
        "you can come back to it", "perhaps the smallest step",
    ),
    "focus": (
        "one thing at a time", "perhaps the smallest step", "no rush",
    ),
    "developer": (
        "tiny commit?", "git status knows things", "did we save?", "ctrl+s is my favorite spell",
        "one bug at a time", "the code has opinions", "computer says hmm",
        "have you tried staring at the logs?", "works on my desktop 🌱", "ship the tiny version",
        "prototype first", "make it exist", "green checks! 🌱", "code cooking",
    ),
    "creative": (
        "make the weird version", "follow the interesting idea", "try it and see",
        "keep the happy accident", "maybe exaggerate it", "give it personality",
        "tiny details matter", "handmade feels nice", "imperfect can feel alive",
        "trust the sketch", "that's got character", "okay wait... that's cute", "keep that",
        "personality > perfection", "maybe one more frame", "good silhouette",
        "timing makes everything", "squishier?", "more bounce?", "animation acquired",
        "art happening 🌱",
    ),
    "body_care": (
        "water nearby?", "tiny sip maybe?", "stretch if you want", "shoulders feeling okay?",
        "little stretch?", "comfortable?", "maybe look out a window for a sec",
    ),
    "rest": (
        "no rush", "you can come back to it", "comfortable?",
    ),
    "frustration": (
        "hmm. annoying.", "okay, that's weird", "well... that wasn't it", "interesting failure",
        "computer please", "rude.", "maybe the logs know", "weird bugs take time",
        "stable is good", "boring and working is underrated", "okay bug. explain yourself.",
        "suspicious.", "noted. extremely suspicious.", "debugging is still building",
        "this is useful information",
    ),
    "mischief": (
        "important blob business", "deeply considering nothing", "currently: blob",
        "being round is hard work", "hmm. yes. computer.",
    ),
    "companionship": (
        "i'm here", "still here", "carry on :)", "hello from down here", "we persist 🌱",
    ),
    "typing": (
        "typing typing typing...", "lots of words happening", "keyboard going brrrr",
        "thoughts detected", "big typing energy", "something's cooking", "words are happening",
        "look at you go", "very clicky today", "keyboard busy :)",
        "brain to keyboard pipeline operational",
    ),
    "media": (
        "oh we're watching something?", "good song :)", "entertainment acquired",
        "i'll be quiet", "movie time?",
    ),
    "network": (
        "internet disappeared...", "where'd the internet go", "hmm. offline.",
        "we're back 🌱", "internet acquired", "there it is",
    ),
    "battery": (
        "we're getting sleepy 🔋", "battery looking a little tired", "tiny power situation",
        "snack acquired ⚡", "charging :)", "power snack",
    ),
    "return_from_idle": (
        "welcome back", "there you are", "hey again :)", "oh, hi",
    ),
}

EVENT_PHRASES: dict[str, tuple[str, ...]] = {
    "battery_low": (
        "we're getting sleepy 🔋", "battery looking a little tired", "tiny power situation",
    ),
    "charging_started": ("snack acquired ⚡", "charging :)", "power snack"),
    "network_lost": ("internet disappeared...", "where'd the internet go", "hmm. offline."),
    "network_restored": ("we're back 🌱", "internet acquired", "there it is"),
    "build_failed": PHRASES["frustration"],
    "build_succeeded": ("green checks! 🌱", "code cooking", "make it exist"),
}


class PhraseBank:
    """Choose phrases while avoiding a short in-memory repetition window."""

    def __init__(
        self,
        *,
        rng: random.Random | None = None,
        recent_limit: int = 12,
    ) -> None:
        self._rng = rng or random.Random()
        self._recent: deque[str] = deque(maxlen=max(1, recent_limit))

    def choose(
        self,
        category: str,
        *,
        exclude_recent: bool = True,
        remember: bool = False,
    ) -> str:
        try:
            choices = PHRASES[category]
        except KeyError as exc:
            raise KeyError(f"unknown Mochi phrase category: {category}") from exc
        return self.choose_from(
            choices,
            exclude_recent=exclude_recent,
            remember=remember,
        )

    def choose_from(
        self,
        choices: Iterable[str],
        *,
        exclude_recent: bool = True,
        remember: bool = False,
    ) -> str:
        pool = tuple(choices)
        if not pool:
            raise ValueError("phrase choices must not be empty")
        if exclude_recent:
            fresh = tuple(item for item in pool if item not in self._recent)
            if fresh:
                pool = fresh
        selected = self._rng.choice(pool)
        if remember:
            self.remember(selected)
        return selected

    def remember(self, text: str) -> None:
        self._recent.append(text)

    @property
    def recent(self) -> tuple[str, ...]:
        return tuple(self._recent)
