"""Hover and menu tray for taking things back out of Mochi's Pocket."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from mochi.menu_window import _distance_to_geometry, _window_coordinate_scale
from mochi.pocket import (
    DEFAULT_CAPACITY,
    PocketItem,
    PocketItemKind,
    item_is_available,
)
from mochi.pocket_actions import folder_uri_for, launch_uri_for
from mochi.pocket_hover import PocketHoverDwell
from mochi.pocket_window import PocketTextWindow, _launch_default, row_model
from mochi.x11 import (
    get_window_position,
    move_window,
    request_keep_above,
    request_no_focus_on_map,
)

TRAY_WIDTH = 360
TRAY_GAP_PX = 8
TRAY_MAX_LIST_HEIGHT = 480
TRAY_FEEDBACK_MS = 1500
PEEK_WIDTH = 150
TRAY_SETTLE_FALLBACK_MS = 300
EMPTY_TRAY_TEXT = "Nothing in here yet. Drag a file, link, image, or text onto Mochi."
LAUNCH_FAILED_TEXT = "Couldn't open it. It's still here."

POCKET_TRAY_CSS = """
window.mochi-pocket-tray {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}
.mochi-tray-peek { padding: 8px 12px 10px; }
.mochi-tray-card { padding: 6px; }
.mochi-tray-header { padding: 6px 8px 4px; }
.mochi-tray-title { font-weight: 700; }
.mochi-tray-dim { color: alpha(@theme_fg_color, 0.68); font-size: smaller; }
.mochi-tray-empty { padding: 12px 8px; }
list.mochi-tray-list { background: none; }
row.mochi-tray-row { border-radius: 10px; padding: 4px 4px 4px 8px; min-height: 48px; }
row.mochi-tray-row .mochi-tray-verb { opacity: 0; }
row.mochi-tray-row:hover .mochi-tray-verb,
row.mochi-tray-row:focus-within .mochi-tray-verb { opacity: 1; }
.mochi-tray-verb {
    background-color: #79c98b;
    color: #102417;
    border-radius: 999px;
    padding: 2px 9px;
    font-weight: 700;
    font-size: smaller;
}
.mochi-tray-chip {
    min-width: 36px;
    min-height: 36px;
    border-radius: 9px;
    background-color: alpha(#79c98b, 0.18);
}
row.mochi-tray-missing { opacity: 0.6; }
button.mochi-tray-quick { min-width: 44px; min-height: 44px; }
.mochi-tray-error { color: #c01c28; }
/* Shorthand: the theme paints progress with a background-image that would
   cover a background-color alone. */
progressbar.mochi-tray-fill > trough > progress { background: #79c98b; }
"""

# While being placed the tray takes no pointer input; afterwards it takes all
# of it. X clips the "everything" region to the window, whatever its size.
_NO_INPUT = cairo.Region()
_ALL_INPUT = cairo.Region(cairo.RectangleInt(0, 0, 32767, 32767))

# Primary verb, quick-action label, quick-action icon.
_ROW_ACTIONS = {
    PocketItemKind.LOCAL_FILE: ("Open", "Show in folder", "folder-open-symbolic"),
    PocketItemKind.URL: ("Open", "Copy link", "edit-copy-symbolic"),
    PocketItemKind.TEXT: ("Copy", "View all", "view-reveal-symbolic"),
    PocketItemKind.SAVED_IMAGE: ("Open", "Copy image", "edit-copy-symbolic"),
}


def tray_position_for_anchor(
    owner_x: int,
    owner_y: int,
    owner_width: int,
    owner_height: int,
    tray_width: int,
    tray_height: int,
    geometries: list,
    *,
    gap: int = TRAY_GAP_PX,
    padding: int = 12,
    coordinate_scale: float = 1.0,
) -> tuple[int, int]:
    """Centre the tray above Mochi, or below him when there is no room above.

    ``owner_*`` and the returned coordinates are X11 device pixels. Tray sizes,
    monitor geometries, gap, and padding are GTK application pixels, matching
    ``menu_position_for_anchor``.
    """
    scale = coordinate_scale if coordinate_scale > 0 else 1.0
    width = max(1, round(tray_width * scale))
    height = max(1, round(tray_height * scale))
    device_gap = round(gap * scale)
    x = owner_x + owner_width // 2 - width // 2
    above = owner_y - device_gap - height
    below = owner_y + owner_height + device_gap
    if not geometries:
        return (x, above if above >= 0 else below)

    centre_x = (owner_x + owner_width / 2) / scale
    centre_y = (owner_y + owner_height / 2) / scale
    monitor = min(
        geometries,
        key=lambda geometry: _distance_to_geometry(centre_x, centre_y, geometry),
    )
    left = round((monitor.x + padding) * scale)
    top = round((monitor.y + padding) * scale)
    right = round((monitor.x + monitor.width - padding) * scale)
    bottom = round((monitor.y + monitor.height - padding) * scale)

    y = above if above >= top else below
    x = max(left, min(x, max(left, right - width)))
    y = max(top, min(y, max(top, bottom - height)))
    return (x, y)


def peek_fill_fraction(elapsed_ms: float, fill_ms: int) -> float:
    """Return the peek bar's progress, clamped to 0..1."""
    if fill_ms <= 0:
        return 1.0
    return max(0.0, min(1.0, elapsed_ms / fill_ms))


@dataclass(frozen=True)
class TrayRowModel:
    item_id: str
    title: str
    subtitle: str
    icon_name: str
    available: bool
    primary_label: str
    quick_label: str
    quick_icon: str


@dataclass
class TrayRowWidgets:
    model: TrayRowModel
    row: Gtk.ListBoxRow
    status: Gtk.Label
    quick_button: Gtk.Button | None
    drag_source: Gtk.DragSource | None


def tray_row_model(item: PocketItem) -> TrayRowModel:
    """Describe a tray row; titles and subtitles match the Pocket window."""
    base = row_model(item)
    primary, quick, quick_icon = _ROW_ACTIONS[item.kind]
    return TrayRowModel(
        item_id=item.id,
        title=base.title,
        subtitle=base.subtitle,
        icon_name=base.icon_name,
        available=base.available,
        primary_label=primary,
        quick_label=quick,
        quick_icon=quick_icon,
    )


def drag_content_for(item: PocketItem) -> Gdk.ContentProvider | None:
    """Return what dragging this item out offers, or None for a missing file."""
    if not item_is_available(item):
        return None
    if item.kind in (PocketItemKind.LOCAL_FILE, PocketItemKind.SAVED_IMAGE):
        files = Gdk.FileList.new_from_list([Gio.File.new_for_path(item.value)])
        return Gdk.ContentProvider.new_for_value(GObject.Value(Gdk.FileList, files))
    if item.kind is PocketItemKind.URL:
        uri_list = GLib.Bytes.new(f"{item.value}\r\n".encode("utf-8"))
        return Gdk.ContentProvider.new_union(
            [
                Gdk.ContentProvider.new_for_bytes("text/uri-list", uri_list),
                Gdk.ContentProvider.new_for_value(item.value),
            ]
        )
    return Gdk.ContentProvider.new_for_value(item.value)


def clipboard_content_for(
    item: PocketItem,
    *,
    load_texture: Callable[[str], Gdk.Texture] = Gdk.Texture.new_from_filename,
) -> Gdk.ContentProvider:
    """Return what Copy puts on the clipboard. Local files are opened, not copied."""
    if item.kind in (PocketItemKind.TEXT, PocketItemKind.URL):
        return Gdk.ContentProvider.new_for_value(item.value)
    if item.kind is PocketItemKind.SAVED_IMAGE:
        # Type the value as Gdk.Texture: GTK finds clipboard serializers by
        # exact type, and a bare GdkMemoryTexture would offer nothing to paste.
        texture = GObject.Value(Gdk.Texture, load_texture(item.value))
        return Gdk.ContentProvider.new_for_value(texture)
    raise ValueError("Local Pocket files are opened or dragged, not copied")


class PocketTray:
    """One small window: a filling peek bar that becomes the Pocket tray.

    The dwell decides when it opens and closes. The tray owns every source it
    creates (positioning, settling, fill tick, inline feedback), its surface
    layout handler, and the text windows it opened, and releases them in
    close() and destroy().
    """

    def __init__(
        self,
        *,
        owner: Gtk.Window,
        controller,
        dwell: PocketHoverDwell,
        on_manage: Callable[[], None],
        show_feedback: Callable[[str], None],
        launcher: Callable[[str], None] = _launch_default,
        clipboard: Gdk.Clipboard | None = None,
        load_texture: Callable[[str], Gdk.Texture] = Gdk.Texture.new_from_filename,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._controller = controller
        self._dwell = dwell
        self._on_manage = on_manage
        self._show_feedback = show_feedback
        self._launcher = launcher
        self._clipboard = clipboard
        self._load_texture = load_texture
        self._logger = logger or logging.getLogger(__name__)
        self.view: str | None = None
        self.rows: dict[str, TrayRowWidgets] = {}
        self.detail_windows: list[PocketTextWindow] = []
        self._was_active = False
        self._dragging = False
        self._drag_cancelled = False
        self._fill_ms = 0
        self._fill_started_us: int | None = None
        self._fill_tick_id: int | None = None
        self._feedback_sources: dict[str, int] = {}
        self._position_sources: set[int] = set()
        self._settling = False
        self._settle_source: int | None = None
        self._layout_handler: int | None = None

        self.window = Gtk.Window()
        self.window.set_title("Mochi's Pocket")
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_modal(False)
        self.window.set_hide_on_close(True)
        self.window.set_transient_for(owner)
        self.window.add_css_class("mochi-pocket-tray")
        self.window.connect("map", self._on_map)
        self.window.connect("close-request", self._on_close_request)
        self.window.connect("notify::is-active", self._on_active_changed)
        self._install_css()

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(keys)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", lambda *_args: self._dwell.tray_entered())
        motion.connect("leave", lambda *_args: self._dwell.tray_left())
        self.window.add_controller(motion)

        self._stack = Gtk.Stack()
        self._stack.set_hhomogeneous(False)
        self._stack.set_vhomogeneous(False)
        self._stack.set_interpolate_size(False)
        self._stack.add_named(self._build_peek(), "peek")
        self._stack.add_named(self._build_tray(), "tray")
        self.window.set_child(self._stack)

    # Public surface ---------------------------------------------------------

    def show_peek(self, count: int, fill_ms: int) -> None:
        self.peek_label.set_text(f"Pocket · {count}")
        self.peek_bar.set_fraction(0.0)
        self._fill_ms = max(0, int(fill_ms))
        self._fill_started_us = None
        self._stack.set_visible_child_name("peek")
        self.view = "peek"
        self._present(focus=False)
        self._start_fill()

    def hide_peek(self) -> None:
        if self.view == "peek":
            self._hide()

    def open(self, *, focus: bool) -> None:
        self._stop_fill()
        if self.window.get_visible():
            # Growing from the small peek happens before the window can move.
            self._begin_settle()
        self.refresh(force=True)
        self._stack.set_visible_child_name("tray")
        self.view = "tray"
        self._was_active = False
        self._present(focus=focus)
        if focus:
            first = self._list.get_row_at_index(0)
            (first or self.manage_button).grab_focus()

    def refresh(self, *, force: bool = False) -> None:
        if self.view != "tray" and not force:
            return
        self._cancel_all_feedback()
        self._list.remove_all()
        self.rows.clear()
        items = tuple(self._controller.items)
        for item in items:
            widgets = self._make_row(item)
            self.rows[item.id] = widgets
            self._list.append(widgets.row)
        self.count_label.set_text(f"{len(items)} of {DEFAULT_CAPACITY}")
        self.empty_label.set_visible(not items)
        self._scroll.set_visible(bool(items))
        if self.window.get_visible():
            self._schedule_position()

    def close(self) -> None:
        """Hide the tray. The dwell owns open/closed state and calls this."""
        self._hide()

    def destroy(self) -> None:
        self._hide()
        surface = self.window.get_surface()
        if surface is not None and self._layout_handler is not None:
            surface.disconnect(self._layout_handler)
        self._layout_handler = None
        details = tuple(self.detail_windows)
        self.detail_windows.clear()
        for detail in details:
            detail.destroy()
        self.window.destroy()

    def activate_primary(self, item_id: str) -> bool:
        item = self._item(item_id)
        if item is None or not item_is_available(item):
            return False
        try:
            if item.kind is PocketItemKind.TEXT:
                self._copy(item)
            else:
                self._launcher(launch_uri_for(item))
        except (GLib.Error, OSError, ValueError) as error:
            self._logger.warning("Pocket tray action failed: %s", error)
            self._show_row_status(item_id, LAUNCH_FAILED_TEXT, error=True)
            return False
        if item.kind is PocketItemKind.TEXT:
            self._show_feedback("Copied")
        self._dwell.close()
        return True

    def activate_quick(self, item_id: str) -> bool:
        item = self._item(item_id)
        if item is None or not item_is_available(item):
            return False
        try:
            if item.kind is PocketItemKind.LOCAL_FILE:
                self._launcher(folder_uri_for(item))
            elif item.kind is PocketItemKind.TEXT:
                self._open_text_detail(item)
            else:
                self._copy(item)
                self._show_row_status(
                    item_id, "Copied", error=False, timeout_ms=TRAY_FEEDBACK_MS
                )
        except (GLib.Error, OSError, ValueError) as error:
            self._logger.warning("Pocket tray quick action failed: %s", error)
            self._show_row_status(item_id, LAUNCH_FAILED_TEXT, error=True)
            return False
        return True

    # Construction -----------------------------------------------------------

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(POCKET_TRAY_CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.window.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_peek(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("mochi-tray-peek")
        box.set_size_request(PEEK_WIDTH, -1)
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        line.append(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
        self.peek_label = Gtk.Label(label="Pocket")
        self.peek_label.add_css_class("mochi-tray-title")
        line.append(self.peek_label)
        box.append(line)
        self.peek_bar = Gtk.ProgressBar()
        self.peek_bar.add_css_class("mochi-tray-fill")
        box.append(self.peek_bar)
        return box

    def _build_tray(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("mochi-tray-card")
        card.set_size_request(TRAY_WIDTH, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("mochi-tray-header")
        title = Gtk.Label(label="Pocket")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("mochi-tray-title")
        header.append(title)
        self.count_label = Gtk.Label()
        self.count_label.add_css_class("mochi-tray-dim")
        header.append(self.count_label)
        card.append(header)

        self.empty_label = Gtk.Label(label=EMPTY_TRAY_TEXT)
        self.empty_label.set_wrap(True)
        self.empty_label.set_max_width_chars(36)
        self.empty_label.add_css_class("mochi-tray-dim")
        self.empty_label.add_css_class("mochi-tray-empty")
        card.append(self.empty_label)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.set_activate_on_single_click(True)
        self._list.add_css_class("mochi-tray-list")
        self._list.update_property([Gtk.AccessibleProperty.LABEL], ["Pocket items"])
        self._list.connect("row-activated", self._on_row_activated)
        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroll.set_propagate_natural_height(True)
        self._scroll.set_max_content_height(TRAY_MAX_LIST_HEIGHT)
        self._scroll.set_child(self._list)
        card.append(self._scroll)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.manage_button = Gtk.Button(label="Manage Pocket…")
        self.manage_button.add_css_class("flat")
        self.manage_button.connect("clicked", lambda _button: self._on_manage())
        footer.append(self.manage_button)
        hint = Gtk.Label(label="Click to open, or drag it out")
        hint.set_xalign(1)
        hint.set_hexpand(True)
        hint.add_css_class("mochi-tray-dim")
        footer.append(hint)
        card.append(footer)
        return card

    def _make_row(self, item: PocketItem) -> TrayRowWidgets:
        model = tray_row_model(item)
        row = Gtk.ListBoxRow()
        row.add_css_class("mochi-tray-row")
        row.set_activatable(model.available)
        if model.available:
            accessible = f"{model.primary_label} {model.title}"
        else:
            row.add_css_class("mochi-tray-missing")
            accessible = f"{model.title}, moved or deleted"
        row.update_property([Gtk.AccessibleProperty.LABEL], [accessible])

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        chip = Gtk.Image.new_from_icon_name(model.icon_name)
        chip.add_css_class("mochi-tray-chip")
        content.append(chip)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label=model.title)
        title.set_xalign(0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.add_css_class("mochi-tray-title")
        labels.append(title)
        subtitle = Gtk.Label(label=model.subtitle)
        subtitle.set_xalign(0)
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.add_css_class("mochi-tray-dim")
        labels.append(subtitle)
        status = Gtk.Label()
        status.set_xalign(0)
        status.set_visible(False)
        labels.append(status)
        content.append(labels)

        quick_button: Gtk.Button | None = None
        drag_source: Gtk.DragSource | None = None
        if model.available:
            verb = Gtk.Label(label=model.primary_label)
            verb.set_valign(Gtk.Align.CENTER)
            verb.add_css_class("mochi-tray-verb")
            content.append(verb)

            quick_button = Gtk.Button.new_from_icon_name(model.quick_icon)
            quick_button.add_css_class("flat")
            quick_button.add_css_class("mochi-tray-quick")
            quick_button.set_valign(Gtk.Align.CENTER)
            quick_button.set_tooltip_text(model.quick_label)
            quick_button.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [f"{model.quick_label}: {model.title}"],
            )
            quick_button.connect(
                "clicked",
                lambda _button, item_id=item.id: self.activate_quick(item_id),
            )
            content.append(quick_button)

            drag_source = Gtk.DragSource()
            drag_source.set_actions(Gdk.DragAction.COPY)
            drag_source.connect(
                "prepare",
                lambda _source, _x, _y, item_id=item.id: self._prepare_drag(item_id),
            )
            drag_source.connect(
                "drag-begin",
                lambda source, _drag, row=row: self._on_drag_begin(source, row),
            )
            drag_source.connect("drag-cancel", self._on_drag_cancel)
            drag_source.connect("drag-end", self._on_drag_end)
            row.add_controller(drag_source)

        row.set_child(content)
        return TrayRowWidgets(model, row, status, quick_button, drag_source)

    # Actions ----------------------------------------------------------------

    def _item(self, item_id: str) -> PocketItem | None:
        return next(
            (item for item in self._controller.items if item.id == item_id),
            None,
        )

    def _copy(self, item: PocketItem) -> None:
        clipboard = self._clipboard or self.window.get_clipboard()
        clipboard.set_content(
            clipboard_content_for(item, load_texture=self._load_texture)
        )

    def _open_text_detail(self, item: PocketItem) -> None:
        detail = PocketTextWindow(
            item,
            parent=self._owner,
            on_close=self._on_detail_window_closed,
        )
        self.detail_windows.append(detail)
        detail.present()

    def _on_detail_window_closed(self, detail: PocketTextWindow) -> None:
        if detail in self.detail_windows:
            self.detail_windows.remove(detail)

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        item_id = next(
            (key for key, widgets in self.rows.items() if widgets.row is row),
            None,
        )
        if item_id is not None:
            self.activate_primary(item_id)

    def _show_row_status(
        self,
        item_id: str,
        message: str,
        *,
        error: bool,
        timeout_ms: int | None = None,
    ) -> None:
        widgets = self.rows.get(item_id)
        if widgets is None:
            return
        self._cancel_feedback(item_id)
        widgets.status.set_text(message)
        if error:
            widgets.status.add_css_class("mochi-tray-error")
        else:
            widgets.status.remove_css_class("mochi-tray-error")
        widgets.status.set_visible(True)
        if timeout_ms is not None:
            self._feedback_sources[item_id] = GLib.timeout_add(
                timeout_ms, self._clear_row_status, item_id
            )

    def _clear_row_status(self, item_id: str) -> bool:
        self._feedback_sources.pop(item_id, None)
        widgets = self.rows.get(item_id)
        if widgets is not None:
            widgets.status.set_visible(False)
            widgets.status.set_text("")
        return GLib.SOURCE_REMOVE

    def _cancel_feedback(self, item_id: str) -> None:
        source_id = self._feedback_sources.pop(item_id, None)
        if source_id is not None:
            GLib.source_remove(source_id)

    def _cancel_all_feedback(self) -> None:
        for item_id in tuple(self._feedback_sources):
            self._cancel_feedback(item_id)

    # Drag out ---------------------------------------------------------------

    def _prepare_drag(self, item_id: str) -> Gdk.ContentProvider | None:
        item = self._item(item_id)
        return drag_content_for(item) if item is not None else None

    def _on_drag_begin(self, source, row: Gtk.ListBoxRow) -> None:
        self._dragging = True
        self._drag_cancelled = False
        source.set_icon(Gtk.WidgetPaintable.new(row), 0, 0)
        self._dwell.drag_started()

    def _on_drag_cancel(self, _source, _drag, _reason) -> bool:
        self._drag_cancelled = True
        return False

    def _on_drag_end(self, _source, _drag, _delete_data) -> None:
        delivered = not self._drag_cancelled
        self._dragging = False
        self._drag_cancelled = False
        self._dwell.drag_finished(delivered)

    # Window lifecycle -------------------------------------------------------

    def _present(self, *, focus: bool) -> None:
        if not self.window.get_visible():
            self.window.realize()
            self._watch_surface_layout()
            self._begin_settle()
            if focus:
                self.window.present()
            else:
                request_no_focus_on_map(self.window)
                self.window.set_visible(True)
        elif focus:
            self.window.present()
        self._schedule_position()

    def _hide(self) -> None:
        self._stop_fill()
        self._finish_settle()
        self._cancel_position()
        self._cancel_all_feedback()
        self.view = None
        self._was_active = False
        if self.window.get_visible():
            self.window.set_visible(False)

    def _on_map(self, _window: Gtk.Window) -> None:
        request_keep_above(self.window)
        self._schedule_position()

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self._dwell.close()
        return True

    def _on_key_pressed(self, _controller, keyval: int, _keycode: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._dwell.close()
            return True
        return False

    def _on_active_changed(self, window, _pspec) -> None:
        if window.is_active():
            self._was_active = True
            return
        if self._was_active and not self._dragging and window.get_visible():
            self._dwell.close()

    # Placing ------------------------------------------------------------------
    # Mutter centres a newly mapped transient window over its parent, and a
    # resize grows the window before it can be moved. Either puts the tray under
    # a resting pointer for a moment, and the crossing events read as the user
    # leaving Mochi. Until the tray sits at its natural size in its final spot
    # it takes no pointer input and is not drawn.

    def _set_pointer_transparent(self, transparent: bool) -> None:
        self.window.realize()
        surface = self.window.get_surface()
        if surface is not None:
            surface.set_input_region(_NO_INPUT if transparent else _ALL_INPUT)
        self.window.set_opacity(0.0 if transparent else 1.0)

    def _begin_settle(self) -> None:
        self._cancel_settle_timer()
        self._settling = True
        self._set_pointer_transparent(True)
        self._settle_source = GLib.timeout_add(
            TRAY_SETTLE_FALLBACK_MS, self._on_settle_timeout
        )

    def _finish_settle(self) -> None:
        self._cancel_settle_timer()
        if not self._settling:
            return
        self._settling = False
        self._set_pointer_transparent(False)

    def _maybe_finish_settle(self, width: int, height: int) -> None:
        if not self._settling:
            return
        natural_width, natural_height = self._natural_size()
        if abs(width - natural_width) <= 1 and abs(height - natural_height) <= 1:
            self._finish_settle()

    def _on_settle_timeout(self) -> bool:
        # Never leave the tray hidden because a size never matched exactly.
        self._settle_source = None
        self._position_now()
        self._finish_settle()
        return GLib.SOURCE_REMOVE

    def _cancel_settle_timer(self) -> None:
        source_id = self._settle_source
        self._settle_source = None
        if source_id is not None:
            GLib.source_remove(source_id)

    def _natural_size(self) -> tuple[int, int]:
        _minimum, natural = self.window.get_preferred_size()
        return natural.width, natural.height

    def _watch_surface_layout(self) -> None:
        if self._layout_handler is not None:
            return
        surface = self.window.get_surface()
        if surface is not None:
            self._layout_handler = surface.connect("layout", self._on_surface_layout)

    def _on_surface_layout(self, _surface, width: int, height: int) -> None:
        if self.window.get_visible():
            self._position_now(width, height)

    def _start_fill(self) -> None:
        self._stop_fill()
        self._fill_tick_id = self.peek_bar.add_tick_callback(self._on_fill_tick)

    def _on_fill_tick(self, _widget, frame_clock) -> bool:
        now_us = frame_clock.get_frame_time()
        if self._fill_started_us is None:
            self._fill_started_us = now_us
        fraction = peek_fill_fraction(
            (now_us - self._fill_started_us) / 1000, self._fill_ms
        )
        self.peek_bar.set_fraction(fraction)
        if fraction >= 1.0:
            self._fill_tick_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _stop_fill(self) -> None:
        tick_id = self._fill_tick_id
        self._fill_tick_id = None
        if tick_id is not None:
            self.peek_bar.remove_tick_callback(tick_id)

    def _schedule_position(self) -> None:
        # Mapping and size allocation can settle after present(). Position on
        # the next loop turn and again shortly after, like MenuWindow.
        self._cancel_position()
        for delay_ms in (0, 24):
            self._add_position_source(delay_ms)

    def _add_position_source(self, delay_ms: int) -> None:
        cell: list[int] = []

        def fire() -> bool:
            if cell:
                self._position_sources.discard(cell[0])
            self._position_now()
            return GLib.SOURCE_REMOVE

        source_id = GLib.timeout_add(delay_ms, fire)
        cell.append(source_id)
        self._position_sources.add(source_id)

    def _cancel_position(self) -> None:
        for source_id in tuple(self._position_sources):
            GLib.source_remove(source_id)
        self._position_sources.clear()

    def _position_now(self, width: int | None = None, height: int | None = None) -> None:
        if not self.window.get_visible():
            return
        owner_position = get_window_position(self._owner)
        if owner_position is None:
            return
        scale = _window_coordinate_scale(self._owner)
        owner_x, owner_y = owner_position
        width = self.window.get_width() if width is None else width
        height = self.window.get_height() if height is None else height
        if width <= 1:
            width = TRAY_WIDTH if self.view == "tray" else PEEK_WIDTH
        if height <= 1:
            height = 48
        monitors = self._owner.get_display().get_monitors()
        geometries = [
            monitors.get_item(index).get_geometry()
            for index in range(monitors.get_n_items())
        ]
        x, y = tray_position_for_anchor(
            owner_x,
            owner_y,
            round(self._owner.get_width() * scale),
            round(self._owner.get_height() * scale),
            width,
            height,
            geometries,
            coordinate_scale=scale,
        )
        move_window(self.window, x, y)
        self._maybe_finish_settle(width, height)
