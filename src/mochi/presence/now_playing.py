"""Compact, user-invoked MPRIS controls attached to Mochi's nameplate.

The feature is deliberately opt-in: Mochi does not retain track metadata during
normal ambient music detection. Metadata is sampled only when the user opens the
nameplate player, kept in memory long enough to render the visible controls, and
never logged or persisted.

The player reuses the existing nameplate surface instead of opening another
popover/window. That keeps pointer ownership simple and avoids reintroducing the
focus/grab contention that older interactive status overlays caused.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from mochi.media_activity import (
    _deep_unpack,
    _is_browser_player,
    _metadata_indicates_watchable_video,
)
from mochi.music_activity import (
    MprisMusicBackend,
    _is_music_first_player,
    _metadata_indicates_music,
)


@dataclass(frozen=True)
class NowPlayingSnapshot:
    """Transient presentation data for one recognized MPRIS music player."""

    title: str
    artist: str | None
    playing: bool


class MprisNowPlayingController:
    """Read and control the currently relevant music player over MPRIS.

    Only the selected D-Bus bus name is retained. Track metadata is returned to
    the caller as an immutable snapshot and is never stored on the controller.
    """

    PLAYER_PREFIX = MprisMusicBackend.PLAYER_PREFIX
    DBUS_NAME = MprisMusicBackend.DBUS_NAME
    DBUS_PATH = MprisMusicBackend.DBUS_PATH
    DBUS_INTERFACE = MprisMusicBackend.DBUS_INTERFACE
    PLAYER_PATH = MprisMusicBackend.PLAYER_PATH
    PLAYER_INTERFACE = MprisMusicBackend.PLAYER_INTERFACE
    PROPERTIES_INTERFACE = MprisMusicBackend.PROPERTIES_INTERFACE

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._connection = None
        self._active_bus_name: str | None = None
        self._logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _load_gio():
        return MprisMusicBackend._load_gio()

    def start(self) -> bool:
        if self._connection is not None:
            return True
        try:
            Gio, _GLib = self._load_gio()
            self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception as exc:
            self._logger.debug("Now Playing unavailable: %s", exc)
            self._connection = None
        return self._connection is not None

    def stop(self) -> None:
        self._active_bus_name = None
        self._connection = None

    def snapshot(self) -> NowPlayingSnapshot | None:
        """Return the best current music player without retaining its metadata."""
        if not self.start():
            return None

        try:
            Gio, GLib = self._load_gio()
            names = self._list_names(Gio)
        except Exception as exc:
            self._logger.debug("Now Playing sample failed: %s", exc)
            self._active_bus_name = None
            return None

        paused_candidate: tuple[str, NowPlayingSnapshot] | None = None
        for bus_name in names:
            if not bus_name.startswith(self.PLAYER_PREFIX):
                continue
            try:
                status = self._get_property(bus_name, "PlaybackStatus", Gio, GLib)
                if status not in ("Playing", "Paused"):
                    continue
                metadata = self._get_property(bus_name, "Metadata", Gio, GLib)
                if not self._is_music_player(bus_name, metadata):
                    continue
                snapshot = self._snapshot_from_metadata(
                    metadata,
                    playing=status == "Playing",
                )
            except Exception:
                continue

            if snapshot.playing:
                self._active_bus_name = bus_name
                return snapshot
            if paused_candidate is None:
                paused_candidate = (bus_name, snapshot)

        if paused_candidate is not None:
            self._active_bus_name = paused_candidate[0]
            return paused_candidate[1]

        self._active_bus_name = None
        return None

    def previous(self) -> bool:
        return self._call_player_method("Previous")

    def play_pause(self) -> bool:
        return self._call_player_method("PlayPause")

    def next(self) -> bool:
        return self._call_player_method("Next")

    def _call_player_method(self, method: str) -> bool:
        if self._active_bus_name is None and self.snapshot() is None:
            return False
        if self._connection is None or self._active_bus_name is None:
            return False
        try:
            Gio, _GLib = self._load_gio()
            self._connection.call_sync(
                self._active_bus_name,
                self.PLAYER_PATH,
                self.PLAYER_INTERFACE,
                method,
                None,
                None,
                Gio.DBusCallFlags.NONE,
                750,
                None,
            )
            return True
        except Exception as exc:
            self._logger.debug("Now Playing command %s failed: %s", method, exc)
            return False

    def _list_names(self, Gio) -> tuple[str, ...]:
        reply = self._connection.call_sync(
            self.DBUS_NAME,
            self.DBUS_PATH,
            self.DBUS_INTERFACE,
            "ListNames",
            None,
            None,
            Gio.DBusCallFlags.NONE,
            750,
            None,
        )
        names = _deep_unpack(reply)
        if isinstance(names, tuple) and len(names) == 1:
            names = names[0]
        if not isinstance(names, (list, tuple)):
            return ()
        return tuple(name for name in names if isinstance(name, str))

    def _get_property(self, bus_name: str, property_name: str, Gio, GLib):
        reply = self._connection.call_sync(
            bus_name,
            self.PLAYER_PATH,
            self.PROPERTIES_INTERFACE,
            "Get",
            GLib.Variant("(ss)", (self.PLAYER_INTERFACE, property_name)),
            None,
            Gio.DBusCallFlags.NONE,
            750,
            None,
        )
        value = _deep_unpack(reply)
        if isinstance(value, tuple) and len(value) == 1:
            value = value[0]
        return value

    @staticmethod
    def _is_music_player(bus_name: str, metadata) -> bool:
        metadata = _deep_unpack(metadata)
        if _metadata_indicates_watchable_video(metadata):
            return False
        browser = _is_browser_player(bus_name)
        if _metadata_indicates_music(metadata, allow_artist_album=not browser):
            return True
        return not browser and _is_music_first_player(bus_name)

    @staticmethod
    def _snapshot_from_metadata(
        metadata,
        *,
        playing: bool,
    ) -> NowPlayingSnapshot:
        metadata = _deep_unpack(metadata)
        if not isinstance(metadata, dict):
            metadata = {}

        title_value = metadata.get("xesam:title")
        title = title_value.strip() if isinstance(title_value, str) else ""
        title = title or "Unknown track"

        artist_value = metadata.get("xesam:artist")
        if isinstance(artist_value, str):
            artists = [artist_value.strip()]
        elif isinstance(artist_value, (list, tuple)):
            artists = [
                value.strip()
                for value in artist_value
                if isinstance(value, str) and value.strip()
            ]
        else:
            artists = []

        return NowPlayingSnapshot(
            title=title,
            artist=", ".join(artists) or None,
            playing=playing,
        )


class _NameplatePlayerUI:
    """Add a constrained primary-click music panel to an existing Nameplate."""

    def __init__(
        self,
        *,
        nameplate,
        on_toggle: Callable[[], None],
        on_previous: Callable[[], None],
        on_play_pause: Callable[[], None],
        on_next: Callable[[], None],
    ) -> None:
        self._nameplate = nameplate
        self._expanded = False
        self._panels = []
        self._track_labels = []
        self._artist_labels = []
        self._play_buttons = []

        self._make_name_clickable(nameplate._label, on_toggle)
        self._make_name_clickable(nameplate._popover_label, on_toggle)

        for content in (nameplate._content, nameplate._popover_content):
            content.set_can_target(True)
            panel, track, artist, play_button = self._make_panel(
                on_previous=on_previous,
                on_play_pause=on_play_pause,
                on_next=on_next,
            )
            content.append(panel)
            self._panels.append(panel)
            self._track_labels.append(track)
            self._artist_labels.append(artist)
            self._play_buttons.append(play_button)

        nameplate._window.set_can_target(True)
        nameplate._popover.set_can_target(True)
        self._install_css(nameplate._owner.get_display())

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        for panel in self._panels:
            panel.set_visible(self._expanded)
        if self._nameplate.visible:
            self._nameplate.update_position()

    def update(self, snapshot: NowPlayingSnapshot) -> None:
        for label in self._track_labels:
            label.set_text(snapshot.title)
        artist_text = snapshot.artist or ""
        for label in self._artist_labels:
            label.set_text(artist_text)
            label.set_visible(bool(artist_text))
        icon_name = (
            "media-playback-pause-symbolic"
            if snapshot.playing
            else "media-playback-start-symbolic"
        )
        for button in self._play_buttons:
            button.set_icon_name(icon_name)
        if self._nameplate.visible:
            self._nameplate.update_position()

    @staticmethod
    def _make_name_clickable(
        label: Gtk.Label,
        on_toggle: Callable[[], None],
    ) -> None:
        label.set_can_target(True)
        gesture = Gtk.GestureClick.new()
        gesture.set_button(Gdk.BUTTON_PRIMARY)
        gesture.connect("released", lambda *_args: on_toggle())
        label.add_controller(gesture)

    @staticmethod
    def _make_control_button(
        icon_name: str,
        callback: Callable[[], None],
    ) -> Gtk.Button:
        button = Gtk.Button.new_from_icon_name(icon_name)
        button.set_focusable(False)
        button.set_can_focus(False)
        button.add_css_class("flat")
        button.add_css_class("mochi-now-playing-button")
        button.connect("clicked", lambda *_args: callback())
        return button

    def _make_panel(
        self,
        *,
        on_previous: Callable[[], None],
        on_play_pause: Callable[[], None],
        on_next: Callable[[], None],
    ) -> tuple[Gtk.Box, Gtk.Label, Gtk.Label, Gtk.Button]:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        panel.add_css_class("mochi-now-playing-panel")
        panel.set_can_target(True)
        panel.set_visible(False)

        now_playing = Gtk.Label(label="NOW PLAYING")
        now_playing.set_xalign(0)
        now_playing.set_can_target(False)
        now_playing.add_css_class("mochi-now-playing-kicker")
        panel.append(now_playing)

        track = Gtk.Label(label="")
        track.set_xalign(0)
        track.set_max_width_chars(30)
        track.set_ellipsize(Pango.EllipsizeMode.END)
        track.set_can_target(False)
        track.add_css_class("mochi-now-playing-title")
        panel.append(track)

        artist = Gtk.Label(label="")
        artist.set_xalign(0)
        artist.set_max_width_chars(30)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.set_can_target(False)
        artist.add_css_class("mochi-now-playing-artist")
        panel.append(artist)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        controls.set_halign(Gtk.Align.CENTER)
        controls.set_can_target(True)
        panel.append(controls)

        previous = self._make_control_button(
            "media-skip-backward-symbolic",
            on_previous,
        )
        play_pause = self._make_control_button(
            "media-playback-pause-symbolic",
            on_play_pause,
        )
        next_button = self._make_control_button(
            "media-skip-forward-symbolic",
            on_next,
        )
        controls.append(previous)
        controls.append(play_pause)
        controls.append(next_button)
        return panel, track, artist, play_pause

    @staticmethod
    def _install_css(display: Gdk.Display) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(
            """
            .mochi-now-playing-panel {
                background: alpha(@window_bg_color, 0.97);
                border: 1px solid alpha(#79c98b, 0.28);
                border-radius: 13px;
                box-shadow: 0 5px 16px alpha(black, 0.12);
                padding: 8px 10px 7px 10px;
                margin-top: 4px;
                min-width: 190px;
            }
            .mochi-now-playing-kicker {
                color: alpha(@window_fg_color, 0.55);
                font-size: 8px;
                font-weight: 800;
            }
            .mochi-now-playing-title {
                color: @window_fg_color;
                font-size: 11px;
                font-weight: 700;
            }
            .mochi-now-playing-artist {
                color: alpha(@window_fg_color, 0.64);
                font-size: 9px;
            }
            button.mochi-now-playing-button {
                min-width: 26px;
                min-height: 26px;
                padding: 2px;
                border-radius: 999px;
            }
            """
        )
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )


class NowPlayingMixin:
    """Expand Mochi's name tag into a tiny MPRIS player on primary click."""

    NOW_PLAYING_REFRESH_SECONDS = 1.0

    def __init__(self, *args, **kwargs) -> None:
        self._now_playing_controller: MprisNowPlayingController | None = None
        self._now_playing_ui: _NameplatePlayerUI | None = None
        self._now_playing_last_sample_at = 0.0
        super().__init__(*args, **kwargs)

        if self._preview_mode or self._nameplate is None:
            return

        self._now_playing_controller = MprisNowPlayingController(self._logger)
        self._now_playing_ui = _NameplatePlayerUI(
            nameplate=self._nameplate,
            on_toggle=self._toggle_now_playing_panel,
            on_previous=self._now_playing_previous,
            on_play_pause=self._now_playing_play_pause,
            on_next=self._now_playing_next,
        )

    def _toggle_now_playing_panel(self) -> None:
        ui = self._now_playing_ui
        if ui is None:
            return
        if ui.expanded:
            ui.set_expanded(False)
            return

        if not self._refresh_now_playing():
            self.show_nameplate_feedback(
                "nothing playing",
                duration_seconds=1.6,
            )
            return
        ui.set_expanded(True)

    def _refresh_now_playing(self) -> bool:
        controller = self._now_playing_controller
        ui = self._now_playing_ui
        if controller is None or ui is None:
            return False
        snapshot = controller.snapshot()
        self._now_playing_last_sample_at = time.monotonic()
        if snapshot is None:
            ui.set_expanded(False)
            return False
        ui.update(snapshot)
        return True

    def _now_playing_previous(self) -> None:
        controller = self._now_playing_controller
        if controller is not None:
            controller.previous()
        self._now_playing_last_sample_at = 0.0

    def _now_playing_play_pause(self) -> None:
        controller = self._now_playing_controller
        if controller is not None:
            controller.play_pause()
        self._now_playing_last_sample_at = 0.0

    def _now_playing_next(self) -> None:
        controller = self._now_playing_controller
        if controller is not None:
            controller.next()
        self._now_playing_last_sample_at = 0.0

    def _tick(self) -> bool:
        result = super()._tick()
        ui = self._now_playing_ui
        nameplate = getattr(self, "_nameplate", None)
        if (
            ui is not None
            and ui.expanded
            and nameplate is not None
            and nameplate.visible
            and time.monotonic() - self._now_playing_last_sample_at
            >= self.NOW_PLAYING_REFRESH_SECONDS
        ):
            self._refresh_now_playing()
        return result

    def shutdown_presence(self) -> None:
        if self._now_playing_controller is not None:
            self._now_playing_controller.stop()
            self._now_playing_controller = None
        self._now_playing_ui = None
        super().shutdown_presence()
