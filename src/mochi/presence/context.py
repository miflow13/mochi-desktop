"""Small, privacy-conscious ambient context snapshots for Mochi."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TypingIntensity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class AmbientContext:
    """Ephemeral facts PresenceEngine may consider.

    Every field is intentionally broad. Missing system signals are represented by
    ``None`` so Wayland/DBus limitations degrade to silence instead of failures.
    """

    user_active: bool = True
    typing_intensity: TypingIntensity = TypingIntensity.LOW
    typing_sustained_seconds: float = 0.0
    mouse_activity: float | None = None
    idle_seconds: float = 0.0
    session_duration: float = 0.0
    battery_percent: float | None = None
    charging: bool | None = None
    network_connected: bool | None = None
    media_playing: bool | None = None
    media_paused: bool | None = None
    current_app_category: str = "unknown"
    recent_build_result: str | None = None
    mochi_state: str = "idle"
    context_menu_open: bool = False
    interaction_active: bool = False
    transition_active: bool = False
    overlay_visible: bool = False
    application_shutting_down: bool = False
