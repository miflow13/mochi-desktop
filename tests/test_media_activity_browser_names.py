import unittest

from mochi.media_activity import MprisMediaBackend, _is_browser_player


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
        if destination == MprisMediaBackend.DBUS_NAME and method == "ListNames":
            return _Variant("(as)", (list(self.players),))
        if interface == MprisMediaBackend.PROPERTIES_INTERFACE and method == "Get":
            _player_interface, property_name = parameters.unpack()
            player = self.players[destination]
            if isinstance(player, Exception):
                raise player
            return _Variant("(v)", (_Variant("v", player[property_name]),))
        raise AssertionError("unexpected D-Bus call")


class BrowserPlayerRegressionTests(unittest.TestCase):
    def _backend(self, players):
        connection = _Connection(players)
        _Gio.connection = connection
        backend = MprisMediaBackend()
        backend._load_gio = lambda: (_Gio, _GLib)
        self.assertTrue(backend.start())
        return backend

    def test_flatpak_google_chrome_mpris_name_is_browser(self) -> None:
        self.assertTrue(_is_browser_player("org.mpris.MediaPlayer2.com.google.Chrome"))

    def test_terminal_chrome_mpris_name_is_browser(self) -> None:
        self.assertTrue(_is_browser_player("org.mpris.MediaPlayer2.chrome"))

    def test_focused_youtube_allows_flatpak_chrome_without_url_metadata(self) -> None:
        backend = self._backend(
            {
                "org.mpris.MediaPlayer2.com.google.Chrome": {
                    "PlaybackStatus": "Playing",
                    "Metadata": {"xesam:title": "A video"},
                }
            }
        )
        backend._youtube_focused = True
        self.assertTrue(backend.sample_youtube_playing())

    def test_stale_player_does_not_block_working_browser_player(self) -> None:
        backend = self._backend(
            {
                "org.mpris.MediaPlayer2.stale": RuntimeError("gone"),
                "org.mpris.MediaPlayer2.com.google.Chrome": {
                    "PlaybackStatus": "Playing",
                    "Metadata": {"xesam:title": "A video"},
                },
            }
        )
        backend._youtube_focused = True
        self.assertTrue(backend.sample_youtube_playing())

    def test_all_unavailable_players_return_unknown_not_false(self) -> None:
        backend = self._backend(
            {"org.mpris.MediaPlayer2.stale": RuntimeError("gone")}
        )
        self.assertIsNone(backend.sample_youtube_playing())


if __name__ == "__main__":
    unittest.main()
