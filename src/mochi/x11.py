"""Small X11 window-manager helpers used by the GNOME XWayland fallback."""

from __future__ import annotations

import ctypes
import ctypes.util
import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

try:
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11  # type: ignore[attr-defined]  # noqa: E402
except (ImportError, ValueError):
    GdkX11 = None


_BUTTON1_MASK = 1 << 8


class _ClientMessageData(ctypes.Union):
    _fields_ = [("longs", ctypes.c_long * 5)]


class _ClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", _ClientMessageData),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [
        ("client", _ClientMessageEvent),
        ("padding", ctypes.c_long * 24),
    ]


def request_keep_above(window: Gtk.Window) -> bool:
    """Ask an EWMH-compatible X11 window manager to keep Mochi above others."""
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return False

    library_name = ctypes.util.find_library("X11")
    if library_name is None:
        logging.getLogger(__name__).warning("libX11 not found; cannot request always-on-top")
        return False

    x11 = ctypes.CDLL(library_name)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XRootWindow.restype = ctypes.c_ulong
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XSendEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_long,
        ctypes.POINTER(_XEvent),
    ]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

    display = x11.XOpenDisplay(None)
    if not display:
        return False

    try:
        root = x11.XRootWindow(display, x11.XDefaultScreen(display))
        wm_state = x11.XInternAtom(display, b"_NET_WM_STATE", False)
        above = x11.XInternAtom(display, b"_NET_WM_STATE_ABOVE", False)
        event = _XEvent()
        event.client.type = 33  # ClientMessage
        event.client.display = display
        event.client.window = surface.get_xid()
        event.client.message_type = wm_state
        event.client.format = 32
        event.client.data.longs[:] = (1, above, 0, 1, 0)  # add, atom, source=app
        sent = x11.XSendEvent(
            display,
            root,
            False,
            (1 << 19) | (1 << 20),  # SubstructureNotifyMask | RedirectMask
            ctypes.byref(event),
        )
        x11.XFlush(display)
        surface.set_skip_taskbar_hint(True)
        return bool(sent)
    finally:
        x11.XCloseDisplay(display)

def apply_sticky_dock_properties(window: Gtk.Window) -> bool:
    """Mark the XWayland window as a sticky dock on the X11 window manager.

    On GNOME Wayland, Mochi runs as a regular X11 window managed by Mutter.
    That binds the window to a single workspace and lets Mutter focus it (and
    its workspace) on interaction. Setting the EWMH properties below turns
    Mochi into a desktop-wide overlay:

    - ``_NET_WM_DESKTOP = 0xFFFFFFFF`` marks the window as sticky, so it is
      visible on every virtual desktop.
    - ``_NET_WM_WINDOW_TYPE_DOCK`` makes Mutter treat it as a panel/dock
      rather than an application window, preventing workspace switches when
      the window is interacted with.
    - ``_NET_WM_STATE_SKIP_TASKBAR`` / ``_NET_WM_STATE_SKIP_PAGER`` keep it
      out of the taskbar and workspace switcher.
    """
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return False

    library_name = ctypes.util.find_library("X11")
    if library_name is None:
        logging.getLogger(__name__).warning(
            "libX11 not found; cannot apply sticky/dock window properties"
        )
        return False

    x11 = ctypes.CDLL(library_name)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x11.XInternAtom.restype = ctypes.c_ulong
    x11.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    x11.XChangeProperty.restype = ctypes.c_int
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

    display = x11.XOpenDisplay(None)
    if not display:
        return False

    _XA_ATOM = 4
    _XA_CARDINAL = 6

    def _set_property(name: bytes, type_atom: int, values: list[int]) -> None:
        prop = x11.XInternAtom(display, name, False)
        count = len(values)
        array = (ctypes.c_ulong * count)(*values)
        x11.XChangeProperty(
            display,
            surface.get_xid(),
            prop,
            type_atom,
            32,
            0,
            ctypes.cast(array, ctypes.c_void_p),
            count,
        )

    try:
        _set_property(b"_NET_WM_DESKTOP", _XA_CARDINAL, [0xFFFFFFFF])
        _set_property(
            b"_NET_WM_WINDOW_TYPE",
            _XA_ATOM,
            [x11.XInternAtom(display, b"_NET_WM_WINDOW_TYPE_DOCK", False)],
        )
        _set_property(
            b"_NET_WM_STATE",
            _XA_ATOM,
            [
                x11.XInternAtom(display, b"_NET_WM_STATE_SKIP_TASKBAR", False),
                x11.XInternAtom(display, b"_NET_WM_STATE_SKIP_PAGER", False),
                x11.XInternAtom(display, b"_NET_WM_STATE_STICKY", False),
                x11.XInternAtom(display, b"_NET_WM_STATE_ABOVE", False),
            ],
        )
        x11.XFlush(display)
    finally:
        x11.XCloseDisplay(display)

    return True

