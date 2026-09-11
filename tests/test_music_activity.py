import logging
import unittest
from unittest.mock import Mock

from mochi.music_activity import (
    MusicActivityMonitor,
    MprisMusicBackend,
    _metadata_indicates_music,
)


class _Variant:
    def __init__(self, _signature, value):
        self.value = value

    def unpack(self):
        return self.value


class _GLib:
    Variant = _Variant


class _Gio:
    class BusType:
        SESSION = object()

    class DBusCallFlags:
        NONE = object()

    connection = None

    @classmethod
    def bus_get_sync(cls, _bus_type, _cancellable):
        return cls.connection


class _Connection:
    def __init__(self, players):
        self.players = players

    def call_sync(
        self,
        destination,
        _path,
        interface,
        method,
        parameters,
        _reply_type,
        _flags,
        _timeout,
        _cancellable,
    ):
        if destination == MprisMusicBackend.DBUS_NAME and method == "ListNames":
            return _Variant("(as)", (list(self.players),))
        if interface == MprisMusicBackend.PROPERTIES_INTERFACE and method == "Get":
            _player_interface, property_name = parameters.unpack()
            return _Variant("(v)", (_Variant("v", self.players[destination][property_name]),))
        raise AssertionError(f"unexpected D-Bus call: {destination} {interface} {method}")


class MprisMusicBackendTests(unittest.TestCase):
    def _backend(self, players):
        connection = _Connection(players)
        _Gio.connection = connection
        backend = MprisMusicBackend()
        backend._load_gio = lambda: (_Gio, _GLib)
        self.assertTrue(backend.start())
        return backend

    def test_spotify_playback_is_music_even_with_sparse_metadata(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.spotify": {
                "PlaybackStatus": "Playing",
                "Metadata": {"xesam:title": "A track"},
            }
        })
        self.assertTrue(backend.sample_music_playing())

    def test_youtube_music_metadata_is_music(self):
        self.assertTrue(_metadata_indicates_music({
            "xesam:url": "https://music.youtube.com/watch?v=abc",
            "xesam:title": "A track - YouTube Music",
        }))

    def test_regular_youtube_video_is_not_music(self):
        self.assertFalse(_metadata_indicates_music({
            "xesam:url": "https://www.youtube.com/watch?v=abc",
            "xesam:title": "A video - YouTube",
        }))

    def test_browser_creator_metadata_alone_is_not_music(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "A normal YouTube video",
                    "xesam:artist": ["Video channel"],
                    "xesam:url": "",
                },
            }
        })
        self.assertFalse(backend.sample_music_playing())

    def test_spotify_web_url_is_music(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "A track",
                    "xesam:artist": ["An artist"],
                    "xesam:url": "https://open.spotify.com/track/abc",
                },
            }
        })
        self.assertTrue(backend.sample_music_playing())

    def test_brainfm_web_url_is_music(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "Deep Work",
                    "xesam:url": "https://www.brain.fm/player",
                },
            }
        })
        self.assertTrue(backend.sample_music_playing())

    def test_brainfm_title_is_music_when_browser_omits_url(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "Deep Work - Brain.fm",
                    "xesam:url": "",
                },
            }
        })
        self.assertTrue(backend.sample_music_playing())

    def test_pandora_title_is_music_when_browser_omits_url(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "Song title - Artist name - Pandora",
                    "xesam:url": "",
                },
            }
        })
        self.assertTrue(backend.sample_music_playing())

    def test_local_audio_file_is_music(self):
        self.assertTrue(_metadata_indicates_music({
            "xesam:url": "file:///home/user/Music/song.flac"
        }))

    def test_local_video_file_is_not_music(self):
        self.assertFalse(_metadata_indicates_music({
            "xesam:url": "file:///home/user/Videos/movie.mkv"
        }))

    def test_artist_metadata_is_music(self):
        self.assertTrue(_metadata_indicates_music({
            "xesam:title": "A track",
            "xesam:artist": ["An artist"],
        }))

    def test_generic_browser_playback_is_not_guessed_as_music(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {"xesam:title": "Ambiguous media"},
            }
        })
        self.assertFalse(backend.sample_music_playing())

    def test_paused_music_is_not_playing(self):
        backend = self._backend({
            "org.mpris.MediaPlayer2.spotify": {
                "PlaybackStatus": "Paused",
                "Metadata": {"xesam:artist": ["Artist"]},
            }
        })
        self.assertFalse(backend.sample_music_playing())

    def test_metadata_is_not_retained(self):
        secret_title = "private track title"
        backend = self._backend({
            "org.mpris.MediaPlayer2.spotify": {
                "PlaybackStatus": "Playing",
                "Metadata": {"xesam:title": secret_title},
            }
        })
        self.assertTrue(backend.sample_music_playing())
        self.assertNotIn(secret_title, repr(vars(backend)))


class _FakeBackend:
    name = "fake music"

    def __init__(self, samples):
        self.samples = list(samples)
        self.last_error = None

    def start(self):
        return True

    def stop(self):
        pass

    def sample_music_playing(self):
        if not self.samples:
            return False
        return self.samples.pop(0)


class MusicActivityMonitorTests(unittest.TestCase):
    def test_start_fires_once(self):
        now = [10.0]
        started = Mock()
        monitor = MusicActivityMonitor(
            on_music_started=started,
            on_music_stopped=Mock(),
            backend=_FakeBackend([True, True]),
            clock=lambda: now[0],
        )
        monitor._poll()
        now[0] += 1.0
        monitor._poll()
        self.assertTrue(monitor.music_playing)
        started.assert_called_once_with()

    def test_brief_pause_uses_grace_period(self):
        now = [10.0]
        stopped = Mock()
        monitor = MusicActivityMonitor(
            on_music_started=Mock(),
            on_music_stopped=stopped,
            backend=_FakeBackend([True, False]),
            clock=lambda: now[0],
        )
        monitor._poll()
        now[0] += 2.0
        monitor._poll()
        self.assertTrue(monitor.music_playing)
        stopped.assert_not_called()

    def test_sustained_pause_stops(self):
        now = [10.0]
        stopped = Mock()
        monitor = MusicActivityMonitor(
            on_music_started=Mock(),
            on_music_stopped=stopped,
            backend=_FakeBackend([True, False]),
            clock=lambda: now[0],
            logger=logging.getLogger("music-test"),
        )
        monitor._poll()
        now[0] += 3.1
        monitor._poll()
        self.assertFalse(monitor.music_playing)
        stopped.assert_called_once_with()

    def test_sample_error_does_not_false_stop(self):
        now = [10.0]
        stopped = Mock()
        monitor = MusicActivityMonitor(
            on_music_started=Mock(),
            on_music_stopped=stopped,
            backend=_FakeBackend([True, None]),
            clock=lambda: now[0],
        )
        monitor._poll()
        now[0] += 10.0
        monitor._poll()
        self.assertTrue(monitor.music_playing)
        stopped.assert_not_called()


if __name__ == "__main__":
    unittest.main()
