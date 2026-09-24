"""GTK developer surface for importing, previewing, and promoting Mochi emotes."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from mochi.dev_emote_workshop import (
    RARITIES,
    EmoteImportSpec,
    build_preview_animation,
    development_checkout_root,
    inspect_source,
    promote_emote,
    slugify_animation_id,
)
from mochi.state import MochiState


class EmoteWorkshopWindow(Gtk.Window):
    """Developer-only emote import workshop opened from Mochi Lab."""

    DEFAULT_FPS = 8.333333333333334

    def __init__(self, buddy) -> None:
        super().__init__(title="Mochi Emote Workshop")
        self._buddy = buddy
        self._source: Path | None = None
        self._chooser: Gtk.FileChooserNative | None = None
        self._preview_surface_keys: tuple[str, ...] = ()
        self.set_transient_for(buddy._window)
        self.set_default_size(520, 720)
        self.set_hide_on_close(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(16)
        outer.set_margin_bottom(16)
        outer.set_margin_start(16)
        outer.set_margin_end(16)

        header = Gtk.Label(label="Emote Workshop  ✦")
        header.set_xalign(0)
        header.add_css_class("mochi-menu-title")
        outer.append(header)

        intro = Gtk.Label(
            label=(
                "Preview a horizontal PNG spritesheet or a folder of PNG frames "
                "without registering it. Promote only after it looks right."
            )
        )
        intro.set_xalign(0)
        intro.set_wrap(True)
        outer.append(intro)

        source_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        choose_sheet = Gtk.Button(label="Choose spritesheet")
        choose_sheet.connect("clicked", self._choose_spritesheet)
        choose_frames = Gtk.Button(label="Choose frame folder")
        choose_frames.connect("clicked", self._choose_frame_folder)
        source_box.append(choose_sheet)
        source_box.append(choose_frames)
        outer.append(source_box)

        self._source_label = Gtk.Label(label="No source selected")
        self._source_label.set_xalign(0)
        self._source_label.set_wrap(True)
        self._source_label.add_css_class("dim-label")
        outer.append(self._source_label)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        row = 0

        self._label_entry = Gtk.Entry()
        self._attach_row(grid, row, "Label", self._label_entry)
        row += 1

        self._id_entry = Gtk.Entry()
        self._id_entry.set_placeholder_text("party_popper")
        self._attach_row(grid, row, "Animation ID", self._id_entry)
        row += 1

        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._cell_width = Gtk.SpinButton.new_with_range(1, 512, 1)
        self._cell_height = Gtk.SpinButton.new_with_range(1, 512, 1)
        self._cell_width.set_value(64)
        self._cell_height.set_value(64)
        size_box.append(self._cell_width)
        size_box.append(Gtk.Label(label="×"))
        size_box.append(self._cell_height)
        self._attach_row(grid, row, "Source cell", size_box)
        row += 1

        self._fps = Gtk.SpinButton.new_with_range(0.1, 60.0, 0.1)
        self._fps.set_digits(2)
        self._fps.set_value(self.DEFAULT_FPS)
        self._attach_row(grid, row, "FPS", self._fps)
        row += 1

        self._loop = Gtk.Switch()
        self._loop.set_halign(Gtk.Align.START)
        self._attach_row(grid, row, "Loop after promotion", self._loop)
        row += 1

        self._bond_level = Gtk.SpinButton.new_with_range(1, 99, 1)
        self._bond_level.set_value(1)
        self._attach_row(grid, row, "Bond level", self._bond_level)
        row += 1

        self._rarity = Gtk.ComboBoxText()
        for rarity in RARITIES:
            self._rarity.append_text(rarity)
        self._rarity.set_active(0)
        self._attach_row(grid, row, "Rarity", self._rarity)
        row += 1

        self._reveal = Gtk.CheckButton(label="Show unlock reveal")
        self._attach_row(grid, row, "Catalogue", self._reveal)

        outer.append(grid)

        self._inspection_label = Gtk.Label(label="Choose art to inspect it.")
        self._inspection_label.set_xalign(0)
        self._inspection_label.set_wrap(True)
        outer.append(self._inspection_label)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._preview_button = Gtk.Button(label="Preview once on Mochi")
        self._preview_button.set_sensitive(False)
        self._preview_button.connect("clicked", self._preview)
        actions.append(self._preview_button)

        self._promote_button = Gtk.Button(label="Promote to Mochi")
        self._promote_button.set_sensitive(False)
        self._promote_button.connect("clicked", self._promote)
        actions.append(self._promote_button)
        outer.append(actions)

        checkout_root = development_checkout_root()
        self._checkout_label = Gtk.Label()
        self._checkout_label.set_xalign(0)
        self._checkout_label.set_wrap(True)
        if checkout_root is None:
            self._checkout_label.set_text(
                "Promotion disabled: run Mochi from a Git source checkout."
            )
        else:
            self._checkout_label.set_text(f"Source checkout: {checkout_root}")
        self._checkout_label.add_css_class("dim-label")
        outer.append(self._checkout_label)

        snippet_label = Gtk.Label(label="Catalogue registration snippet")
        snippet_label.set_xalign(0)
        snippet_label.add_css_class("mochi-menu-section")
        outer.append(snippet_label)

        self._snippet = Gtk.TextView()
        self._snippet.set_editable(False)
        self._snippet.set_monospace(True)
        self._snippet.set_wrap_mode(Gtk.WrapMode.NONE)
        snippet_scroll = Gtk.ScrolledWindow()
        snippet_scroll.set_min_content_height(150)
        snippet_scroll.set_child(self._snippet)
        outer.append(snippet_scroll)

        self._copy_button = Gtk.Button(label="Copy snippet")
        self._copy_button.set_sensitive(False)
        self._copy_button.connect("clicked", self._copy_snippet)
        outer.append(self._copy_button)

        self._status = Gtk.Label(label="")
        self._status.set_xalign(0)
        self._status.set_wrap(True)
        outer.append(self._status)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(outer)
        self.set_child(scroller)

        self._cell_width.connect("value-changed", self._reinspect)
        self._cell_height.connect("value-changed", self._reinspect)

    @staticmethod
    def _attach_row(grid: Gtk.Grid, row: int, label: str, widget: Gtk.Widget) -> None:
        text = Gtk.Label(label=label)
        text.set_xalign(0)
        grid.attach(text, 0, row, 1, 1)
        widget.set_hexpand(True)
        grid.attach(widget, 1, row, 1, 1)

    def _choose_spritesheet(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative.new(
            "Choose emote spritesheet",
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )
        image_filter = Gtk.FileFilter()
        image_filter.set_name("PNG images")
        image_filter.add_mime_type("image/png")
        chooser.add_filter(image_filter)
        chooser.connect("response", self._on_source_chosen)
        self._chooser = chooser
        chooser.show()

    def _choose_frame_folder(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative.new(
            "Choose emote frame folder",
            self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            "_Open",
            "_Cancel",
        )
        chooser.connect("response", self._on_source_chosen)
        self._chooser = chooser
        chooser.show()

    def _on_source_chosen(
        self,
        chooser: Gtk.FileChooserNative,
        response: int,
    ) -> None:
        try:
            if response != Gtk.ResponseType.ACCEPT:
                return
            selected = chooser.get_file()
            if selected is None or selected.get_path() is None:
                self._set_status("The selected source is not a local filesystem path.")
                return
            self._source = Path(selected.get_path())
            base_name = (
                self._source.stem if self._source.is_file() else self._source.name
            )
            animation_id = slugify_animation_id(base_name)
            self._id_entry.set_text(animation_id)
            self._label_entry.set_text(
                animation_id.replace("_", " ").title()
            )
            self._source_label.set_text(str(self._source))
            self._inspect_selected_source()
        finally:
            chooser.destroy()
            self._chooser = None

    def _reinspect(self, _control) -> None:
        if self._source is not None:
            self._inspect_selected_source()

    def _inspect_selected_source(self) -> None:
        if self._source is None:
            return
        try:
            inspection = inspect_source(self._source, self._cell_size())
        except Exception as exc:
            self._inspection_label.set_text(f"Invalid source: {exc}")
            self._preview_button.set_sensitive(False)
            self._promote_button.set_sensitive(False)
            return

        warning_text = ""
        if inspection.warnings:
            warning_text = " · " + " · ".join(inspection.warnings)
        self._inspection_label.set_text(
            f"{inspection.frame_count} frame(s) · {inspection.source_kind} · "
            f"{inspection.source_cell_size[0]}×{inspection.source_cell_size[1]}"
            f"{warning_text}"
        )
        self._preview_button.set_sensitive(True)
        self._promote_button.set_sensitive(development_checkout_root() is not None)
        self._set_status("")

    def _cell_size(self) -> tuple[int, int]:
        return (
            self._cell_width.get_value_as_int(),
            self._cell_height.get_value_as_int(),
        )

    def _build_spec(self) -> EmoteImportSpec:
        if self._source is None:
            raise ValueError("Choose a spritesheet or frame folder first")
        rarity = self._rarity.get_active_text() or RARITIES[0]
        spec = EmoteImportSpec(
            source=self._source,
            animation_id=self._id_entry.get_text().strip(),
            label=self._label_entry.get_text().strip(),
            fps=self._fps.get_value(),
            loop=self._loop.get_active(),
            source_cell_size=self._cell_size(),
            bond_level=self._bond_level.get_value_as_int(),
            rarity=rarity,
            reveal_on_unlock=self._reveal.get_active(),
        )
        spec.validate()
        return spec

    def _preview(self, _button: Gtk.Button) -> None:
        try:
            spec = self._build_spec()
            animation, surfaces, inspection = build_preview_animation(spec)
        except Exception as exc:
            self._set_status(f"Preview failed: {exc}")
            return

        buddy = self._buddy
        buddy._cancel_active_emote()
        if buddy.state.current is MochiState.WALKING:
            buddy._cancel_walk()
            buddy._transition_to(MochiState.IDLE)
            buddy._play_animation("idle")
        if buddy.state.current is not MochiState.IDLE:
            self._set_status(
                f"Preview deferred: Mochi is currently {buddy.state.current.name.lower()}."
            )
            return
        if not buddy._transition_to(MochiState.IDLE_EMOTE):
            self._set_status("Mochi could not enter the preview state.")
            return

        for key in self._preview_surface_keys:
            buddy.atlas.frames.pop(key, None)
        buddy.atlas.frames.update(surfaces)
        self._preview_surface_keys = tuple(surfaces)

        buddy._current_animation = animation.name
        buddy._active_animation = animation
        buddy._pending_animation = "idle"
        buddy.player.play(animation)
        buddy.queue_draw()
        self._set_status(
            f"Previewing {inspection.frame_count} frame(s) once on Mochi."
        )

    def _promote(self, _button: Gtk.Button) -> None:
        try:
            spec = self._build_spec()
            result = promote_emote(spec)
        except Exception as exc:
            self._set_status(f"Promotion failed: {exc}")
            return

        buffer = self._snippet.get_buffer()
        buffer.set_text(result.catalogue_snippet)
        self._copy_button.set_sensitive(True)
        self._promote_button.set_sensitive(False)
        self._set_status(
            "Promoted art and manifest entry. Copy the catalogue snippet into "
            "src/mochi/emotes.py, then restart Mochi before testing the registered emote."
        )

    def _copy_snippet(self, _button: Gtk.Button) -> None:
        buffer = self._snippet.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, False)
        if text:
            self.get_clipboard().set_text(text)
            self._set_status("Catalogue snippet copied.")

    def _set_status(self, message: str) -> None:
        self._status.set_text(message)
