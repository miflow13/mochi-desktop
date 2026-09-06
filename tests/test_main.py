import unittest

from mochi.main import configure_display_backend


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
