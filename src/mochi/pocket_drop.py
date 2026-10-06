"""Thin GTK4 drag-and-drop adapter for Mochi Pocket."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from mochi.pocket import PocketItem, make_local_file_item, make_text_item, make_url_item
from mochi.pocket_controller import PocketController


def items_from_file_payload(files: Iterable[object]) -> tuple[PocketItem, ...]:
    """Convert a GTK file list to one all-local Pocket batch."""
    items: list[PocketItem] = []
    for value in files:
        if isinstance(value, (str, Path)):
            path = str(value)
        else:
            getter = getattr(value, "get_path", None)
            path = getter() if callable(getter) else None
        if not path:
            raise ValueError("Pocket file drops must contain only local files")
        items.append(make_local_file_item(path))
    if not items:
        raise ValueError("Pocket file drops must not be empty")
    return tuple(items)


def _existing_local_path_from_string(candidate: str) -> Path | None:
    """Resolve supported string representations of local existing paths."""
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("Pocket file URI must reference this computer")
        if parsed.query or parsed.fragment:
            raise ValueError("Pocket file URI must not include query or fragment")
        path = Path(unquote(parsed.path))
        if not path.is_absolute() or not path.exists():
            raise ValueError("Pocket file URI does not reference an available local path")
        return path

    if parsed.scheme:
        return None

    path = Path(candidate).expanduser()
    if path.is_absolute() and path.exists():
        return path
    return None


def items_from_string_payload(value: str) -> PocketItem:
    """Classify a GTK string as local path, HTTP(S) URL, or literal text."""
    if not isinstance(value, str):
        raise TypeError("Pocket string payload must be text")
    candidate = value.strip()
    if not candidate:
        raise ValueError("Pocket string payload must not be empty")

    local_path = _existing_local_path_from_string(candidate)
    if local_path is not None:
        return make_local_file_item(local_path)

    parsed = urlsplit(candidate)
    if parsed.scheme:
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("Pocket does not support this URI scheme")
        return make_url_item(candidate)
    return make_text_item(value)


def texture_to_png_bytes(texture: object) -> bytes:
    """Encode a Gdk.Texture-like value without exposing GTK to the domain."""
    encode = getattr(texture, "save_to_png_bytes", None)
    if not callable(encode):
        raise TypeError("Pocket texture payload cannot be encoded as PNG")
    encoded = encode()
    if isinstance(encoded, bytes):
        data = encoded
    else:
        get_data = getattr(encoded, "get_data", None)
        if not callable(get_data):
            raise TypeError("Pocket texture PNG encoder returned unsupported data")
        data = bytes(get_data())
    if not data:
        raise ValueError("Pocket texture PNG data must not be empty")
    return data


class PocketDropAdapter:
    """Install supported GTK drop targets and forward completed payloads."""

    def __init__(
        self,
        widget: Gtk.Widget,
        controller: PocketController,
        *,
        target_factory: Callable[[object, Gdk.DragAction], object] | None = None,
    ) -> None:
        self._widget = widget
        self._controller = controller
        self._target_factory = target_factory or Gtk.DropTarget.new
        self._targets: list[object] = []
        self._install_target(Gdk.FileList, self._receive_files)
        self._install_target(str, self._receive_string)
        self._install_target(Gdk.Texture, self._receive_texture)

    @property
    def targets(self) -> tuple[object, ...]:
        return tuple(self._targets)

    def detach(self) -> None:
        self._controller.end_hover()
        remover = getattr(self._widget, "remove_controller", None)
        if callable(remover):
            for target in self._targets:
                remover(target)
        self._targets.clear()

    def _install_target(self, value_type: object, receive: Callable[[Any], bool]) -> None:
        target = self._target_factory(value_type, Gdk.DragAction.COPY)
        target.connect("enter", self._on_enter)
        target.connect("motion", self._on_motion)
        target.connect("leave", self._on_leave)
        target.connect(
            "drop",
            lambda target, value, _x, _y: (
                False if self._is_own_drag(target) else self._on_drop(value, receive)
            ),
        )
        self._widget.add_controller(target)
        self._targets.append(target)

    def _on_enter(self, target, _x: float, _y: float) -> Gdk.DragAction:
        if self._is_own_drag(target):
            return Gdk.DragAction(0)
        return self._drag_action()

    def _on_motion(self, target, _x: float, _y: float) -> Gdk.DragAction:
        if self._is_own_drag(target):
            return Gdk.DragAction(0)
        return self._drag_action()

    @staticmethod
    def _is_own_drag(target) -> bool:
        """A drag out of Mochi's own Pocket tray must never re-enter it."""
        get_drop = getattr(target, "get_current_drop", None)
        drop = get_drop() if callable(get_drop) else None
        get_drag = getattr(drop, "get_drag", None)
        return callable(get_drag) and get_drag() is not None

    def _on_leave(self, _target) -> None:
        self._controller.end_hover()

    def _drag_action(self) -> Gdk.DragAction:
        accepted = self._controller.begin_hover()
        return Gdk.DragAction.COPY if accepted else Gdk.DragAction(0)

    def _on_drop(self, value: object, receive: Callable[[Any], bool]) -> bool:
        if not self._controller.begin_hover():
            self._controller.reject_busy()
            return False
        try:
            return bool(receive(value))
        except (AttributeError, GLib.Error, OSError, TypeError, ValueError):
            self._controller.reject_unsupported()
            self._controller.end_hover()
            return False

    def _receive_files(self, value: object) -> bool:
        get_files = getattr(value, "get_files", None)
        files = get_files() if callable(get_files) else value
        return self._controller.receive(items_from_file_payload(files))

    def _receive_string(self, value: object) -> bool:
        return self._controller.receive((items_from_string_payload(value),))

    def _receive_texture(self, value: object) -> bool:
        return self._controller.receive_image(texture_to_png_bytes(value))
