"""Compact GTK presentation for Mochi updates."""

from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Callable

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .model import InstalledBuild, UpdateTarget
from .worker import UpdateProgress, UpdateStage


MOCHI_GREEN = "#79c98b"

UPDATE_WINDOW_CSS = f"""
window.mochi-update-window {{
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}}

.mochi-update-card {{
    padding: 22px;
}}

.mochi-update-title {{
    font-size: 20px;
    font-weight: 700;
    color: @theme_fg_color;
}}

.mochi-update-body,
.mochi-update-version,
.mochi-update-highlight,
.mochi-update-details,
.mochi-update-stage {{
    color: alpha(@theme_fg_color, 0.76);
}}

.mochi-update-version,
.mochi-update-details,
.mochi-update-stage {{
    font-size: 11px;
}}

.mochi-update-highlight {{
    font-size: 13px;
}}

progressbar.mochi-update-progress trough {{
    min-height: 8px;
    border-radius: 999px;
    background-color: alpha(@theme_fg_color, 0.12);
}}

progressbar.mochi-update-progress progress {{
    min-height: 8px;
    border-radius: 999px;
    background-color: {MOCHI_GREEN};
}}

button.mochi-update-primary {{
    background-image: none;
    background-color: {MOCHI_GREEN};
    color: #102417;
    border-radius: 10px;
    font-weight: 700;
}}

button.mochi-update-secondary {{
    border-radius: 10px;
}}

.mochi-update-safe {{
    color: {MOCHI_GREEN};
    font-weight: 600;
}}
"""


def _default_asset_root() -> Path:
    override = os.environ.get("MOCHI_UPDATER_ASSET_ROOT")
    if override:
        return Path(override)

    source_root = Path(__file__).resolve().parents[3] / "assets" / "mochi"
    if source_root.is_dir():
        return source_root

    return Path(os.environ.get("MOCHI_ASSET_ROOT", Path(os.sys.prefix) / "share" / "mochi"))


