"""Privacy-conscious media activity detection for Mochi.

Mochi uses MPRIS for playback state plus coarse GNOME Shell focus signals.
Metadata is inspected transiently and is never retained, logged, or exposed.
When Chromium omits URL/site metadata, focused-browser state can safely act as
the final fallback for an already-playing browser MPRIS session.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
import time
from urllib.parse import unquote, urlparse

VIDEO_FILE_EXTENSIONS = frozenset(
    (
        ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v",
        ".ogv", ".flv", ".wmv", ".mpeg", ".mpg", ".ts",
        ".m2ts", ".3gp",
    )
)

_BROWSER_PLAYER_MARKERS = (
    "chromium",
    "chrome",
    "google.chrome",
    "google-chrome",
    "com.google.chrome",
    "firefox",
    "mozilla.firefox",
    "brave",
    "vivaldi",
    "microsoft-edge",
    "microsoft.edge",
)


class MprisMediaBackend:
    """Read a minimal boolean watchable-media signal from MPRIS."""

    name = "MPRIS media playback"
    DBUS_NAME = "org.freedesktop.DBus"
    DBUS_PATH = "/org/freedesktop/DBus"
    DBUS_INTERFACE = "org.freedesktop.DBus"
    PLAYER_PATH = "/org/mpris/MediaPlayer2"
    PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
    PLAYER_PREFIX = "org.mpris.MediaPlayer2."
    ACTIVITY_BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    ACTIVITY_OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    ACTIVITY_INTERFACE_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    YOUTUBE_FOCUSED_STARTED_SIGNAL = "YouTubeFocusedStarted"
    YOUTUBE_FOCUSED_STOPPED_SIGNAL = "YouTubeFocusedStopped"
    APP_CATEGORY_SIGNAL = "AppCategoryChanged"

    def __init__(self) -> None:
        self._connection = None
        self._youtube_focused = False
        self._focused_browser = False
        self._watching_via_youtube_focus = False
        self._watching_via_browser_focus = False
        self._on_youtube_focus_changed: Callable[[bool], None] | None = None
        self._on_browser_focus_changed: Callable[[bool], None] | None = None
        self._youtube_focus_started_subscription_id: int | None = None
        self._youtube_focus_stopped_subscription_id: int | None = None
        self._app_category_subscription_id: int | None = None
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._connection is not None

    @property
    def watching_via_youtube_focus(self) -> bool:
        return self._watching_via_youtube_focus

    @property
    def watching_via_browser_focus(self) -> bool:
        return self._watching_via_browser_focus

    def set_youtube_focus_changed_callback(
        self, callback: Callable[[bool], None] | None
    ) -> None:
        self._on_youtube_focus_changed = callback

    def set_browser_focus_changed_callback(
        self, callback: Callable[[bool], None] | None
    ) -> None:
        self._on_browser_focus_changed = callback

    def set_focused_browser(self, active: bool) -> None:
        """Receive only whether the coarse focused-app category is a browser."""
        self._focused_browser = bool(active)

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
            self._subscribe_focus_signals()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._connection = None
            return False
        return True

    def _subscribe_focus_signals(self) -> None:
        connection = self._connection
        if connection is None or not hasattr(connection, "signal_subscribe"):
            return

        try:
            Gio, _GLib = self._load_gio()
            flags = Gio.DBusSignalFlags.NONE
            started_id = connection.signal_subscribe(
                self.ACTIVITY_BUS_NAME,
                self.ACTIVITY_INTERFACE_NAME,
                self.YOUTUBE_FOCUSED_STARTED_SIGNAL,
                self.ACTIVITY_OBJECT_PATH,
                None,
                flags,
                self._on_youtube_focused_started,
            )
            stopped_id = connection.signal_subscribe(
                self.ACTIVITY_BUS_NAME,
                self.ACTIVITY_INTERFACE_NAME,
                self.YOUTUBE_FOCUSED_STOPPED_SIGNAL,
                self.ACTIVITY_OBJECT_PATH,
                None,
                flags,
                self._on_youtube_focused_stopped,
            )
            category_id = connection.signal_subscribe(
                self.ACTIVITY_BUS_NAME,
                self.ACTIVITY_INTERFACE_NAME,
                self.APP_CATEGORY_SIGNAL,
                self.ACTIVITY_OBJECT_PATH,
                None,
                flags,
                self._on_app_category_changed,
            )
            self._youtube_focus_started_subscription_id = (
                int(started_id) if started_id else None
            )
            self._youtube_focus_stopped_subscription_id = (
                int(stopped_id) if stopped_id else None
            )
            self._app_category_subscription_id = (
                int(category_id) if category_id else None
            )
        except Exception:
            # Metadata-only detection can still operate without the Shell helper.
            self._youtube_focus_started_subscription_id = None
            self._youtube_focus_stopped_subscription_id = None
            self._app_category_subscription_id = None

    def _on_youtube_focused_started(self, *_ignored) -> None:
        changed = not self._youtube_focused
        self._youtube_focused = True
        if changed and self._on_youtube_focus_changed is not None:
            self._on_youtube_focus_changed(True)

    def _on_youtube_focused_stopped(self, *_ignored) -> None:
        changed = self._youtube_focused
        self._youtube_focused = False
        if changed and self._on_youtube_focus_changed is not None:
            self._on_youtube_focus_changed(False)

    def _on_app_category_changed(
        self,
        _connection,
        _sender_name,
        _object_path,
        _interface_name,
        _signal_name,
        parameters,
    ) -> None:
        try:
            unpacked = _deep_unpack(parameters)
            category = unpacked[0] if isinstance(unpacked, tuple) else unpacked
        except Exception:
            return
        active = category == "browser"
        changed = active != self._focused_browser
        self._focused_browser = active
        if changed and self._on_browser_focus_changed is not None:
            self._on_browser_focus_changed(active)

    def stop(self) -> None:
        if self._connection is not None and hasattr(
            self._connection, "signal_unsubscribe"
        ):
            for subscription_id in (
                self._youtube_focus_started_subscription_id,
                self._youtube_focus_stopped_subscription_id,
                self._app_category_subscription_id,
            ):
                if subscription_id is None:
                    continue
                try:
                    self._connection.signal_unsubscribe(subscription_id)
                except Exception:
                    pass

        self._youtube_focus_started_subscription_id = None
        self._youtube_focus_stopped_subscription_id = None
        self._app_category_subscription_id = None
        self._youtube_focused = False
        self._focused_browser = False
        self._watching_via_youtube_focus = False
        self._watching_via_browser_focus = False
        self._connection = None

    def sample_youtube_playing(self) -> bool | None:
        """Return True/False, or None when MPRIS could not be sampled safely."""
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

        self._watching_via_youtube_focus = False
        self._watching_via_browser_focus = False
        sampled_player = False
        player_error = False

        for bus_name in names:
            if not isinstance(bus_name, str) or not bus_name.startswith(
                self.PLAYER_PREFIX
            ):
                continue
            try:
                playing = self._player_is_youtube_playing(bus_name, Gio, GLib)
                sampled_player = True
            except Exception:
                # A stale/partial MPRIS service must not prevent another player
                # (for example Chrome) from being evaluated.
                player_error = True
                continue

            if playing:
                self.last_error = None
                return True

        # If every discovered MPRIS player failed to answer, preserve the
        # previous monitor state rather than manufacturing a false stop.
        if player_error and not sampled_player:
            self.last_error = "MPRIS players were present but unavailable"
            return None

        self.last_error = None
        return False

    def _player_is_youtube_playing(self, bus_name: str, Gio, GLib) -> bool:
        status = self._get_property(bus_name, "PlaybackStatus", Gio, GLib)
        if status != "Playing":
            return False

        metadata = self._get_property(bus_name, "Metadata", Gio, GLib)
        is_browser = _is_browser_player(bus_name)

        # Local/direct video files are playback-driven, not focus-driven.
        if _metadata_indicates_video_file(metadata):
            return True

        youtube_metadata = _metadata_indicates_youtube(metadata)

        # Browser YouTube is focus-sensitive so background playback does not
        # make Mochi behave as though the user is actively watching it.
        if youtube_metadata and is_browser:
            if self._youtube_focused:
                self._watching_via_youtube_focus = True
                return True
            if self._focused_browser:
                self._watching_via_browser_focus = True
                return True
            return False

        # Non-browser players that explicitly identify YouTube can use metadata.
        if youtube_metadata:
            return True

        # Preferred sparse-metadata fallback: the Shell already reduced the
        # focused page to a YouTube boolean.
        if self._youtube_focused and is_browser:
            self._watching_via_youtube_focus = True
            return True

        # Chromium on Fedora commonly exposes exactly what playerctl reports:
        # a browser MPRIS player in Playing state, a media title, and no URL or
        # site branding. If that browser is also the coarse focused-app category,
        # treat it as focused browser media. No title, URL, or page content is
        # retained or transmitted to make this decision.
        if self._focused_browser and is_browser:
            self._watching_via_browser_focus = True
            return True

        return False

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
    """Turn privacy-reduced MPRIS/focus samples into stable media events."""

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
        if hasattr(self._backend, "set_youtube_focus_changed_callback"):
            self._backend.set_youtube_focus_changed_callback(
                self._on_youtube_focus_changed
            )
        if hasattr(self._backend, "set_browser_focus_changed_callback"):
            self._backend.set_browser_focus_changed_callback(
                self._on_browser_focus_changed
            )
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

    def _on_browser_focus_changed(self, active: bool) -> None:
        if not self.available:
            return

        self._logger.debug(
            "Focused browser media fallback: %s",
            "active" if active else "inactive",
        )

        if active:
            self._poll()
            return

        if (
            self.youtube_playing
            and bool(getattr(self._backend, "watching_via_browser_focus", False))
        ):
            self._stop_watching_now("browser focus lost")

    def _on_youtube_focus_changed(self, active: bool) -> None:
        if not self.available:
            return

        self._logger.debug(
            "YouTube focus signal: %s",
            "active" if active else "inactive",
        )

        if active:
            self._poll()
            return

        if (
            self.youtube_playing
            and bool(getattr(self._backend, "watching_via_youtube_focus", False))
        ):
            self._stop_watching_now("YouTube focus lost")

    def _stop_watching_now(self, reason: str) -> None:
        if not self.youtube_playing:
            return
        self.youtube_playing = False
        self._last_playing_at = None
        self._logger.debug("Watchable media playback inactive: %s", reason)
        self._on_youtube_stopped()

    def _poll(self) -> bool:
        keep_running = True

        sample = self._backend.sample_youtube_playing()
        if sample is None:
            return keep_running

        now = self._clock()
        if sample:
            self._last_playing_at = now
            if not self.youtube_playing:
                self.youtube_playing = True
                self._logger.debug("Watchable media playback active")
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

        self._stop_watching_now("playback grace expired")
        return keep_running


def _is_browser_player(bus_name: str) -> bool:
    lowered = bus_name.lower().replace("_", "-")
    if lowered.startswith(MprisMediaBackend.PLAYER_PREFIX.lower()):
        lowered = lowered[len(MprisMediaBackend.PLAYER_PREFIX):]
    return any(marker in lowered for marker in _BROWSER_PLAYER_MARKERS)


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


def _url_is_youtube_video(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False

    host = (parsed.hostname or "").lower().rstrip(".")
    path = parsed.path.lower()

    if host == "music.youtube.com":
        return False
    if host == "youtu.be" or host.endswith(".youtu.be"):
        return bool(path.strip("/"))
    if host == "youtube.com" or host.endswith(".youtube.com"):
        return (
            path == "/watch"
            or path.startswith("/shorts/")
            or path.startswith("/live/")
            or path.startswith("/embed/")
        )
    return False


def _looks_like_video_file(value: str) -> bool:
    try:
        parsed = urlparse(value)
        path = unquote(parsed.path if parsed.scheme else value)
    except Exception:
        path = value

    lowered = path.lower().split("?", 1)[0].split("#", 1)[0]
    return any(lowered.endswith(extension) for extension in VIDEO_FILE_EXTENSIONS)


def _metadata_indicates_youtube(metadata) -> bool:
    metadata = _deep_unpack(metadata)
    if not isinstance(metadata, dict):
        return False

    titles = tuple(_string_values(metadata.get("xesam:title")))
    is_youtube_music = any(
        "youtube music" in title.strip().lower()
        for title in titles
    )

    for value in _string_values(metadata.get("xesam:url")):
        if _url_is_youtube_video(value):
            return True

    if not is_youtube_music:
        for value in _string_values(metadata.get("mpris:artUrl")):
            lowered = value.lower()
            if "ytimg.com/" in lowered or "img.youtube.com/" in lowered:
                return True

    for title in titles:
        lowered = title.strip().lower()
        if not is_youtube_music and (
            lowered == "youtube" or lowered.endswith(" - youtube")
        ):
            return True

    return False


def _metadata_indicates_video_file(metadata) -> bool:
    metadata = _deep_unpack(metadata)
    if not isinstance(metadata, dict):
        return False

    for value in _string_values(metadata.get("xesam:url")):
        if _looks_like_video_file(value):
            return True

    for title in _string_values(metadata.get("xesam:title")):
        if _looks_like_video_file(title):
            return True

    return False


def _metadata_indicates_watchable_video(metadata) -> bool:
    return _metadata_indicates_youtube(metadata) or _metadata_indicates_video_file(metadata)
