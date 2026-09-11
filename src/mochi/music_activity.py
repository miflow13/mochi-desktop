"""Privacy-conscious music playback detection for Mochi.

Only the minimum MPRIS playback state and transient metadata needed to classify
music are inspected. Track titles, artists, URLs, and other metadata are never
retained, logged, or exposed by this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
import time
from urllib.parse import unquote, urlparse

from mochi.media_activity import (
    MprisMediaBackend,
    _deep_unpack,
    _is_browser_player,
    _metadata_indicates_watchable_video,
)


AUDIO_FILE_EXTENSIONS = frozenset(
    (
        ".mp3",
        ".flac",
        ".ogg",
        ".oga",
        ".opus",
        ".wav",
        ".wave",
        ".m4a",
        ".aac",
        ".alac",
        ".aiff",
        ".aif",
        ".wma",
    )
)

# Players that are music-first can safely use playback state as a fallback when
# their MPRIS implementation omits artist/album/file metadata.
_MUSIC_PLAYER_MARKERS = (
    "spotify",
    "rhythmbox",
    "amberol",
    "lollypop",
    "audacious",
    "clementine",
    "strawberry",
    "elisa",
    "tauon",
    "deadbeef",
    "quodlibet",
    "cmus",
    "mpd",
)

# Browser playback needs a source-specific signal before it is called music.
# Artist/album metadata alone is not enough because normal YouTube videos often
# expose channel/creator fields through MPRIS that look music-like.
_MUSIC_WEB_HOSTS = (
    "open.spotify.com",
    "soundcloud.com",
    "bandcamp.com",
    "music.apple.com",
    "tidal.com",
    "deezer.com",
    "pandora.com",
)


class MprisMusicBackend:
    """Reduce MPRIS state to a conservative music-playing boolean."""

    name = "MPRIS music playback"
    DBUS_NAME = MprisMediaBackend.DBUS_NAME
    DBUS_PATH = MprisMediaBackend.DBUS_PATH
    DBUS_INTERFACE = MprisMediaBackend.DBUS_INTERFACE
    PLAYER_PATH = MprisMediaBackend.PLAYER_PATH
    PLAYER_INTERFACE = MprisMediaBackend.PLAYER_INTERFACE
    PROPERTIES_INTERFACE = MprisMediaBackend.PROPERTIES_INTERFACE
    PLAYER_PREFIX = MprisMediaBackend.PLAYER_PREFIX

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

    def sample_music_playing(self) -> bool | None:
        """Return True/False, or None when MPRIS cannot be sampled safely."""
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
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

        names = _deep_unpack(reply)
        if isinstance(names, tuple) and len(names) == 1:
            names = names[0]
        if not isinstance(names, (list, tuple)):
            return False

        sampled_player = False
        player_error = False
        for bus_name in names:
            if not isinstance(bus_name, str) or not bus_name.startswith(
                self.PLAYER_PREFIX
            ):
                continue
            try:
                playing = self._player_is_music_playing(bus_name, Gio, GLib)
                sampled_player = True
            except Exception:
                player_error = True
                continue

            if playing:
                self.last_error = None
                return True

        if player_error and not sampled_player:
            self.last_error = "MPRIS players were present but unavailable"
            return None

        self.last_error = None
        return False

    def _player_is_music_playing(self, bus_name: str, Gio, GLib) -> bool:
        status = self._get_property(bus_name, "PlaybackStatus", Gio, GLib)
        if status != "Playing":
            return False

        metadata = self._get_property(bus_name, "Metadata", Gio, GLib)
        is_browser = _is_browser_player(bus_name)
        if _metadata_indicates_watchable_video(metadata):
            return False
        if _metadata_indicates_music(
            metadata,
            allow_artist_album=not is_browser,
        ):
            return True

        # A browser with ambiguous metadata could be playing any kind of media,
        # so never classify it as music from playback or artist/album state alone.
        if is_browser:
            return False
        return _is_music_first_player(bus_name)

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


class MusicActivityMonitor:
    """Turn MPRIS samples into stable music start/stop events."""

    POLL_INTERVAL_MS = 1_000
    STOP_GRACE_SECONDS = 3.0

    def __init__(
        self,
        *,
        on_music_started: Callable[[], None],
        on_music_stopped: Callable[[], None],
        logger: logging.Logger | None = None,
        backend: MprisMusicBackend | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._on_music_started = on_music_started
        self._on_music_stopped = on_music_stopped
        self._logger = logger or logging.getLogger(__name__)
        self._backend = backend or MprisMusicBackend()
        self._clock = clock
        self._source_id: int | None = None
        self._last_playing_at: float | None = None
        self.music_playing = False
        self.available = False

    @property
    def backend_name(self) -> str | None:
        return self._backend.name if self.available else None

    def start(self) -> bool:
        if self.available:
            return True
        if not self._backend.start():
            self._logger.debug(
                "Music awareness unavailable via %s: %s",
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
            self._logger.debug("Music awareness timer unavailable: %s", exc)
            return False

        self.available = True
        self._logger.info("Music awareness enabled via %s", self._backend.name)
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
        self.music_playing = False
        self._last_playing_at = None

    def _poll(self) -> bool:
        keep_running = True
        sample = self._backend.sample_music_playing()
        if sample is None:
            return keep_running

        now = self._clock()
        if sample:
            self._last_playing_at = now
            if not self.music_playing:
                self.music_playing = True
                self._logger.debug("Music playback active")
                self._on_music_started()
            return keep_running

        if not self.music_playing:
            return keep_running

        last_playing_at = self._last_playing_at
        if last_playing_at is None:
            last_playing_at = now
            self._last_playing_at = now
        if now - last_playing_at < self.STOP_GRACE_SECONDS:
            return keep_running

        self.music_playing = False
        self._last_playing_at = None
        self._logger.debug("Music playback inactive")
        self._on_music_stopped()
        return keep_running


def _string_values(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _string_values(item)


def _looks_like_audio_file(value: str) -> bool:
    try:
        parsed = urlparse(value)
        path = unquote(parsed.path if parsed.scheme else value)
    except Exception:
        path = value

    lowered = path.lower().split("?", 1)[0].split("#", 1)[0]
    return any(lowered.endswith(extension) for extension in AUDIO_FILE_EXTENSIONS)


def _url_is_youtube_music(value: str) -> bool:
    try:
        host = (urlparse(value).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    return host == "music.youtube.com" or host.endswith(".music.youtube.com")


def _url_is_known_music_service(value: str) -> bool:
    try:
        host = (urlparse(value).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    return any(host == domain or host.endswith(f".{domain}") for domain in _MUSIC_WEB_HOSTS)


def _metadata_indicates_music(
    metadata,
    *,
    allow_artist_album: bool = True,
) -> bool:
    """Conservatively classify transient MPRIS metadata as music."""
    metadata = _deep_unpack(metadata)
    if not isinstance(metadata, dict):
        return False
    if _metadata_indicates_watchable_video(metadata):
        return False

    for value in _string_values(metadata.get("xesam:url")):
        if (
            _url_is_youtube_music(value)
            or _url_is_known_music_service(value)
            or _looks_like_audio_file(value)
        ):
            return True

    for value in _string_values(metadata.get("xesam:title")):
        lowered = value.strip().lower()
        if "youtube music" in lowered or _looks_like_audio_file(value):
            return True

    # Native music players commonly expose artist/album without a useful URL.
    # Browser video can expose creator/channel fields in the same MPRIS keys,
    # so browser callers intentionally disable this fallback.
    if allow_artist_album:
        if any(
            value.strip()
            for value in _string_values(metadata.get("xesam:artist"))
        ):
            return True
        if any(
            value.strip()
            for value in _string_values(metadata.get("xesam:album"))
        ):
            return True

    return False


def _is_music_first_player(bus_name: str) -> bool:
    lowered = bus_name.lower().replace("_", "-")
    if lowered.startswith(MprisMusicBackend.PLAYER_PREFIX.lower()):
        lowered = lowered[len(MprisMusicBackend.PLAYER_PREFIX):]
    return any(marker in lowered for marker in _MUSIC_PLAYER_MARKERS)