class UpdaterSprite(Gtk.DrawingArea):
    """Small real-Mochi animation renderer with crisp pixel scaling."""

    def __init__(
        self,
        asset_root: Path | None = None,
        animation: str = "idle",
        *,
        content_size: int = 128,
        frame_interval_ms: int = 180,
    ) -> None:
        super().__init__()
        self.asset_root = Path(asset_root) if asset_root is not None else _default_asset_root()
        self.animation = animation
        self.frame_interval_ms = max(60, int(frame_interval_ms))
        self._frames: list[cairo.ImageSurface] = []
        self._frame_index = 0
        self._timer_id: int | None = None

        self.set_content_width(content_size)
        self.set_content_height(content_size)
        self.set_draw_func(self._draw)
        self.set_animation(animation)

    def set_animation(self, animation: str) -> None:
        self.animation = animation
        self._frames = self._load_frames(animation)
        self._frame_index = 0
        self._replace_timer()
        self.queue_draw()

    def _load_frames(self, animation: str) -> list[cairo.ImageSurface]:
        folder = self.asset_root / animation
        if not folder.is_dir():
            return []

        frames: list[cairo.ImageSurface] = []
        for path in sorted(folder.glob("*.png")):
            try:
                frames.append(cairo.ImageSurface.create_from_png(str(path)))
            except (cairo.Error, OSError):
                continue
        return frames

    def _replace_timer(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        if len(self._frames) > 1:
            self._timer_id = GLib.timeout_add(
                self.frame_interval_ms,
                self._advance_frame,
            )

    def _advance_frame(self) -> bool:
        if len(self._frames) <= 1:
            self._timer_id = None
            return False
        self._frame_index = (self._frame_index + 1) % len(self._frames)
        self.queue_draw()
        return True

    def _draw(
        self,
        _area: Gtk.DrawingArea,
        context: cairo.Context,
        width: int,
        height: int,
    ) -> None:
        if not self._frames:
            return

        surface = self._frames[self._frame_index]
        source_width = max(1, surface.get_width())
        source_height = max(1, surface.get_height())
        raw_scale = min(width / source_width, height / source_height)
        if raw_scale >= 1:
            scale = max(1, int(raw_scale))
        else:
            scale = raw_scale

        draw_width = source_width * scale
        draw_height = source_height * scale
        x = (width - draw_width) / 2
        y = (height - draw_height) / 2

        context.save()
        context.translate(x, y)
        context.scale(scale, scale)
        context.set_source_surface(surface, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
        context.restore()


class UpdateWindow(Gtk.Window):
    """One compact window that transitions through the update lifecycle."""

    def __init__(
        self,
        *,
        on_later: Callable[[], None],
        on_update_restart: Callable[[], None],
        on_retry: Callable[[], None],
        on_close: Callable[[], None],
        asset_root: Path | None = None,
    ) -> None:
        super().__init__(title="Mochi Update")
        self.set_default_size(460, 520)
        self.set_resizable(False)
        self.add_css_class("mochi-update-window")

        self._on_later = on_later
        self._on_update_restart = on_update_restart
        self._on_retry = on_retry
        self._on_close = on_close

        self.state_name = "idle"
        self.title_text = ""
        self.body_text = ""
        self.version_text = ""
        self.highlight_texts: tuple[str, ...] = ()
        self.details_text = ""
        self.visible_actions: tuple[str, ...] = ()
        self.progress_fraction: float | None = None
        self.progress_is_indeterminate = True

        self._install_css()

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("mochi-update-card")
        card.set_margin_top(8)
        card.set_margin_bottom(8)
        card.set_margin_start(8)
        card.set_margin_end(8)
        self.set_child(card)

        self.sprite = UpdaterSprite(asset_root=asset_root, animation="idle")
        self.sprite.set_halign(Gtk.Align.CENTER)
        card.append(self.sprite)

        self._title = Gtk.Label()
        self._title.set_wrap(True)
        self._title.set_justify(Gtk.Justification.CENTER)
        self._title.set_halign(Gtk.Align.CENTER)
        self._title.add_css_class("mochi-update-title")
        card.append(self._title)

        self._body = Gtk.Label()
        self._body.set_wrap(True)
        self._body.set_justify(Gtk.Justification.CENTER)
        self._body.set_halign(Gtk.Align.FILL)
        self._body.add_css_class("mochi-update-body")
        card.append(self._body)

        self._version = Gtk.Label()
        self._version.set_wrap(True)
        self._version.set_xalign(0.0)
        self._version.add_css_class("mochi-update-version")
        card.append(self._version)

        self._highlights = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.append(self._highlights)

        self._progress = Gtk.ProgressBar()
        self._progress.add_css_class("mochi-update-progress")
        self._progress.set_visible(False)
        card.append(self._progress)

        self._stage = Gtk.Label()
        self._stage.set_wrap(True)
        self._stage.set_xalign(0.0)
        self._stage.add_css_class("mochi-update-stage")
        self._stage.set_visible(False)
        card.append(self._stage)

        self._details = Gtk.Revealer()
        details_label = Gtk.Label()
        details_label.set_wrap(True)
        details_label.set_selectable(True)
        details_label.set_xalign(0.0)
        details_label.add_css_class("mochi-update-details")
        self._details_label = details_label
        self._details.set_child(details_label)
        self._details.set_reveal_child(False)
        card.append(self._details)

        self._actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._actions.set_halign(Gtk.Align.END)
        card.append(self._actions)

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(UPDATE_WINDOW_CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def show_available(
        self,
        installed: InstalledBuild | None,
        target: UpdateTarget,
    ) -> None:
        self.state_name = "available"
        self.title_text = "A new Mochi update!"
        self.body_text = "Mochi learned some new things and would love to update."
        installed_version = installed.version if installed is not None else "unknown"
        installed_commit = (
            installed.commit[:7]
            if installed is not None and installed.commit
            else "unknown"
        )
        self.version_text = (
            f"Installed  {installed_version} ({installed_commit})\n"
            f"Available  {target.metadata.version} ({target.commit[:7]})"
        )
        self.highlight_texts = tuple(target.metadata.highlights[:3])
        self.details_text = ""
        self.progress_fraction = None
        self.progress_is_indeterminate = True

        self.sprite.set_animation("idle")
        self._title.set_text(self.title_text)
        self._body.set_text(self.body_text)
        self._version.set_text(self.version_text)
        self._set_highlights(self.highlight_texts)
        self._progress.set_visible(False)
        self._stage.set_visible(False)
        self._details.set_reveal_child(False)
        self._details_label.set_text("")
        self._set_actions(
            (
                ("Later", self._on_later, False),
                ("Update & Restart", self._on_update_restart, True),
            )
        )

    def show_progress(self, progress: UpdateProgress) -> None:
        self.state_name = progress.stage.value
        self.title_text = self._progress_title(progress.stage)
        self.body_text = progress.message
        self.highlight_texts = ()
        self.details_text = ""

        self.sprite.set_animation("focus")
        self._title.set_text(self.title_text)
        self._body.set_text(self.body_text)
        self._version.set_text("")
        self._set_highlights(())
        self._details.set_reveal_child(False)
        self._details_label.set_text("")
        self._stage.set_visible(True)
        self._stage.set_text(self._stage_text(progress.stage))
        self._progress.set_visible(True)

        if (
            progress.stage is UpdateStage.DOWNLOADING
            and progress.downloaded is not None
            and progress.total is not None
            and progress.total > 0
        ):
            fraction = max(0.0, min(progress.downloaded / progress.total, 1.0))
            self.progress_fraction = fraction
            self.progress_is_indeterminate = False
            self._progress.set_fraction(fraction)
        else:
            self.progress_fraction = None
            self.progress_is_indeterminate = True
            self._progress.pulse()

        self._set_actions(())

    def show_failure(self, message: str, details: str) -> None:
        self.state_name = "failure"
        self.title_text = "Hmm... something went wrong."
        self.body_text = (
            f"{message}\n\nYour current Mochi is still safe."
            if message and message != self.title_text
            else "Your current Mochi is still safe."
        )
        self.version_text = ""
        self.highlight_texts = ()
        self.details_text = details
        self.progress_fraction = None
        self.progress_is_indeterminate = True

        self.sprite.set_animation("sad_idle")
        self._title.set_text(self.title_text)
        self._body.set_text(self.body_text)
        self._body.add_css_class("mochi-update-safe")
        self._version.set_text("")
        self._set_highlights(())
        self._progress.set_visible(False)
        self._stage.set_visible(False)
        self._details_label.set_text(details)
        self._details.set_reveal_child(False)
        self._set_actions(
            (
                ("Try Again", self._on_retry, True),
                ("Close", self._on_close, False),
                ("Show Details", self._toggle_details, False),
            )
        )

    def show_success(self) -> None:
        self.state_name = "success"
        self.title_text = "All updated!"
        self.body_text = "Mochi is ready to come back. 🌱"
        self.version_text = ""
        self.highlight_texts = ()
        self.details_text = ""
        self.progress_fraction = None
        self.progress_is_indeterminate = True

        self.sprite.set_animation("wave")
        self._title.set_text(self.title_text)
        self._body.set_text(self.body_text)
        self._version.set_text("")
        self._set_highlights(())
        self._progress.set_visible(False)
        self._stage.set_visible(False)
        self._details.set_reveal_child(False)
        self._details_label.set_text("")
        self._set_actions(())

    def _set_highlights(self, highlights: tuple[str, ...]) -> None:
        self._clear_box(self._highlights)
        if not highlights:
            self._highlights.set_visible(False)
            return

        self._highlights.set_visible(True)
        heading = Gtk.Label(label="What’s new")
        heading.set_xalign(0.0)
        heading.add_css_class("mochi-update-title")
        self._highlights.append(heading)
        for highlight in highlights:
            label = Gtk.Label(label=f"• {highlight}")
            label.set_wrap(True)
            label.set_xalign(0.0)
            label.add_css_class("mochi-update-highlight")
            self._highlights.append(label)

    def _set_actions(
        self,
        actions: tuple[tuple[str, Callable[[], None], bool], ...],
    ) -> None:
        self._clear_box(self._actions)
        labels: list[str] = []
        for label, callback, primary in actions:
            button = Gtk.Button(label=label)
            button.add_css_class(
                "mochi-update-primary" if primary else "mochi-update-secondary"
            )
            button.connect("clicked", lambda _button, cb=callback: cb())
            self._actions.append(button)
            labels.append(label)
        self.visible_actions = tuple(labels)

    def _toggle_details(self) -> None:
        self._details.set_reveal_child(not self._details.get_reveal_child())

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            box.remove(child)
            child = next_child

    @staticmethod
    def _progress_title(stage: UpdateStage) -> str:
        if stage is UpdateStage.DOWNLOADING:
            return "Getting the newest Mochi…"
        if stage in {UpdateStage.INSTALLING, UpdateStage.SWAPPING, UpdateStage.REFRESHING}:
            return "Setting things up…"
        if stage is UpdateStage.RESTARTING:
            return "Almost done…"
        if stage is UpdateStage.SUCCESS:
            return "All updated!"
        return "Mochi Update"

    @staticmethod
    def _stage_text(active: UpdateStage) -> str:
        stages = (
            (UpdateStage.DOWNLOADING, "Downloaded update"),
            (UpdateStage.VERIFYING, "Verified files"),
            (UpdateStage.INSTALLING, "Installing Mochi"),
            (UpdateStage.SWAPPING, "Switching runtime"),
            (UpdateStage.REFRESHING, "Refreshing desktop integration"),
            (UpdateStage.RESTARTING, "Restarting Mochi"),
        )
        active_index = next(
            (index for index, (stage, _label) in enumerate(stages) if stage is active),
            -1,
        )
        rendered: list[str] = []
        for index, (_stage, label) in enumerate(stages):
            if active_index >= 0 and index < active_index:
                marker = "✓"
            elif index == active_index:
                marker = "●"
            else:
                marker = "○"
            rendered.append(f"{marker} {label}")
        return "\n".join(rendered)
