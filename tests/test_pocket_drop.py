"""GTK-thin Pocket drag-and-drop adapter coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from mochi.pocket import PocketItemKind
from mochi.pocket_drop import (
    PocketDropAdapter,
    items_from_file_payload,
    items_from_string_payload,
    texture_to_png_bytes,
)


class _File:
    def __init__(self, path: str | None) -> None:
        self._path = path

    def get_path(self) -> str | None:
        return self._path


class _Texture:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def save_to_png_bytes(self):
        return self.data


class _Target:
    def __init__(self, value_type, action) -> None:
        self.value_type = value_type
        self.action = action
        self.callbacks = {}

    def connect(self, signal, callback) -> None:
        self.callbacks[signal] = callback


class _Widget:
    def __init__(self) -> None:
        self.controllers = []

    def add_controller(self, controller) -> None:
        self.controllers.append(controller)


class _Controller:
    def __init__(self) -> None:
        self.accepting = True
        self.received = []
        self.images = []
        self.rejections = 0
        self.busy_rejections = 0
        self.hover_starts = 0
        self.hover_ends = 0
        self.hover_active = False

    def can_receive(self) -> bool:
        return self.accepting

    def begin_hover(self) -> bool:
        if not self.accepting:
            return False
        if not self.hover_active:
            self.hover_starts += 1
            self.hover_active = True
        return True

    def end_hover(self) -> None:
        if self.hover_active:
            self.hover_ends += 1
            self.hover_active = False

    def receive(self, items) -> bool:
        self.received.append(tuple(items))
        self.hover_active = False
        return True

    def receive_image(self, png_bytes: bytes) -> bool:
        self.images.append(png_bytes)
        self.hover_active = False
        return True

    def reject_unsupported(self) -> None:
        self.rejections += 1

    def reject_busy(self) -> None:
        self.busy_rejections += 1


def _adapter():
    widget = _Widget()
    controller = _Controller()
    targets = []

    def target_factory(value_type, action):
        target = _Target(value_type, action)
        targets.append(target)
        return target

    adapter = PocketDropAdapter(
        widget,
        controller,
        target_factory=target_factory,
    )
    return adapter, widget, controller, targets


def test_file_payload_becomes_one_normalized_item_per_local_path(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "folder"

    items = items_from_file_payload([_File(str(first)), _File(str(second))])

    assert tuple(item.kind for item in items) == (
        PocketItemKind.LOCAL_FILE,
        PocketItemKind.LOCAL_FILE,
    )
    assert tuple(item.value for item in items) == (
        str(first.resolve()),
        str(second.resolve()),
    )


def test_non_local_file_payload_rejects_the_complete_batch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="local"):
        items_from_file_payload([_File(str(tmp_path / "ok")), _File(None)])


def test_string_payload_classifies_http_urls_before_plain_text() -> None:
    url = items_from_string_payload("  HTTPS://Example.COM/page  ")
    path_like_text = items_from_string_payload("/tmp/example.txt")

    assert url.kind is PocketItemKind.URL
    assert url.value == "https://example.com/page"
    assert path_like_text.kind is PocketItemKind.TEXT
    assert path_like_text.value == "/tmp/example.txt"


def test_string_payload_classifies_existing_absolute_file_and_directory_paths(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")
    directory_path = tmp_path / "folder"
    directory_path.mkdir()

    file_item = items_from_string_payload(str(file_path))
    directory_item = items_from_string_payload(str(directory_path))

    assert file_item.kind is PocketItemKind.LOCAL_FILE
    assert file_item.value == str(file_path.resolve())
    assert directory_item.kind is PocketItemKind.LOCAL_FILE
    assert directory_item.value == str(directory_path.resolve())


def test_string_payload_classifies_existing_file_uri_with_escaped_spaces(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "with space.txt"
    file_path.write_text("hello", encoding="utf-8")

    item = items_from_string_payload(file_path.as_uri())

    assert item.kind is PocketItemKind.LOCAL_FILE
    assert item.value == str(file_path.resolve())


def test_nonexistent_absolute_path_text_remains_literal_text(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    item = items_from_string_payload(str(missing))

    assert item.kind is PocketItemKind.TEXT
    assert item.value == str(missing)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "file:///definitely-does-not-exist/mochi-pocket.txt",
        "file://example.com/tmp/mochi-pocket.txt",
        "mailto:a@b.test",
    ],
)
def test_empty_unsupported_or_unavailable_uri_strings_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        items_from_string_payload(value)


def test_texture_is_encoded_to_png_bytes() -> None:
    assert texture_to_png_bytes(_Texture(b"png-data")) == b"png-data"


def test_motion_starts_hover_preview_without_receiving_or_restarting() -> None:
    _adapter_instance, _widget, controller, targets = _adapter()
    file_target = targets[0]

    action = file_target.callbacks["enter"](file_target, 1.0, 2.0)
    motion_action = file_target.callbacks["motion"](file_target, 2.0, 3.0)
    file_target.callbacks["leave"](file_target)

    assert int(action) != 0
    assert int(motion_action) != 0
    assert controller.hover_starts == 1
    assert controller.hover_ends == 1
    assert controller.received == []
    assert controller.images == []


def test_file_drop_forwards_one_batch_and_clears_highlight(tmp_path: Path) -> None:
    _adapter_instance, _widget, controller, targets = _adapter()
    file_target = targets[0]
    payload = [_File(str(tmp_path / "a")), _File(str(tmp_path / "b"))]

    assert file_target.callbacks["drop"](file_target, payload, 1.0, 2.0)

    assert len(controller.received) == 1
    assert len(controller.received[0]) == 2
    assert controller.hover_starts == 1
    assert controller.hover_active is False


def test_texture_drop_hands_png_bytes_to_controller() -> None:
    _adapter_instance, _widget, controller, targets = _adapter()
    texture_target = targets[2]

    assert texture_target.callbacks["drop"](
        texture_target, _Texture(b"png-data"), 1.0, 2.0
    )

    assert controller.images == [b"png-data"]
    assert controller.hover_starts == 1
    assert controller.hover_active is False


def test_busy_controller_rejects_motion_and_drop_without_mutation(
    tmp_path: Path,
) -> None:
    _adapter_instance, _widget, controller, targets = _adapter()
    controller.accepting = False
    file_target = targets[0]

    action = file_target.callbacks["motion"](file_target, 1.0, 2.0)
    accepted = file_target.callbacks["drop"](
        file_target, [_File(str(tmp_path / "a"))], 1.0, 2.0
    )

    assert int(action) == 0
    assert accepted is False
    assert controller.hover_starts == 0
    assert controller.hover_ends == 0
    assert controller.received == []
    assert controller.busy_rejections == 1


def test_unsupported_string_drop_reports_rejection_without_receiving() -> None:
    _adapter_instance, _widget, controller, targets = _adapter()
    string_target = targets[1]

    accepted = string_target.callbacks["drop"](
        string_target, "file:///tmp/a", 1.0, 2.0
    )

    assert accepted is False
    assert controller.rejections == 1
    assert controller.received == []
    assert controller.hover_starts == 1
    assert controller.hover_ends == 1


class _Drop:
    def __init__(self, drag) -> None:
        self._drag = drag

    def get_drag(self):
        return self._drag


class _OwnDragTarget(_Target):
    def get_current_drop(self):
        return _Drop(drag=object())


def test_drags_that_start_inside_mochi_are_refused_silently(tmp_path: Path) -> None:
    from gi.repository import Gdk

    controller = _Controller()
    adapter = PocketDropAdapter(
        _Widget(), controller, target_factory=_OwnDragTarget
    )
    file_target = adapter.targets[0]
    document = tmp_path / "report.pdf"
    document.write_bytes(b"%PDF")

    assert file_target.callbacks["enter"](file_target, 1.0, 2.0) == Gdk.DragAction(0)
    assert file_target.callbacks["motion"](file_target, 1.0, 2.0) == Gdk.DragAction(0)
    assert file_target.callbacks["drop"](file_target, [_File(str(document))], 1.0, 2.0) is False

    assert controller.hover_starts == 0
    assert controller.received == []
    assert controller.rejections == 0
    assert controller.busy_rejections == 0
