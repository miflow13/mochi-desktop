"""Pocket tray placement, rows, actions, and lifecycle under Xvfb."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, GObject, Gtk  # noqa: E402

from mochi.pocket import (  # noqa: E402
    make_local_file_item,
    make_saved_image_item,
    make_text_item,
    make_url_item,
)
from mochi.pocket_tray import (  # noqa: E402
    LAUNCH_FAILED_TEXT,
    PocketTray,
    clipboard_content_for,
    drag_content_for,
    peek_fill_fraction,
    tray_position_for_anchor,
    tray_row_model,
)
from mochi.x11 import request_no_focus_on_map  # noqa: E402


def _monitor(x: int, y: int, width: int = 1920, height: int = 1080):
    return SimpleNamespace(x=x, y=y, width=width, height=height)


def _tiny_texture(_path: str) -> Gdk.Texture:
    return Gdk.MemoryTexture.new(
        1, 1, Gdk.MemoryFormat.R8G8B8A8, GLib.Bytes.new(bytes(4)), 4
    )


def _mime_types(formats: Gdk.ContentFormats) -> list[str]:
    return list(formats.union_serialize_mime_types().get_mime_types())


class _Dwell:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def tray_entered(self) -> None:
        self.calls.append("tray-entered")

    def tray_left(self) -> None:
        self.calls.append("tray-left")

    def drag_started(self) -> None:
        self.calls.append("drag-started")

    def drag_finished(self, delivered: bool) -> None:
        self.calls.append(f"drag-finished:{delivered}")

    def close(self) -> None:
        self.calls.append("close")


class _Clipboard:
    def __init__(self) -> None:
        self.contents: list[Gdk.ContentProvider] = []

    def set_content(self, provider: Gdk.ContentProvider) -> bool:
        self.contents.append(provider)
        return True


@pytest.fixture
def make_tray(monkeypatch):
    created: list[PocketTray] = []
    no_focus_calls: list[Gtk.Window] = []
    monkeypatch.setattr(
        "mochi.pocket_tray.request_no_focus_on_map",
        lambda window: no_focus_calls.append(window) or True,
    )

    def build(items=(), **overrides):
        dwell = _Dwell()
        launched: list[str] = []
        feedback: list[str] = []
        clipboard = _Clipboard()
        kwargs = dict(
            owner=Gtk.Window(),
            controller=SimpleNamespace(items=tuple(items)),
            dwell=dwell,
            on_manage=Mock(),
            show_feedback=feedback.append,
            launcher=launched.append,
            clipboard=clipboard,
            load_texture=_tiny_texture,
        )
        kwargs.update(overrides)
        tray = PocketTray(**kwargs)
        created.append(tray)
        return SimpleNamespace(
            tray=tray,
            dwell=dwell,
            launched=launched,
            feedback=feedback,
            clipboard=clipboard,
            no_focus_calls=no_focus_calls,
            on_manage=kwargs["on_manage"],
        )

    yield build
    for tray in created:
        owner = tray._owner
        tray.destroy()
        owner.destroy()


def _file(tmp_path: Path, name: str = "invoice-september.pdf"):
    path = tmp_path / name
    path.write_bytes(b"data")
    return path, make_local_file_item(path)


# Placement -----------------------------------------------------------------


def test_tray_sits_centred_above_mochi() -> None:
    assert tray_position_for_anchor(
        900, 900, 112, 112, 360, 300, [_monitor(0, 0)]
    ) == (776, 592)


def test_tray_flips_below_mochi_near_the_top_edge() -> None:
    assert tray_position_for_anchor(
        900, 50, 112, 112, 360, 300, [_monitor(0, 0)]
    ) == (776, 170)


def test_tray_is_clamped_inside_the_monitor() -> None:
    left = tray_position_for_anchor(0, 900, 112, 112, 360, 300, [_monitor(0, 0)])
    right = tray_position_for_anchor(1880, 900, 112, 112, 360, 300, [_monitor(0, 0)])

    assert left == (12, 592)
    assert right == (1548, 592)


def test_tray_uses_device_pixels_on_scaled_displays() -> None:
    assert tray_position_for_anchor(
        1800, 1800, 224, 224, 360, 300, [_monitor(0, 0)], coordinate_scale=2.0
    ) == (1552, 1184)


def test_tray_stays_on_mochis_monitor() -> None:
    monitors = [_monitor(0, 0), _monitor(1920, 0)]

    assert tray_position_for_anchor(
        2000, 900, 112, 112, 360, 300, monitors
    ) == (1932, 592)


def test_peek_fill_is_clamped_progress() -> None:
    assert peek_fill_fraction(0, 1400) == 0.0
    assert peek_fill_fraction(700, 1400) == pytest.approx(0.5)
    assert peek_fill_fraction(5000, 1400) == 1.0
    assert peek_fill_fraction(10, 0) == 1.0


# Rows and providers ---------------------------------------------------------


def test_row_models_name_the_action_for_each_kind(tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    image_path = tmp_path / "drop.png"
    image_path.write_bytes(b"png")

    file_row = tray_row_model(document)
    url_row = tray_row_model(make_url_item("https://example.org/"))
    text_row = tray_row_model(make_text_item("Ask Sam about the venue deposit"))
    image_row = tray_row_model(make_saved_image_item(image_path))

    assert (file_row.primary_label, file_row.quick_label) == ("Open", "Show in folder")
    assert (url_row.primary_label, url_row.quick_label) == ("Open", "Copy link")
    assert (text_row.primary_label, text_row.quick_label) == ("Copy", "View all")
    assert (image_row.primary_label, image_row.quick_label) == ("Open", "Copy image")
    assert all(
        row.available for row in (file_row, url_row, text_row, image_row)
    )


def test_missing_file_row_is_unavailable(tmp_path: Path) -> None:
    path, document = _file(tmp_path)
    path.unlink()

    assert tray_row_model(document).available is False
    assert drag_content_for(document) is None


def test_drag_offers_files_urls_and_text_in_native_formats(tmp_path: Path) -> None:
    _path, document = _file(tmp_path)

    file_formats = drag_content_for(document).ref_formats()
    url_formats = drag_content_for(make_url_item("https://example.org/")).ref_formats()
    text_formats = drag_content_for(make_text_item("hello")).ref_formats()

    assert file_formats.contain_gtype(Gdk.FileList)
    assert url_formats.contain_mime_type("text/uri-list")
    assert url_formats.contain_gtype(GObject.TYPE_STRING)
    assert text_formats.contain_gtype(GObject.TYPE_STRING)
    # What another application can actually receive:
    assert "text/uri-list" in _mime_types(file_formats)
    assert "text/plain;charset=utf-8" in _mime_types(text_formats)


def test_clipboard_copies_text_links_and_images_but_not_files(tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    image_path = tmp_path / "drop.png"
    image_path.write_bytes(b"png")

    text = clipboard_content_for(make_text_item("hello"))
    link = clipboard_content_for(make_url_item("https://example.org/"))
    image = clipboard_content_for(
        make_saved_image_item(image_path), load_texture=_tiny_texture
    )

    assert text.ref_formats().contain_gtype(GObject.TYPE_STRING)
    assert link.ref_formats().contain_gtype(GObject.TYPE_STRING)
    assert image.ref_formats().contain_gtype(Gdk.Texture)
    # A bare GdkMemoryTexture value has no serializers; other apps could not paste it.
    assert "image/png" in _mime_types(image.ref_formats())
    with pytest.raises(ValueError):
        clipboard_content_for(document)


# Views --------------------------------------------------------------------


def test_peek_maps_without_focus_and_shows_the_count(make_tray) -> None:
    built = make_tray()

    built.tray.show_peek(3, 1400)

    assert built.tray.view == "peek"
    assert built.tray.peek_label.get_text() == "Pocket · 3"
    assert built.no_focus_calls == [built.tray.window]
    assert built.tray.window.get_visible()

    built.tray.hide_peek()
    assert built.tray.view is None
    assert not built.tray.window.get_visible()
    assert built.tray._fill_tick_id is None


def test_hover_open_lists_items_newest_first_without_focus(make_tray, tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    items = (make_text_item("newest"), make_url_item("https://example.org/"), document)
    built = make_tray(items)

    built.tray.open(focus=False)

    assert built.tray.view == "tray"
    assert built.tray.count_label.get_text() == "3 of 10"
    assert [
        built.tray._list.get_row_at_index(index) for index in range(3)
    ] == [built.tray.rows[item.id].row for item in items]
    assert built.no_focus_calls == [built.tray.window]
    assert not built.tray.empty_label.get_visible()


def test_menu_open_presents_normally_and_shows_the_empty_state(make_tray) -> None:
    built = make_tray(())

    built.tray.open(focus=True)

    assert built.no_focus_calls == []
    assert built.tray.empty_label.get_visible()
    assert built.tray.count_label.get_text() == "0 of 10"


def test_refresh_only_rebuilds_an_open_tray(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.refresh()
    assert built.tray.rows == {}

    built.tray.open(focus=False)
    built.tray._controller = SimpleNamespace(
        items=(make_text_item("two"), make_text_item("one"))
    )
    built.tray.refresh()
    assert len(built.tray.rows) == 2


# Actions ------------------------------------------------------------------


def test_primary_opens_files_and_links_then_closes(make_tray, tmp_path: Path) -> None:
    path, document = _file(tmp_path)
    link = make_url_item("https://example.org/")
    built = make_tray((document, link))
    built.tray.open(focus=False)

    assert built.tray.activate_primary(document.id) is True
    assert built.tray.activate_primary(link.id) is True

    assert built.launched == [path.as_uri(), link.value]
    assert built.dwell.calls == ["close", "close"]


def test_primary_copies_text_and_says_so(make_tray) -> None:
    note = make_text_item("Ask Sam about the venue deposit")
    built = make_tray((note,))
    built.tray.open(focus=False)

    assert built.tray.activate_primary(note.id) is True

    assert len(built.clipboard.contents) == 1
    assert built.feedback == ["Copied"]
    assert built.dwell.calls == ["close"]
    assert built.launched == []


def test_launch_failure_keeps_the_tray_and_the_item(make_tray, tmp_path: Path) -> None:
    _path, document = _file(tmp_path)

    def failing(_uri: str) -> None:
        raise OSError("no handler")

    built = make_tray((document,), launcher=failing)
    built.tray.open(focus=False)

    assert built.tray.activate_primary(document.id) is False

    status = built.tray.rows[document.id].status
    assert status.get_visible()
    assert status.get_text() == LAUNCH_FAILED_TEXT
    assert built.dwell.calls == []


def test_quick_actions_stay_open_and_confirm_in_place(make_tray, tmp_path: Path) -> None:
    _path, document = _file(tmp_path)
    link = make_url_item("https://example.org/")
    built = make_tray((document, link))
    built.tray.open(focus=False)

    assert built.tray.activate_quick(document.id) is True
    assert built.tray.activate_quick(link.id) is True

    assert built.launched == [tmp_path.as_uri()]
    assert len(built.clipboard.contents) == 1
    assert built.tray.rows[link.id].status.get_text() == "Copied"
    assert link.id in built.tray._feedback_sources
    assert built.dwell.calls == []

    built.tray.close()
    assert built.tray._feedback_sources == {}


def test_view_all_opens_the_read_only_text_window(make_tray) -> None:
    note = make_text_item("line one\nline two")
    built = make_tray((note,))
    built.tray.open(focus=False)

    assert built.tray.activate_quick(note.id) is True

    assert len(built.tray.detail_windows) == 1


def test_unreadable_image_copy_shows_the_row_error(make_tray, tmp_path: Path) -> None:
    image_path = tmp_path / "drop.png"
    image_path.write_bytes(b"not really a png")
    image = make_saved_image_item(image_path)

    def failing(_path: str):
        raise OSError("cannot decode")

    built = make_tray((image,), load_texture=failing)
    built.tray.open(focus=False)

    assert built.tray.activate_quick(image.id) is False
    assert built.tray.rows[image.id].status.get_text() == LAUNCH_FAILED_TEXT


def test_missing_rows_cannot_be_grabbed(make_tray, tmp_path: Path) -> None:
    path, document = _file(tmp_path)
    path.unlink()
    built = make_tray((document,))
    built.tray.open(focus=False)

    widgets = built.tray.rows[document.id]
    assert widgets.row.get_activatable() is False
    assert widgets.quick_button is None
    assert widgets.drag_source is None
    assert built.tray.activate_primary(document.id) is False
    assert built.launched == []


def test_manage_hands_off_to_the_pocket_window(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.open(focus=False)

    built.tray.manage_button.emit("clicked")

    built.on_manage.assert_called_once_with()


# Closing, focus, and drag ---------------------------------------------------


def test_escape_closes_through_the_dwell(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.open(focus=False)

    assert built.tray._on_key_pressed(None, Gdk.KEY_a, 0, Gdk.ModifierType(0)) is False
    assert built.tray._on_key_pressed(
        None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0)
    ) is True
    assert built.dwell.calls == ["close"]


def test_focus_loss_after_activation_closes_unless_dragging(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.open(focus=False)
    inactive = SimpleNamespace(is_active=lambda: False, get_visible=lambda: True)

    built.tray._was_active = True
    built.tray._dragging = True
    built.tray._on_active_changed(inactive, None)
    assert built.dwell.calls == []

    built.tray._dragging = False
    built.tray._on_active_changed(inactive, None)
    assert built.dwell.calls == ["close"]


def test_drag_reports_delivery_to_the_dwell(make_tray) -> None:
    note = make_text_item("one")
    built = make_tray((note,))
    built.tray.open(focus=False)
    source = SimpleNamespace(set_icon=Mock())
    row = built.tray.rows[note.id].row

    built.tray._on_drag_begin(source, row)
    built.tray._on_drag_end(source, None, False)
    built.tray._on_drag_begin(source, row)
    assert built.tray._on_drag_cancel(source, None, None) is False
    built.tray._on_drag_end(source, None, False)

    assert built.dwell.calls == [
        "drag-started",
        "drag-finished:True",
        "drag-started",
        "drag-finished:False",
    ]


def test_destroy_releases_detail_windows_and_sources(make_tray) -> None:
    note = make_text_item("one")
    built = make_tray((note,))
    built.tray.show_peek(1, 1400)
    built.tray.open(focus=False)
    built.tray.activate_quick(note.id)
    detail = built.tray.detail_windows[0]

    built.tray.destroy()

    # gtk_window_destroy() removes the window from the toplevel list at once;
    # the "destroy" signal itself waits for the last reference to drop.
    assert detail not in list(Gtk.Window.get_toplevels())
    assert built.tray.detail_windows == []
    assert built.tray._position_sources == set()
    assert built.tray._fill_tick_id is None


def test_no_focus_request_needs_an_x11_surface() -> None:
    assert request_no_focus_on_map(SimpleNamespace(get_surface=lambda: None)) is False

    window = Gtk.Window()
    window.realize()
    try:
        assert request_no_focus_on_map(window) is True
    finally:
        window.destroy()


# Placing without catching the pointer -----------------------------------------
# Mutter centres a newly mapped transient window over its parent, and a resize
# grows the window before it can be moved. While the tray is being placed it is
# pointer-transparent and invisible, so a resting pointer stays on Mochi.


@pytest.fixture
def transparency(monkeypatch):
    calls: list[bool] = []

    def spy(tray):
        monkeypatch.setattr(tray, "_set_pointer_transparent", calls.append)
        return calls

    return spy


def test_peek_is_placed_before_it_can_catch_the_pointer(make_tray, transparency) -> None:
    built = make_tray((make_text_item("one"),))
    calls = transparency(built.tray)

    built.tray.show_peek(1, 1400)

    assert calls == [True]
    assert built.tray._settling is True
    assert built.tray._settle_source is not None


def test_settling_ends_once_the_window_has_its_natural_size(make_tray, transparency, monkeypatch) -> None:
    built = make_tray((make_text_item("one"),))
    calls = transparency(built.tray)
    built.tray.show_peek(1, 1400)
    monkeypatch.setattr(built.tray, "_natural_size", lambda: (176, 45))

    built.tray._maybe_finish_settle(150, 30)
    assert built.tray._settling is True

    built.tray._maybe_finish_settle(176, 45)
    assert built.tray._settling is False
    assert calls == [True, False]
    assert built.tray._settle_source is None


def test_settling_has_a_fallback_so_the_tray_never_stays_hidden(make_tray, transparency) -> None:
    built = make_tray((make_text_item("one"),))
    calls = transparency(built.tray)
    built.tray.show_peek(1, 1400)

    assert built.tray._on_settle_timeout() is GLib.SOURCE_REMOVE

    assert built.tray._settling is False
    assert calls == [True, False]


def test_growing_from_peek_to_tray_settles_again(make_tray, transparency) -> None:
    built = make_tray((make_text_item("one"),))
    calls = transparency(built.tray)
    built.tray.show_peek(1, 1400)
    built.tray._finish_settle()

    built.tray.open(focus=False)

    assert calls == [True, False, True]
    assert built.tray._settling is True


def test_closing_mid_settle_restores_the_pointer_and_drops_the_timer(make_tray, transparency) -> None:
    built = make_tray((make_text_item("one"),))
    calls = transparency(built.tray)
    built.tray.show_peek(1, 1400)

    built.tray.close()

    assert calls == [True, False]
    assert built.tray._settling is False
    assert built.tray._settle_source is None


def test_size_changes_reposition_the_tray(make_tray) -> None:
    built = make_tray((make_text_item("one"),))
    built.tray.show_peek(1, 1400)

    assert built.tray._layout_handler is not None


def test_real_pointer_transparency_toggles_input_and_opacity(make_tray) -> None:
    built = make_tray((make_text_item("one"),))

    built.tray._set_pointer_transparent(True)
    assert built.tray.window.get_opacity() == 0.0
    built.tray._set_pointer_transparent(False)
    assert built.tray.window.get_opacity() == 1.0
