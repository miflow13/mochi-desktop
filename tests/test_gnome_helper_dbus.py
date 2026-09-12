"""Exercise actual Gio owner changes/subscriptions on an isolated session bus."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("already_active", [False, True])
def test_ambient_recovery_on_private_session_bus(already_active):
    pytest.importorskip("gi.repository.Gio")
    launcher = shutil.which("dbus-run-session")
    if launcher is None:
        pytest.skip("dbus-run-session is required for the isolated bus test")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [launcher, "--", sys.executable, str(Path(__file__).resolve()),
         "active" if already_active else "absent"],
        env={**os.environ, "PYTHONPATH": str(root / "src"),
             "GSETTINGS_BACKEND": "memory"},
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise(already_active):
    from gi.repository import Gio, GLib
    from mochi.developer_shortcut import DeveloperShortcutMonitor
    from mochi.file_activity import FileActivityMonitor
    from mochi.gnome_helper import GnomeHelperLifecycle
    from mochi.media_activity import MediaActivityMonitor, MprisMediaBackend
    from mochi.presence.integration import PresenceBuddyMixin
    from mochi.presence.signals import AppCategorySignalAdapter
    from mochi.presence_activity import PresenceActivityMonitor
    from mochi.typing_activity import (
        GnomeShellTypingPulseBackend, TypingActivityMonitor, TypingBurstDetector,
    )

    def until(predicate):
        deadline = time.monotonic() + 3
        while not predicate():
            assert time.monotonic() < deadline, "D-Bus lifecycle timed out"
            GLib.MainContext.default().iteration(False)
            time.sleep(0.001)

    helper = Gio.DBusConnection.new_for_address_sync(
        os.environ["DBUS_SESSION_BUS_ADDRESS"],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None,
    )
    events = []
    syncs = []
    name_ready = []

    def emit(name, payload=None):
        helper.emit_signal(None, GnomeHelperLifecycle.OBJECT_PATH,
                           GnomeHelperLifecycle.INTERFACE_NAME, name, payload)

    def sync(*_ignored):
        syncs.append(True)
        emit("UserIdle")
        emit("FileBrowsingStarted")
        emit("YouTubeFocusedStarted")
        emit("AppCategoryChanged", GLib.Variant("(s)", ("editor",)))

    request_id = helper.signal_subscribe(
        None, GnomeHelperLifecycle.INTERFACE_NAME,
        GnomeHelperLifecycle.SYNC_SIGNAL_NAME, GnomeHelperLifecycle.OBJECT_PATH,
        None, Gio.DBusSignalFlags.NONE, sync,
    )

    def acquire():
        name_ready.clear()
        owner_id = Gio.bus_own_name_on_connection(
            helper, GnomeHelperLifecycle.BUS_NAME, Gio.BusNameOwnerFlags.NONE,
            lambda *_: name_ready.append(True), lambda *_: None,
        )
        until(lambda: name_ready)
        return owner_id

    owner_id = acquire() if already_active else None
    fallback = Mock(name="typing fallback")
    fallback.name = "test fallback"
    fallback.start.return_value = True
    downloads = Mock(name="downloads")
    downloads.name = "test downloads"
    downloads.start.return_value = True
    typing = TypingActivityMonitor(
        on_typing_activity=lambda: events.append("typing"),
        on_typing_stopped=lambda: events.append("typing stopped"),
        detector=TypingBurstDetector(minimum_start_span_seconds=0,
                                    stop_delay_seconds=0.05),
        backends=[GnomeShellTypingPulseBackend(), fallback],
    )
    presence = PresenceActivityMonitor(
        on_user_idle=lambda: events.append("idle"),
        on_user_active=lambda: events.append("active"),
    )
    files = FileActivityMonitor(
        on_file_activity_started=lambda: events.append("files"),
        on_file_activity_stopped=lambda: events.append("files stopped"),
        downloads_backend=downloads,
    )
    categories = AppCategorySignalAdapter(
        on_category_changed=lambda category: events.append(category),
    )
    media_backend = MprisMediaBackend()
    # Playback is independent of helper availability; only its focus half is
    # under test. Model one playing browser without creating an MPRIS service.
    def sample_media():
        media_backend._watching_via_youtube_focus = media_backend._youtube_focused
        return media_backend._youtube_focused
    media_backend.sample_youtube_playing = sample_media
    media = MediaActivityMonitor(
        on_youtube_started=lambda: events.append("watching"),
        on_youtube_stopped=lambda: events.append("watching stopped"),
        backend=media_backend,
    )
    shortcut = DeveloperShortcutMonitor(
        on_requested=lambda: events.append("shortcut"),
    )
    monitors = [typing, presence, files, categories, media, shortcut]
    for monitor in monitors:
        monitor.start()
    if not already_active:
        assert typing.backend_name == "test fallback"
        assert files.available and not files.file_context_available
        assert not presence.available and not categories.available

    buddy = SimpleNamespace(
        _presence_shutting_down=False, _typing_monitor=typing,
        _presence_monitor=presence, _file_activity_monitor=files,
        _app_category_monitor=categories, _media_monitor=media,
        _developer_shortcut_monitor=shortcut,
        _presence_source_id=None, _presence_startup_source_id=None,
        _cancel_vscode_cowork_source=lambda: None,
        _system_signal_monitor=None, _presence_bubble=None,
    )
    watcher = GnomeHelperLifecycle(
        on_available=lambda: PresenceBuddyMixin._on_gnome_helper_available(buddy),
        on_unavailable=lambda: PresenceBuddyMixin._on_gnome_helper_unavailable(buddy),
    )
    buddy._gnome_helper_lifecycle = watcher
    assert watcher.start()
    if owner_id is None:
        # The initial absent callback reconciles failed adapters without closing
        # the independent Downloads, MPRIS, or fallback paths.
        until(lambda: watcher._owner_known)
        assert not watcher.available
        assert files.available and media.available and typing.available
        owner_id = acquire()

    for cycle in range(2):
        until(lambda: categories.category == "editor" and media.youtube_playing
              and files.file_activity_active and presence._user_idle)
        assert len(syncs) == cycle + 1
        assert typing.backend_name == GnomeShellTypingPulseBackend.name
        assert events.count("files") == cycle + 1
        assert events.count("idle") == cycle + 1
        assert events.count("watching") == cycle + 1

        # A replay must not repeat semantic callbacks or synthesize typing.
        previous = list(events)
        sync()
        emit("DeveloperMenuRequested")  # barrier after replay signals
        until(lambda: events.count("shortcut") == cycle + 1)
        assert events == previous + ["shortcut"]
        syncs.pop()  # only owner-triggered requests are counted above
        for _ in range(5):
            emit("Pulse")
        until(lambda: events.count("typing stopped") == cycle + 1)
        assert events.count("typing") == cycle + 1

        Gio.bus_unown_name(owner_id)
        until(lambda: not watcher.available)
        assert typing.backend_name == "test fallback"
        assert not files.file_activity_active and files.available
        assert not media.youtube_playing and media.available
        assert categories.category == "unknown"
        assert events.count("files stopped") == cycle + 1
        assert events.count("watching stopped") == cycle + 1
        owner_id = acquire()

    until(lambda: categories.category == "editor")
    PresenceBuddyMixin._shutdown_presence(buddy)
    PresenceBuddyMixin._shutdown_presence(buddy)
    assert watcher._watch_id is None
    assert all(not monitor.available for monitor in monitors)
    previous = list(events)
    sync()
    emit("Pulse")
    emit("DeveloperMenuRequested")
    helper.flush_sync(None)
    # A bus round trip and a main-loop drain must not deliver stopped callbacks.
    helper.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                     "org.freedesktop.DBus", "ListNames", None, None,
                     Gio.DBusCallFlags.NONE, 1000, None)
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    assert events == previous
    downloads.start.assert_called_once()
    downloads.stop.assert_called_once()
    helper.signal_unsubscribe(request_id)
    Gio.bus_unown_name(owner_id)
    helper.close_sync(None)


if __name__ == "__main__":
    _exercise(sys.argv[1] == "active")
