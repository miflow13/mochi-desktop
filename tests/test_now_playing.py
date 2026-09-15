import unittest
from unittest.mock import Mock

from mochi.presence.now_playing import (
    MprisNowPlayingController,
    NowPlayingMixin,
    NowPlayingSnapshot,
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
        self.commands = []

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
        if destination == MprisNowPlayingController.DBUS_NAME and method == "ListNames":
            return _Variant("(as)", (list(self.players),))
        if (
            interface == MprisNowPlayingController.PROPERTIES_INTERFACE
            and method == "Get"
        ):
            _player_interface, property_name = parameters.unpack()
            return _Variant(
                "(v)",
                (_Variant("v", self.players[destination][property_name]),),
            )
        if interface == MprisNowPlayingController.PLAYER_INTERFACE:
            self.commands.append((destination, method))
            return _Variant("()", ())
        raise AssertionError(f"unexpected D-Bus call: {destination} {interface} {method}")


class MprisNowPlayingControllerTests(unittest.TestCase):
    def _controller(self, players):
        connection = _Connection(players)
        _Gio.connection = connection
        controller = MprisNowPlayingController()
        controller._load_gio = lambda: (_Gio, _GLib)
        self.assertTrue(controller.start())
        return controller, connection

    def test_playing_spotify_exposes_transient_title_and_artist(self):
        controller, _connection = self._controller({
            "org.mpris.MediaPlayer2.spotify": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "Green Tea",
                    "xesam:artist": ["Tiny Sprout"],
                },
            }
        })

        snapshot = controller.snapshot()

        self.assertEqual(
            snapshot,
            NowPlayingSnapshot(
                title="Green Tea",
                artist="Tiny Sprout",
                playing=True,
            ),
        )

    def test_paused_music_stays_available_for_resume(self):
        controller, _connection = self._controller({
            "org.mpris.MediaPlayer2.spotify": {
                "PlaybackStatus": "Paused",
                "Metadata": {
                    "xesam:title": "Green Tea",
                    "xesam:artist": ["Tiny Sprout"],
                },
            }
        })

        snapshot = controller.snapshot()

        self.assertIsNotNone(snapshot)
        self.assertFalse(snapshot.playing)

    def test_regular_youtube_video_is_not_exposed_as_music(self):
        controller, _connection = self._controller({
            "org.mpris.MediaPlayer2.chromium.instance123": {
                "PlaybackStatus": "Playing",
                "Metadata": {
                    "xesam:title": "A normal video",
                    "xesam:artist": ["Video channel"],
                    "xesam:url": "https://www.youtube.com/watch?v=abc",
                },
            }
        })

        self.assertIsNone(controller.snapshot())

    def test_controls_target_the_selected_player(self):
        bus_name = "org.mpris.MediaPlayer2.spotify"
        controller, connection = self._controller({
            bus_name: {
                "PlaybackStatus": "Playing",
                "Metadata": {"xesam:title": "Green Tea"},
            }
        })
        self.assertIsNotNone(controller.snapshot())

        self.assertTrue(controller.previous())
        self.assertTrue(controller.play_pause())
        self.assertTrue(controller.next())

        self.assertEqual(
            connection.commands,
            [
                (bus_name, "Previous"),
                (bus_name, "PlayPause"),
                (bus_name, "Next"),
            ],
        )

    def test_track_metadata_is_not_retained_on_controller(self):
        title = "private track title"
        controller, _connection = self._controller({
            "org.mpris.MediaPlayer2.spotify": {
                "PlaybackStatus": "Playing",
                "Metadata": {"xesam:title": title},
            }
        })

        self.assertEqual(controller.snapshot().title, title)
        self.assertNotIn(title, repr(vars(controller)))


class _FakeUI:
    def __init__(self):
        self.expanded = False
        self.snapshots = []

    def set_expanded(self, expanded):
        self.expanded = expanded

    def update(self, snapshot):
        self.snapshots.append(snapshot)


class _FakeController:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.previous_calls = 0
        self.play_pause_calls = 0
        self.next_calls = 0

    def snapshot(self):
        return self._snapshot

    def previous(self):
        self.previous_calls += 1
        return True

    def play_pause(self):
        self.play_pause_calls += 1
        return True

    def next(self):
        self.next_calls += 1
        return True


class NowPlayingMixinTests(unittest.TestCase):
    def _mixin(self, snapshot):
        mixin = object.__new__(NowPlayingMixin)
        mixin._now_playing_ui = _FakeUI()
        mixin._now_playing_controller = _FakeController(snapshot)
        mixin._now_playing_last_sample_at = 0.0
        mixin.show_nameplate_feedback = Mock()
        return mixin

    def test_nameplate_click_expands_when_music_exists(self):
        snapshot = NowPlayingSnapshot("Green Tea", "Tiny Sprout", True)
        mixin = self._mixin(snapshot)

        mixin._toggle_now_playing_panel()

        self.assertTrue(mixin._now_playing_ui.expanded)
        self.assertEqual(mixin._now_playing_ui.snapshots, [snapshot])

    def test_nameplate_click_gives_quiet_feedback_when_nothing_is_playing(self):
        mixin = self._mixin(None)

        mixin._toggle_now_playing_panel()

        self.assertFalse(mixin._now_playing_ui.expanded)
        mixin.show_nameplate_feedback.assert_called_once_with(
            "nothing playing",
            duration_seconds=1.6,
        )

    def test_clicking_open_panel_collapses_without_resampling(self):
        mixin = self._mixin(NowPlayingSnapshot("Green Tea", None, True))
        mixin._now_playing_ui.expanded = True
        mixin._now_playing_controller.snapshot = Mock()

        mixin._toggle_now_playing_panel()

        self.assertFalse(mixin._now_playing_ui.expanded)
        mixin._now_playing_controller.snapshot.assert_not_called()

    def test_transport_controls_request_a_refresh_on_next_tick(self):
        mixin = self._mixin(NowPlayingSnapshot("Green Tea", None, True))
        mixin._now_playing_last_sample_at = 123.0

        mixin._now_playing_previous()
        self.assertEqual(mixin._now_playing_controller.previous_calls, 1)
        self.assertEqual(mixin._now_playing_last_sample_at, 0.0)

        mixin._now_playing_play_pause()
        self.assertEqual(mixin._now_playing_controller.play_pause_calls, 1)
        self.assertEqual(mixin._now_playing_last_sample_at, 0.0)

        mixin._now_playing_next()
        self.assertEqual(mixin._now_playing_controller.next_calls, 1)
        self.assertEqual(mixin._now_playing_last_sample_at, 0.0)


if __name__ == "__main__":
    unittest.main()
