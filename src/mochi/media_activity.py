"""Privacy-conscious media activity detection for Mochi.

Mochi uses the standard MPRIS D-Bus interface exposed by Linux media players
and browsers. Runtime metadata is inspected only long enough to answer one
question: "is a YouTube session currently playing?" Metadata values are never
logged, stored, emitted, or exposed to the rest of Mochi.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
import time


class MprisMediaBackend:
    """Read a minimal boolean YouTube-playing signal from MPRIS."""

    name = "MPRIS media playback"
    DBUS_NAME = "org.freedesktop.DBus"
    DBUS_PATH = "/org/freedesktop/DBus"
    DBUS_INTERFACE = "org.freedesktop.DBus"
    PLAYER_PATH = "/org/mpris/MediaPlayer2"
    PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
    PLAYER_PREFIX = "org.mpris.MediaPlayer2."

    def __init__(self) -> None:
        self._connection = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._connection is not None

    @staticmethod
    def _load_gio():
        import gi

        from gi.repository import Gio, GLib

        return Gio, GLib

    def start(self) -> bool:
        if self.active:
            return True

        self.last_error = None
        try:
            Gio, _GLib = self._load_gio()
            self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if self._connection is None:
                self.last_error = "session D-Bus connection is unavailable"
                return False
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._connection = None
            return False
        return True

    def stop(self) -> None:
        self._connection = None

    def sample_youtube_playing(self) -> bool | None:
        """Return True/False, or None if MPRIS could not be sampled safely."""
        if self._connection is None:
            return None

        try:
            Gio, GLib = self._load_gio()
            reply = self._connection.call_sync(
                self.DBUS_NAME,
                self.DBUS_PATH,
                self.DBUS_INTERFACE,
                "ListNames",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                1_000,
                None,
            )
            names = _deep_unpack(reply)
            if isinstance(names, tuple) and len(names) == 1:
                names = names[0]
            if not isinstance(names, (list, tuple)):
                return False

            for bus_name in names:
                if not isinstance(bus_name, str) or not bus_name.startswith(
                    self.PLAYER_PREFIX
                ):
                    continue
                if self._player_is_youtube_playing(bus_name, Gio, GLib):
                    return True
            return False
        except Exception as exc:
            # D-Bus errors contain no media metadata. Do not include property
            # values in this message or retain them on the backend.
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def _player_is_youtube_playing(self, bus_name: str, Gio, GLib) -> bool:
        status = self._get_property(bus_name, "PlaybackStatus", Gio, GLib)
        if status != "Playing":
            return False

        metadata = self._get_property(bus_name, "Metadata", Gio, GLib)
        if _metadata_indicates_youtube(metadata):
            return True

        # Chromium's Linux MPRIS implementation exposes playback/title/artist
        # but not the page URL, so it cannot identify the originating website.
        # For Chrome/Chromium we deliberately fall back to "browser media is
        # playing" so the watch-along works there. This can also react to
        # non-YouTube media playing in a Chromium-based browser.
        return any(marker in bus_name.lower() for marker in (".chromium.", ".chrome."))

    def _get_property(self, bus_name: str, property_name: str, Gio, GLib):
        reply = self._connection.call_sync(
            bus_name,
            self.PLAYER_PATH,
            self.PROPERTIES_INTERFACE,
            "Get",
            GLib.Variant("(ss)", (self.PLAYER_INTERFACE, property_name)),
            None,
            Gio.DBusCallFlags.NONE,
            750,
            None,
        )
        value = _deep_unpack(reply)
        if isinstance(value, tuple) and len(value) == 1:
            value = value[0]
        return value


class MediaActivityMonitor:
    """Turn MPRIS samples into stable YouTube start/stop events."""

    POLL_INTERVAL_MS = 1_000
    STOP_GRACE_SECONDS = 5.0

    def __init__(
        self,
        *,
        on_youtube_started: Callable[[], None],
        on_youtube_stopped: Callable[[], None],
        logger: logging.Logger | None = None,
        backend: MprisMediaBackend | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._on_youtube_started = on_youtube_started
        self._on_youtube_stopped = on_youtube_stopped
        self._logger = logger or logging.getLogger(__name__)
        self._backend = backend or MprisMediaBackend()
        self._clock = clock
        self._source_id: int | None = None
        self._last_playing_at: float | None = None
        self.youtube_playing = False
        self.available = False

    @property
    def backend_name(self) -> str | None:
        return self._backend.name if self.available else None

    def start(self) -> bool:
        if self.available:
            return True
        if not self._backend.start():
            self._logger.debug(
                "Media awareness unavailable via %s: %s",
                self._backend.name,
                self._backend.last_error or "unknown error",
            )
            return False

        try:
            from gi.repository import GLib

            self._source_id = GLib.timeout_add(
                self.POLL_INTERVAL_MS,
                self._poll,
            )
        except Exception as exc:
            self._backend.stop()
            self._logger.debug("Media awareness timer unavailable: %s", exc)
            return False

        self.available = True
        self._logger.info("Media awareness enabled via %s", self._backend.name)
        self._poll()
        return True

    def stop(self) -> None:
        if self._source_id is not None:
            try:
                from gi.repository import GLib

                GLib.source_remove(self._source_id)
            except Exception:
                pass
        self._source_id = None
        self._backend.stop()
        self.available = False
        self.youtube_playing = False
        self._last_playing_at = None

    def _poll(self) -> bool:
        # GLib timeout callbacks continue while they return a truthy value.
        # Keeping this method GI-free also makes the debounce logic easy to test.
        keep_running = True

        sample = self._backend.sample_youtube_playing()
        if sample is None:
            return keep_running

        now = self._clock()
        if sample:
            self._last_playing_at = now
            if not self.youtube_playing:
                self.youtube_playing = True
                self._logger.debug("YouTube playback active")
                self._on_youtube_started()
            return keep_running

        if not self.youtube_playing:
            return keep_running

        last_playing_at = self._last_playing_at
        if last_playing_at is None:
            last_playing_at = now
            self._last_playing_at = now
        if now - last_playing_at < self.STOP_GRACE_SECONDS:
            return keep_running

        self.youtube_playing = False
        self._last_playing_at = None
        self._logger.debug("YouTube playback inactive")
        self._on_youtube_stopped()
        return keep_running


def _deep_unpack(value):
    """Recursively unpack GLib.Variant-like values without stringifying them."""
    while hasattr(value, "unpack"):
        unpacked = value.unpack()
        if unpacked is value:
            break
        value = unpacked
    if isinstance(value, dict):
        return {key: _deep_unpack(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_deep_unpack(item) for item in value)
    if isinstance(value, list):
        return [_deep_unpack(item) for item in value]
    return value


def _string_values(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _string_values(item)


def _metadata_indicates_youtube(metadata) -> bool:
    """Reduce transient MPRIS metadata to a boolean and discard the rest."""
    metadata = _deep_unpack(metadata)
    if not isinstance(metadata, dict):
        return False

    for field in ("xesam:url", "mpris:artUrl"):
        for value in _string_values(metadata.get(field)):
            lowered = value.lower()
            if (
                "youtube.com/" in lowered
                or "youtu.be/" in lowered
                or "ytimg.com/" in lowered
            ):
                return True

    # Some browser MPRIS implementations omit xesam:url but suffix the media
    # title with the site name. Inspect the title only in this stack frame;
    # never log it, return it, or store it.
    for title in _string_values(metadata.get("xesam:title")):
        lowered = title.strip().lower()
        if lowered == "youtube" or lowered.endswith(" - youtube"):
            return True

    return False