def move_window(window: Gtk.Window, x: int, y: int) -> bool:
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return False
    x11, display = _open_x11()
    if display is None:
        return False
    try:
        x11.XMoveWindow(display, surface.get_xid(), x, y)
        x11.XFlush(display)
        return True
    finally:
        x11.XCloseDisplay(display)


def get_window_position(window: Gtk.Window) -> tuple[int, int] | None:
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return None
    x11, display = _open_x11()
    if display is None:
        return None
    try:
        root = x11.XRootWindow(display, x11.XDefaultScreen(display))
        x = ctypes.c_int()
        y = ctypes.c_int()
        child = ctypes.c_ulong()
        translated = x11.XTranslateCoordinates(
            display,
            surface.get_xid(),
            root,
            0,
            0,
            ctypes.byref(x),
            ctypes.byref(y),
            ctypes.byref(child),
        )
        return (x.value, y.value) if translated else None
    finally:
        x11.XCloseDisplay(display)


def get_pointer_position(window: Gtk.Window) -> tuple[int, int] | None:
    """Return the pointer position in X11 root/device coordinates."""
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return None

    x11, display = _open_x11()
    if display is None:
        return None

    try:
        root = ctypes.c_ulong()
        child = ctypes.c_ulong()
        root_x = ctypes.c_int()
        root_y = ctypes.c_int()
        window_x = ctypes.c_int()
        window_y = ctypes.c_int()
        mask = ctypes.c_uint()
        queried = x11.XQueryPointer(
            display,
            surface.get_xid(),
            ctypes.byref(root),
            ctypes.byref(child),
            ctypes.byref(root_x),
            ctypes.byref(root_y),
            ctypes.byref(window_x),
            ctypes.byref(window_y),
            ctypes.byref(mask),
        )
        return (root_x.value, root_y.value) if queried else None
    finally:
        x11.XCloseDisplay(display)


def primary_button_pressed(window: Gtk.Window) -> bool:
    """Return whether X11 button 1 is currently held for Mochi's display."""
    surface = window.get_surface()
    if GdkX11 is None or not isinstance(surface, GdkX11.X11Surface):
        return False

    x11, display = _open_x11()
    if display is None:
        return False

    try:
        root = ctypes.c_ulong()
        child = ctypes.c_ulong()
        root_x = ctypes.c_int()
        root_y = ctypes.c_int()
        window_x = ctypes.c_int()
        window_y = ctypes.c_int()
        mask = ctypes.c_uint()
        queried = x11.XQueryPointer(
            display,
            surface.get_xid(),
            ctypes.byref(root),
            ctypes.byref(child),
            ctypes.byref(root_x),
            ctypes.byref(root_y),
            ctypes.byref(window_x),
            ctypes.byref(window_y),
            ctypes.byref(mask),
        )
        return bool(queried and mask.value & _BUTTON1_MASK)
    finally:
        x11.XCloseDisplay(display)


def _open_x11() -> tuple[ctypes.CDLL, int | None]:
    library_name = ctypes.util.find_library("X11")
    if library_name is None:
        return ctypes.CDLL(None), None
    x11 = ctypes.CDLL(library_name)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XRootWindow.restype = ctypes.c_ulong
    x11.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
    x11.XTranslateCoordinates.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_ulong),
    ]
    x11.XQueryPointer.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_uint),
    ]
    x11.XQueryPointer.restype = ctypes.c_int
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    return x11, x11.XOpenDisplay(None)
