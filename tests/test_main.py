import unittest

from mochi.main import build_parser, configure_display_backend


class CliTests(unittest.TestCase):
    def test_trailer_entrance_flag_is_opt_in(self) -> None:
        parser = build_parser()

        self.assertFalse(parser.parse_args([]).trailer_entrance)
        self.assertTrue(parser.parse_args(["--trailer-entrance"]).trailer_entrance)


class DisplayBackendTests(unittest.TestCase):
    def test_gnome_wayland_selects_xwayland(self) -> None:
        environment = {
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "GNOME",
            "DISPLAY": ":0",
        }

        self.assertTrue(configure_display_backend(environment))
        self.assertEqual(environment["GDK_BACKEND"], "x11")

    def test_session_default_wayland_backend_is_overridden(self) -> None:
        environment = {
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "GNOME",
            "DISPLAY": ":0",
            "GDK_BACKEND": "wayland",
        }

        self.assertTrue(configure_display_backend(environment))
        self.assertEqual(environment["GDK_BACKEND"], "x11")

    def test_mochi_native_wayland_opt_out_is_preserved(self) -> None:
        environment = {
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "GNOME",
            "DISPLAY": ":0",
            "GDK_BACKEND": "wayland",
            "MOCHI_NATIVE_WAYLAND": "1",
        }

        self.assertFalse(configure_display_backend(environment))
        self.assertEqual(environment["GDK_BACKEND"], "wayland")


if __name__ == "__main__":
    unittest.main()
