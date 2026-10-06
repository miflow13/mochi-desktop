"""Small GTK4 management surface for Mochi Pocket."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from mochi.pocket import PocketItem, PocketItemKind, item_is_available
from mochi.pocket_actions import folder_uri_for, launch_uri_for
from mochi.pocket_controller import PocketController


POCKET_WINDOW_CSS = """
window.mochi-pocket-window {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}
.mochi-pocket-card { padding: 18px; }
.mochi-pocket-title { font-size: 20px; font-weight: 700; }
.mochi-pocket-subtitle,
.mochi-pocket-row-subtitle { color: alpha(@theme_fg_color, 0.62); }
.mochi-pocket-error { color: #c01c28; }
button.mochi-pocket-primary {
    background-image: none;
    background-color: #79c98b;
    color: #102417;
}
"""


@dataclass(frozen=True)
class PocketRowModel:
    item_id: str
    title: str
    subtitle: str
    icon_name: str
    available: bool
    action_label: str


@dataclass
class PocketRowWidgets:
    model: PocketRowModel
    container: Gtk.Widget
    open_button: Gtk.Button
    folder_button: Gtk.Button | None
    remove_button: Gtk.Button


def row_model(item: PocketItem) -> PocketRowModel:
    available = item_is_available(item)
    received = datetime.fromtimestamp(item.received_at).strftime("%I:%M %p").lstrip("0")
    if item.kind is PocketItemKind.LOCAL_FILE:
        path = Path(item.value)
        subtitle = f"{path.parent} · {received}"
        icon = "text-x-generic-symbolic"
        action = "Open"
    elif item.kind is PocketItemKind.SAVED_IMAGE:
        subtitle = f"Dropped image · {received}"
        icon = "image-x-generic-symbolic"
        action = "Open"
    elif item.kind is PocketItemKind.URL:
        host = urlsplit(item.value).hostname or item.display_name
        subtitle = f"{host} · {received}"
        icon = "web-browser-symbolic"
        action = "Open"
    else:
        subtitle = f"Text · {received}"
        icon = "accessories-text-editor-symbolic"
        action = "View"
    if not available:
        subtitle = f"Unavailable · {subtitle}"
    return PocketRowModel(
        item_id=item.id,
        title=item.display_name,
        subtitle=subtitle,
        icon_name=icon,
        available=available,
        action_label=action,
    )


def _launch_default(uri: str) -> None:
    Gio.AppInfo.launch_default_for_uri(uri, None)


class PocketTextWindow(Gtk.Window):
    """Read-only detail view for a Pocket text item."""

    def __init__(
        self,
        item: PocketItem,
        *,
        parent: Gtk.Window | None = None,
        on_close: Callable[["PocketTextWindow"], None] | None = None,
    ) -> None:
        super().__init__(title=item.display_name)
        self.set_default_size(440, 320)
        self.set_resizable(True)
        self.add_css_class("mochi-pocket-window")
        self._on_close = on_close
        if parent is not None:
            self.set_transient_for(parent)
        if on_close is not None:
            self.connect("close-request", self._handle_close_request)

        scroll = Gtk.ScrolledWindow()
        scroll.set_margin_top(16)
        scroll.set_margin_bottom(16)
        scroll.set_margin_start(16)
        scroll.set_margin_end(16)
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.get_buffer().set_text(item.value)
        scroll.set_child(self.text_view)
        self.set_child(scroll)

    def _handle_close_request(self, _window: Gtk.Window) -> bool:
        callback = self._on_close
        self._on_close = None
        if callback is not None:
            callback(self)
        return False


class PocketClearDialog(Gtk.Window):
    """Small modal confirmation without deprecated Gtk.Dialog APIs."""

    def __init__(
        self,
        *,
        parent: Gtk.Window,
        on_response: Callable[["PocketClearDialog", bool], None],
    ) -> None:
        super().__init__(title="Clear Pocket?")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_resizable(False)
        self.add_css_class("mochi-pocket-window")
        self._on_response = on_response
        self._responded = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        self.set_child(content)

        message = Gtk.Label(
            label=(
                "Remove everything from Pocket? "
                "Original files on your computer will not be deleted."
            )
        )
        message.set_wrap(True)
        message.set_xalign(0)
        content.append(message)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        content.append(actions)

        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", lambda _button: self.respond(False))
        actions.append(self.cancel_button)

        self.clear_button = Gtk.Button(label="Clear All")
        self.clear_button.add_css_class("destructive-action")
        self.clear_button.connect("clicked", lambda _button: self.respond(True))
        actions.append(self.clear_button)

        self.connect("close-request", self._on_close_request)

    def respond(self, accepted: bool) -> None:
        if self._responded:
            return
        self._responded = True
        self._on_response(self, bool(accepted))

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        self.respond(False)
        return True


class PocketWindow(Gtk.Window):
    """Newest-first Pocket list with safe open/view/remove actions."""

    EMPTY_TEXT = "Pocket is empty. Drag a file, link, image, or text onto Mochi."

    def __init__(
        self,
        controller: PocketController,
        *,
        launcher: Callable[[str], None] = _launch_default,
    ) -> None:
        super().__init__(title="Mochi Pocket")
        self.set_default_size(500, 520)
        self.set_resizable(True)
        self.set_hide_on_close(True)
        self.add_css_class("mochi-pocket-window")
        self._controller = controller
        self._launcher = launcher
        self.rows: dict[str, PocketRowWidgets] = {}
        self.detail_windows: list[PocketTextWindow] = []
        self.clear_dialog: PocketClearDialog | None = None
        self.empty_visible = False
        self.empty_text = self.EMPTY_TEXT
        self.error_text = ""
        self._install_css()

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("mochi-pocket-card")
        self.set_child(card)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.append(header)

        title = Gtk.Label(label="Pocket")
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("mochi-pocket-title")
        header.append(title)

        self.clear_button = Gtk.Button(label="Clear All")
        self.clear_button.add_css_class("destructive-action")
        self.clear_button.set_tooltip_text("Remove everything from Pocket")
        self.clear_button.connect("clicked", self._request_clear_all)
        header.append(self.clear_button)

        subtitle = Gtk.Label(label="The latest things Mochi is holding for you.")
        subtitle.set_xalign(0)
        subtitle.set_wrap(True)
        subtitle.add_css_class("mochi-pocket-subtitle")
        card.append(subtitle)

        self._error = Gtk.Label()
        self._error.set_xalign(0)
        self._error.set_wrap(True)
        self._error.add_css_class("mochi-pocket-error")
        self._error.set_visible(False)
        card.append(self._error)

        self._empty = Gtk.Label(label=self.EMPTY_TEXT)
        self._empty.set_wrap(True)
        self._empty.set_justify(Gtk.Justification.CENTER)
        self._empty.set_vexpand(True)
        self._empty.set_valign(Gtk.Align.CENTER)
        card.append(self._empty)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll.set_child(self._list)
        card.append(scroll)
        self._scroll = scroll

        self.refresh()

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(POCKET_WINDOW_CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def refresh(self) -> None:
        child = self._list.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            self._list.remove(child)
            child = following
        self.rows.clear()

        for item in self._controller.items:
            widgets = self._make_row(item)
            self.rows[item.id] = widgets
            self._list.append(widgets.container)

        self.empty_visible = not self.rows
        self._empty.set_visible(self.empty_visible)
        self._scroll.set_visible(not self.empty_visible)
        self.clear_button.set_sensitive(not self.empty_visible)

    def destroy(self) -> None:
        if self.clear_dialog is not None:
            dialog = self.clear_dialog
            self.clear_dialog = None
            dialog.destroy()
        self._close_detail_windows()
        super().destroy()

    def open_item(self, item_id: str) -> bool:
        item = self._item(item_id)
        if item is None:
            return False
        if item.kind is PocketItemKind.TEXT:
            detail = PocketTextWindow(
                item,
                parent=self,
                on_close=self._on_detail_window_closed,
            )
            self.detail_windows.append(detail)
            detail.present()
            self._clear_error()
            return True
        if not item_is_available(item):
            self._show_error("That item is no longer available.")
            return False

        uri = launch_uri_for(item)
        try:
            self._launcher(uri)
        except (GLib.Error, OSError, ValueError) as error:
            self._show_error(f"Mochi couldn't open that item: {error}")
            return False
        self._clear_error()
        return True

    def open_containing_folder(self, item_id: str) -> bool:
        item = self._item(item_id)
        if item is None or item.kind is not PocketItemKind.LOCAL_FILE:
            return False
        if not item_is_available(item):
            self._show_error("That item is no longer available.")
            return False

        folder_uri = folder_uri_for(item)
        try:
            self._launcher(folder_uri)
        except (GLib.Error, OSError, ValueError) as error:
            self._show_error(f"Mochi couldn't open that folder: {error}")
            return False
        self._clear_error()
        return True

    def remove_item(self, item_id: str) -> bool:
        if not self._controller.remove(item_id):
            self._show_error("Mochi couldn't remove that item.")
            return False
        self._clear_error()
        self._sync_rows_if_needed()
        return True

    def _request_clear_all(self, _button: Gtk.Button) -> None:
        if not self._controller.items or self.clear_dialog is not None:
            return

        dialog = PocketClearDialog(
            parent=self,
            on_response=self._on_clear_response,
        )
        self.clear_dialog = dialog
        dialog.present()

    def _on_clear_response(
        self,
        dialog: PocketClearDialog,
        accepted: bool,
    ) -> None:
        if self.clear_dialog is dialog:
            self.clear_dialog = None
        dialog.destroy()

        if not accepted:
            return
        if not self._controller.clear_all():
            self._show_error("Mochi couldn't clear Pocket.")
            return

        self._close_detail_windows()
        self._clear_error()
        self._sync_rows_if_needed()

    def _sync_rows_if_needed(self) -> None:
        current_ids = tuple(item.id for item in self._controller.items)
        if tuple(self.rows) != current_ids:
            self.refresh()
            return
        self.empty_visible = not current_ids
        self.clear_button.set_sensitive(bool(current_ids))

    def _on_detail_window_closed(self, detail: PocketTextWindow) -> None:
        if detail in self.detail_windows:
            self.detail_windows.remove(detail)

    def _close_detail_windows(self) -> None:
        details = tuple(self.detail_windows)
        self.detail_windows.clear()
        for detail in details:
            detail.destroy()

    def _make_row(self, item: PocketItem) -> PocketRowWidgets:
        model = row_model(item)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("mochi-setting-row")

        icon = Gtk.Image.new_from_icon_name(model.icon_name)
        row.append(icon)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        title = Gtk.Label(label=model.title)
        title.set_xalign(0)
        title.set_ellipsize(3)
        labels.append(title)
        subtitle = Gtk.Label(label=model.subtitle)
        subtitle.set_xalign(0)
        subtitle.set_ellipsize(3)
        subtitle.add_css_class("mochi-pocket-row-subtitle")
        labels.append(subtitle)
        row.append(labels)

        open_button = Gtk.Button(label=model.action_label)
        open_button.add_css_class("mochi-pocket-primary")
        open_button.set_sensitive(model.available)
        open_button.connect("clicked", lambda _button: self.open_item(item.id))
        row.append(open_button)

        folder_button: Gtk.Button | None = None
        if item.kind is PocketItemKind.LOCAL_FILE:
            folder_button = Gtk.Button.new_from_icon_name("folder-open-symbolic")
            folder_button.set_tooltip_text("Open containing folder")
            folder_button.set_sensitive(model.available)
            folder_button.connect(
                "clicked",
                lambda _button: self.open_containing_folder(item.id),
            )
            row.append(folder_button)

        remove_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        remove_button.set_tooltip_text("Remove from Pocket")
        remove_button.connect("clicked", lambda _button: self.remove_item(item.id))
        row.append(remove_button)
        return PocketRowWidgets(
            model,
            row,
            open_button,
            folder_button,
            remove_button,
        )

    def _item(self, item_id: str) -> PocketItem | None:
        return next(
            (item for item in self._controller.items if item.id == item_id),
            None,
        )

    def _show_error(self, message: str) -> None:
        self.error_text = message
        self._error.set_text(message)
        self._error.set_visible(True)

    def _clear_error(self) -> None:
        self.error_text = ""
        self._error.set_text("")
        self._error.set_visible(False)
