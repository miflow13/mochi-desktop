import unittest
from unittest.mock import Mock

from mochi.media_activity import MediaActivityMonitor, MprisMediaBackend


class _Parameters:
    def __init__(self, category: str) -> None:
        self._category = category

    def unpack(self):
        return (self._category,)


class MediaFocusFallbackTests(unittest.TestCase):
    def test_sparse_chromium_mpris_is_media_when_browser_is_focused(self) -> None:
        backend = MprisMediaBackend()
        backend.set_focused_browser(True)
        properties = {
            "PlaybackStatus": "Playing",
            "Metadata": {
                "xesam:title": "I Play Fallout New Vegas, You Relax/Sleep",
                "xesam:url": "",
            },
        }
        backend._get_property = (
            lambda _bus_name, property_name, _gio, _glib: properties[property_name]
        )

        self.assertTrue(
            backend._player_is_youtube_playing(
                "org.mpris.MediaPlayer2.chromium.instance387598",
                object(),
                object(),
            )
        )
        self.assertTrue(backend.watching_via_browser_focus)

    def test_sparse_chromium_mpris_is_ignored_when_browser_is_not_focused(self) -> None:
        backend = MprisMediaBackend()
        properties = {
            "PlaybackStatus": "Playing",
            "Metadata": {"xesam:title": "A song", "xesam:url": ""},
        }
        backend._get_property = (
            lambda _bus_name, property_name, _gio, _glib: properties[property_name]
        )

        self.assertFalse(
            backend._player_is_youtube_playing(
                "org.mpris.MediaPlayer2.chromium.instance387598",
                object(),
                object(),
            )
        )

    def test_coarse_app_category_updates_browser_focus_only(self) -> None:
        backend = MprisMediaBackend()
        changed = Mock()
        backend.set_browser_focus_changed_callback(changed)

        backend._on_app_category_changed(
            None, None, None, None, None, _Parameters("browser")
        )
        self.assertTrue(backend._focused_browser)
        changed.assert_called_once_with(True)

        backend._on_app_category_changed(
            None, None, None, None, None, _Parameters("editor")
        )
        self.assertFalse(backend._focused_browser)
        self.assertEqual(changed.call_args_list[-1].args, (False,))

    def test_browser_focus_loss_stops_focus_dependent_media_immediately(self) -> None:
        stopped = Mock()
        backend = Mock()
        backend.watching_via_browser_focus = True
        monitor = MediaActivityMonitor(
            on_youtube_started=Mock(),
            on_youtube_stopped=stopped,
            backend=backend,
        )
        monitor.available = True
        monitor.youtube_playing = True
        monitor._last_playing_at = 10.0

        monitor._on_browser_focus_changed(False)

        self.assertFalse(monitor.youtube_playing)
        self.assertIsNone(monitor._last_playing_at)
        stopped.assert_called_once_with()

    def test_helper_loss_clears_focus_state_and_stops_focus_dependent_media(self) -> None:
        stopped = Mock()
        backend = MprisMediaBackend()
        monitor = MediaActivityMonitor(
            on_youtube_started=Mock(),
            on_youtube_stopped=stopped,
            backend=backend,
        )
        monitor.available = True
        monitor.youtube_playing = True
        monitor._last_playing_at = 10.0
        backend._youtube_focused = True
        backend._focused_browser = True
        backend._watching_via_youtube_focus = True

        backend.on_gnome_helper_unavailable()
        backend.on_gnome_helper_unavailable()

        self.assertFalse(backend._youtube_focused)
        self.assertFalse(backend._focused_browser)
        self.assertFalse(monitor.youtube_playing)
        stopped.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
