"""Pocket management window and safe action coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock


from mochi.pocket import (
    make_local_file_item,
    make_text_item,
    make_url_item,
)
from mochi.pocket_window import PocketTextWindow, PocketWindow


class _Controller:
    def __init__(self, items=()) -> None:
        self._items = tuple(items)
        self.removed = []
        self.clear_calls = 0
        self.clear_succeeds = True
        self.on_changed = None

    @property
    def items(self):
        return self._items

    def remove(self, item_id: str) -> bool:
        self.removed.append(item_id)
        self._items = tuple(item for item in self._items if item.id != item_id)
        if self.on_changed is not None:
            self.on_changed()
        return True

    def clear_all(self) -> bool:
        self.clear_calls += 1
        if not self.clear_succeeds:
            return False
        self._items = ()
        if self.on_changed is not None:
            self.on_changed()
        return True


def test_empty_pocket_shows_drag_explanation() -> None:
    window = PocketWindow(_Controller())

    assert window.empty_visible is True
    assert window.get_hide_on_close() is True
    assert window.rows == {}
    assert "drag" in window.empty_text.lower()


def test_list_rows_show_available_and_missing_file_states(tmp_path: Path) -> None:
    available_path = tmp_path / "available.txt"
    available_path.write_text("hello", encoding="utf-8")
    available = make_local_file_item(available_path, received_at=2)
    missing = make_local_file_item(tmp_path / "missing.txt", received_at=1)

    window = PocketWindow(_Controller((available, missing)))

    assert window.empty_visible is False
    assert window.rows[available.id].model.available is True
    assert window.rows[available.id].open_button.get_sensitive() is True
    assert window.rows[missing.id].model.available is False
    assert window.rows[missing.id].open_button.get_sensitive() is False
    assert "Unavailable" in window.rows[missing.id].model.subtitle


def test_open_file_and_url_use_validated_uris(tmp_path: Path) -> None:
    path = tmp_path / "note with spaces.txt"
    path.write_text("hello", encoding="utf-8")
    file_item = make_local_file_item(path)
    url_item = make_url_item("https://example.com/page")
    launched = []
    window = PocketWindow(
        _Controller((file_item, url_item)),
        launcher=launched.append,
    )

    window.open_item(file_item.id)
    window.open_item(url_item.id)

    assert launched == [path.as_uri(), "https://example.com/page"]

def test_local_file_row_can_open_its_containing_folder(tmp_path: Path) -> None:
    folder = tmp_path / "documents"
    folder.mkdir()
    path = folder / "note.txt"
    path.write_text("hello", encoding="utf-8")
    file_item = make_local_file_item(path)
    text_item = make_text_item("hello")
    launched = []
    window = PocketWindow(
        _Controller((file_item, text_item)),
        launcher=launched.append,
    )

    file_row = window.rows[file_item.id]
    assert file_row.folder_button is not None
    assert file_row.folder_button.get_sensitive() is True
    assert window.rows[text_item.id].folder_button is None

    file_row.folder_button.emit("clicked")

    assert launched == [folder.as_uri()]


def test_missing_local_file_disables_containing_folder_action(tmp_path: Path) -> None:
    item = make_local_file_item(tmp_path / "missing.txt")
    window = PocketWindow(_Controller((item,)))

    folder_button = window.rows[item.id].folder_button

    assert folder_button is not None
    assert folder_button.get_sensitive() is False


def test_text_opens_in_a_read_only_detail_window() -> None:
    item = make_text_item("full\ntext")
    window = PocketWindow(_Controller((item,)))

    assert window.open_item(item.id) is True

    detail = window.detail_windows[-1]
    assert isinstance(detail, PocketTextWindow)
    assert detail.text_view.get_editable() is False
    assert detail.text_view.get_cursor_visible() is False
    start, end = detail.text_view.get_buffer().get_bounds()
    assert detail.text_view.get_buffer().get_text(start, end, True) == "full\ntext"

def test_closed_text_detail_window_is_released_from_owner() -> None:
    item = make_text_item("close me")
    window = PocketWindow(_Controller((item,)))
    assert window.open_item(item.id) is True
    detail = window.detail_windows[-1]

    detail.emit("close-request")

    assert detail not in window.detail_windows



def test_destroy_closes_owned_text_detail_windows() -> None:
    window = PocketWindow(_Controller())
    detail = Mock()
    window.detail_windows.append(detail)

    window.destroy()

    detail.destroy.assert_called_once_with()
    assert window.detail_windows == []


def test_remove_dispatches_to_controller_and_refreshes_rows() -> None:
    item = make_text_item("remove me")
    controller = _Controller((item,))
    window = PocketWindow(controller)

    window.rows[item.id].remove_button.emit("clicked")

    assert controller.removed == [item.id]
    assert window.rows == {}
    assert window.empty_visible is True


def test_launch_failure_preserves_item_and_shows_feedback() -> None:
    item = make_url_item("https://example.com")
    controller = _Controller((item,))

    def fail(_uri: str) -> None:
        raise OSError("no handler")

    window = PocketWindow(controller, launcher=fail)

    assert window.open_item(item.id) is False

    assert controller.items == (item,)
    assert controller.removed == []
    assert "couldn't open" in window.error_text.lower()



def test_clear_all_button_is_disabled_when_pocket_is_empty() -> None:
    window = PocketWindow(_Controller())

    assert window.clear_button.get_sensitive() is False


def test_clear_all_requires_confirmation_then_refreshes_to_empty() -> None:
    controller = _Controller((make_text_item("one"), make_text_item("two")))
    window = PocketWindow(controller)

    assert window.clear_button.get_sensitive() is True
    window.clear_button.emit("clicked")

    dialog = window.clear_dialog
    assert dialog is not None
    assert controller.clear_calls == 0

    dialog.respond(True)

    assert controller.clear_calls == 1
    assert window.clear_dialog is None
    assert window.rows == {}
    assert window.empty_visible is True
    assert window.clear_button.get_sensitive() is False


def test_clear_all_cancel_preserves_items() -> None:
    item = make_text_item("keep")
    controller = _Controller((item,))
    window = PocketWindow(controller)

    window.clear_button.emit("clicked")
    dialog = window.clear_dialog
    assert dialog is not None

    dialog.respond(False)

    assert controller.clear_calls == 0
    assert tuple(window.rows) == (item.id,)
    assert window.clear_dialog is None


def test_clear_all_failure_preserves_rows_and_shows_error() -> None:
    item = make_text_item("keep")
    controller = _Controller((item,))
    controller.clear_succeeds = False
    window = PocketWindow(controller)

    window.clear_button.emit("clicked")
    dialog = window.clear_dialog
    assert dialog is not None
    dialog.respond(True)

    assert controller.clear_calls == 1
    assert tuple(window.rows) == (item.id,)
    assert "couldn't clear" in window.error_text.lower()


def test_clear_all_closes_owned_text_detail_windows() -> None:
    item = make_text_item("detail")
    controller = _Controller((item,))
    window = PocketWindow(controller)
    detail = Mock()
    window.detail_windows.append(detail)

    window.clear_button.emit("clicked")
    dialog = window.clear_dialog
    assert dialog is not None
    dialog.respond(True)

    detail.destroy.assert_called_once_with()
    assert window.detail_windows == []



def test_remove_avoids_duplicate_refresh_when_change_callback_already_synced() -> None:
    item = make_text_item("remove once")
    controller = _Controller((item,))
    window = PocketWindow(controller)
    controller.on_changed = lambda: window.refresh()
    original_refresh = window.refresh
    window.refresh = Mock(wraps=original_refresh)

    window.rows[item.id].remove_button.emit("clicked")

    assert window.refresh.call_count == 1
    assert window.rows == {}


def test_clear_all_avoids_duplicate_refresh_when_change_callback_already_synced() -> None:
    item = make_text_item("clear once")
    controller = _Controller((item,))
    window = PocketWindow(controller)
    controller.on_changed = lambda: window.refresh()
    original_refresh = window.refresh
    window.refresh = Mock(wraps=original_refresh)

    window.clear_button.emit("clicked")
    dialog = window.clear_dialog
    assert dialog is not None
    dialog.respond(True)

    assert window.refresh.call_count == 1
    assert window.rows == {}


def test_hover_setting_shows_the_stored_delay() -> None:
    assert PocketWindow(_Controller(), hover_delay_ms=3000).hover_delay_dropdown.get_selected() == 3
    assert PocketWindow(_Controller(), hover_delay_ms=0).hover_delay_dropdown.get_selected() == 0
    assert PocketWindow(_Controller(), hover_delay_ms=2500).hover_delay_dropdown.get_selected() == 2


def test_choosing_a_hover_delay_reports_milliseconds() -> None:
    changes: list[int] = []
    window = PocketWindow(_Controller(), on_hover_delay_changed=changes.append)
    assert changes == []

    window.hover_delay_dropdown.set_selected(0)
    window.hover_delay_dropdown.set_selected(1)

    assert changes == [0, 1500]
