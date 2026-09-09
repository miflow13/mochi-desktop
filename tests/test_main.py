import unittest
from pathlib import Path
import tomllib

from mochi import __version__
from mochi.main import configure_display_backend, run_application


class DisplayBackendTests(unittest.TestCase):
    def test_keyboard_interrupt_exits_without_propagating_a_traceback(self) -> None:
        class InterruptedApplication:
            def run(self, _arguments):
                raise KeyboardInterrupt

        self.assertEqual(run_application(InterruptedApplication(), "mochi"), 130)

    def test_runtime_version_matches_package_metadata(self) -> None:
        project = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(__version__, project["project"]["version"])

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
