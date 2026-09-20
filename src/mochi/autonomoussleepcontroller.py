"""Low-priority autonomous nap behavior for Mochi."""

from __future__ import annotations

import random

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

from mochi.state import MochiState


class AutonomousSleepController:
    """Schedule occasional low-priority naps without owning sleep behavior."""

    def __init__(self, buddy) -> None:
        self._buddy = buddy
        self._nap_source_id: int | None = None
        self._wake_source_id: int | None = None
        self._owns_sleep = False