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

def _send_wm_state_client_message(
    x11,
    display,
    window_id: int,
    action: int,
    first_atom: int,
    second_atom: int = 0,
) -> None:
    """Send a single _NET_WM_STATE ClientMessage to the root window.

    ``action`` follows the EWMH convention: 0 = remove, 1 = add, 2 = toggle.
    ``first_atom`` and ``second_atom`` are the state atoms to apply; the
    second may be 0 when only one property is being changed.
    """
    root = x11.XRootWindow(display, x11.XDefaultScreen(display))
    wm_state = x11.XInternAtom(display, b"_NET_WM_STATE", False)
    event = _XEvent()
    event.client.type = 33  # ClientMessage
    event.client.display = display
    event.client.window = window_id
    event.client.message_type = wm_state
    event.client.format = 32
    event.client.data.longs[:] = (action, first_atom, second_atom, 1, 0)
    x11.XSendEvent(
        display,
        root,
        False,
        (1 << 19) | (1 << 20),  # SubstructureNotifyMask | RedirectMask
        ctypes.byref(event),
    )


def _send_wm_desktop_client_message(
    x11,
    display,
    window_id: int,
    desktop: int,
) -> None:
    """Send a single _NET_WM_DESKTOP ClientMessage to the root window.

    ``desktop`` uses 0xFFFFFFFF for "sticky / all desktops", or a concrete
    index (0-based) for a specific virtual desktop.
    """
    root = x11.XRootWindow(display, x11.XDefaultScreen(display))
    wm_desktop = x11.XInternAtom(display, b"_NET_WM_DESKTOP", False)
    event = _XEvent()
    event.client.type = 33  # ClientMessage
    event.client.display = display
    event.client.window = window_id
    event.client.message_type = wm_desktop
    event.client.format = 32
    event.client.data.longs[:] = (desktop, 1, 0, 0, 0)
    x11.XSendEvent(
        display,
        root,
        False,
        (1 << 19) | (1 << 20),  # SubstructureNotifyMask | RedirectMask
        ctypes.byref(event),
    )

def apply_sticky_dock_properties(window: Gtk.Window) -> bool:
    """Make an XWayland window a sticky, non-focus-stealing desktop overlay.

    On GNOME Wayland, Mochi runs as a regular X11 window managed by Mutter,
    which binds the window to a single workspace and lets Mutter focus it on
    interaction. This helper marks the window as a dock and then asks the WM
    to make it sticky, skip the taskbar/pager, and stay above.

    EWMH expects the window type to be set before the window is mapped, and
    state/desktop changes to be sent as ClientMessages to the root window
    once the window is managed. The helper mirrors that split so Mutter does
    not race or overwrite our requests.
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
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XRootWindow.restype = ctypes.c_ulong
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

    _XA_ATOM = 4
    _NET_WM_STATE_ADD = 1

    try:
        window_id = surface.get_xid()

        # Window type must be set before the WM starts managing the window.
        # GdkX11 X11Surface.get_xid() is the same id the WM sees in
        # MapRequest, so writing it here is the correct pre-map step.
        dock_atom = x11.XInternAtom(
            display, b"_NET_WM_WINDOW_TYPE_DOCK", False
        )
        type_prop = x11.XInternAtom(display, b"_NET_WM_WINDOW_TYPE", False)
        type_values = (ctypes.c_ulong * 1)(dock_atom)
        x11.XChangeProperty(
            display,
            window_id,
            type_prop,
            _XA_ATOM,
            32,
            0,
            ctypes.cast(type_values, ctypes.c_void_p),
            1,
        )

        # State and desktop changes must go through ClientMessages once the
        # window is mapped so the WM owns the update, matching the protocol
        # already used by request_keep_above().
        sticky = x11.XInternAtom(display, b"_NET_WM_STATE_STICKY", False)
        skip_taskbar = x11.XInternAtom(
            display, b"_NET_WM_STATE_SKIP_TASKBAR", False
        )
        skip_pager = x11.XInternAtom(
            display, b"_NET_WM_STATE_SKIP_PAGER", False
        )
        above = x11.XInternAtom(display, b"_NET_WM_STATE_ABOVE", False)

        _send_wm_state_client_message(
            x11, display, window_id, _NET_WM_STATE_ADD, sticky
        )
        _send_wm_state_client_message(
            x11, display, window_id, _NET_WM_STATE_ADD, skip_taskbar
        )
        _send_wm_state_client_message(
            x11, display, window_id, _NET_WM_STATE_ADD, skip_pager
        )
        _send_wm_state_client_message(
            x11, display, window_id, _NET_WM_STATE_ADD, above
        )

        # 0xFFFFFFFF means "show on all desktops" in EWMH.
        _send_wm_desktop_client_message(
            x11, display, window_id, 0xFFFFFFFF
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
