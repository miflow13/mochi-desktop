"""Command-line entry point for Mochi."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import MutableMapping

from mochi.config import ConfigStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A tiny friend for your desktop.")
    parser.add_argument("--debug", action="store_true", help="show debug logging")
    parser.add_argument(
        "--preview-animations",
        action="store_true",
        help="cycle through sprite animations with left-click",
    )
    parser.add_argument(
        "--reset-position",
        action="store_true",
        help="forget Mochi's saved position before starting",
    )
    return parser


def configure_display_backend(environment: MutableMapping[str, str]) -> bool:
    """Use XWayland for the pet on GNOME, following Codex's Linux approach."""
    desktop = environment.get("XDG_CURRENT_DESKTOP", "").casefold()
    is_gnome_wayland = (
        environment.get("XDG_SESSION_TYPE", "").casefold() == "wayland"
        and "gnome" in desktop
        and bool(environment.get("DISPLAY"))
    )
    if not is_gnome_wayland or environment.get("MOCHI_NATIVE_WAYLAND") == "1":
        return False

    # Mutter does not expose layer shell. XWayland gives this small standalone
    # buddy the transparent, freely movable window path used by Codex's pet,
    # while the rest of the desktop remains native Wayland.
    environment["GDK_BACKEND"] = "x11"
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected_xwayland = configure_display_backend(os.environ)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.debug:
        logging.getLogger(__name__).debug(
            "Display environment: session_type=%r current_desktop=%r "
            "session_desktop=%r wayland_display=%r display=%r "
            "gdk_backend=%r forced_xwayland=%s",
            os.environ.get("XDG_SESSION_TYPE"),
            os.environ.get("XDG_CURRENT_DESKTOP"),
            os.environ.get("XDG_SESSION_DESKTOP"),
            os.environ.get("WAYLAND_DISPLAY"),
            os.environ.get("DISPLAY"),
            os.environ.get("GDK_BACKEND"),
            selected_xwayland,
        )
    if selected_xwayland:
        logging.getLogger(__name__).info(
            "GNOME Wayland detected; using XWayland for the buddy window"
        )

    config = ConfigStore()
    if args.reset_position:
        config.reset_position()

    # Import GTK only when actually launching. This keeps config and state tests
    # usable on machines without a graphical session.
    try:
        from mochi.app import MochiApplication
    except (ImportError, ValueError) as error:
        logging.getLogger(__name__).error(
            "GTK4/PyGObject is required to run Mochi: %s", error
        )
        return 1

    application = MochiApplication(
        config=config, preview_animations=args.preview_animations
    )
    return application.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
