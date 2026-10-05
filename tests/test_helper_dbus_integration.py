"""Opt-in real Gio/GJS lifecycle check on a private session-bus name.

Run with MOCHI_RUN_DBUS_TESTS=1 python -m pytest tests/test_helper_dbus_integration.py.
The installed GNOME helper and its bus name are never modified.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import pytest

from mochi.file_activity import GnomeShellFileContextBackend
from mochi.helper_connection import HelperConnection
from mochi.media_activity import MprisMediaBackend
from mochi.presence.signals import AppCategorySignalAdapter
from mochi.presence_activity import GnomeShellPresenceBackend
from mochi.typing_activity import GnomeShellTypingPulseBackend


@pytest.mark.skipif(
    os.environ.get("MOCHI_RUN_DBUS_TESTS") != "1",
    reason="requires opt-in access to a session bus and GJS",
)
def test_real_helper_lifecycle(tmp_path, monkeypatch):
    pytest.importorskip("gi")
    from gi.repository import GLib

    if shutil.which("gjs") is None:
        pytest.skip("GJS is unavailable")
    name = f"io.github.mochi_desktop.LifecycleTest.p{os.getpid()}"
    monkeypatch.setattr(HelperConnection, "BUS_NAME", name)

    # Use the production export definition and method, without importing Shell
    # or touching desktop input. The fixture supplies only semantic state.
    extension = (
        Path(__file__).resolve().parents[1]
        / "gnome-extension/mochi-typing@miflow13/extension.js"
    ).read_text()
    export = extension[
        extension.index("        this._dbusObject ="):
        extension.index("        this._nameOwnerId = Gio.bus_own_name_on_connection(")
    ]
    method = extension[
        extension.index("    GetState() {"):
        extension.index("    _emitSignal(signalName)")
    ]
    script = tmp_path / "helper.js"
    script.write_text(
        "const {Gio, GLib} = imports.gi;\n"
        f"const BUS_NAME = '{name}';\n"
        f"const INTERFACE_NAME = '{HelperConnection.INTERFACE}';\n"
        f"const OBJECT_PATH = '{HelperConnection.OBJECT_PATH}';\n"
        "class Helper {\n"
        "  constructor() {\n"
        "    this._connection = Gio.DBus.session;\n"
        "    this._presenceIsIdle = true;\n"
        "    this._fileBrowsingActive = true;\n"
        "    this._youtubeFocusedActive = true;\n"
        "    this._appCategory = 'terminal';\n"
        + export + "\n  }\n" + method + "\n}\n"
        "const helper = new Helper();\n"
        "let owner = 0;\n"
        "function toggle() {\n"
        "  if (owner) {\n"
        "    Gio.bus_unown_name(owner); owner = 0;\n"
        "  } else {\n"
        "    owner = Gio.bus_own_name_on_connection(helper._connection, BUS_NAME,\n"
        "      Gio.BusNameOwnerFlags.NONE, () => print('ready'), () => {});\n"
        "  }\n"
        "  return GLib.SOURCE_CONTINUE;\n"
        "}\n"
        "GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 10, toggle);\n"
        "toggle();\n"
        "new GLib.MainLoop(null, false).run();\n"
    )
    events = {key: [] for key in ("presence", "files", "category", "video", "typing")}
    presence = GnomeShellPresenceBackend()
    files = GnomeShellFileContextBackend()
    category = AppCategorySignalAdapter(on_category_changed=events["category"].append)
    media = MprisMediaBackend()
    media.set_youtube_focus_changed_callback(events["video"].append)
    typing = GnomeShellTypingPulseBackend()
    adapters = (presence, files, category, media, typing)

    def start_adapters():
        assert presence.start(
            lambda: events["presence"].append(True),
            lambda: events["presence"].append(False),
        ), presence.last_error
        assert files.start(
            lambda: events["files"].append(True),
            lambda: events["files"].append(False),
        ), files.last_error
        assert category.start(), category.last_error
        assert media.start(), media.last_error
        assert typing.start(lambda: events["typing"].append(True)), typing.last_error

    context = GLib.MainContext.default()

    def wait_for(predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            while context.pending():
                context.iteration(False)
            if predicate():
                return
            time.sleep(0.01)
        pytest.fail(f"Lifecycle timeout: {events}")

    def connected():
        return all(adapter._helper.active for adapter in adapters)

    def disconnected():
        return not any(adapter._helper.active for adapter in adapters)

    def assert_current_state():
        assert events["presence"][-1] is True
        assert events["files"][-1] is True
        assert events["category"][-1] == "terminal"
        assert events["video"][-1] is True
        assert events["typing"] == []  # State sync must never invent a key pulse.
        assert [len(adapter._helper._subscriptions) for adapter in adapters] == [2, 2, 2, 3, 1]
        assert all(adapter._helper.last_error is None for adapter in adapters)

    def assert_cleared_state():
        assert events["presence"][-1] is False
        assert events["files"][-1] is False
        assert events["category"][-1] == "unknown"
        assert events["video"][-1] is False
        assert all(not adapter._helper._subscriptions for adapter in adapters)
        assert media.active  # The MPRIS bus connection survives helper loss.

    helper = None
    try:
        start_adapters()
        for process_cycle in range(2):
            helper = subprocess.Popen(
                ["gjs", str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            wait_for(connected)
            assert_current_state()
            if process_cycle == 0:
                # GNOME extension disable/enable reuses Shell's unique owner.
                original_owner = presence._helper._owner
                for _ in range(2):
                    helper.send_signal(signal.SIGUSR1)
                    wait_for(disconnected)
                    assert_cleared_state()
                    helper.send_signal(signal.SIGUSR1)
                    wait_for(connected)
                    assert presence._helper._owner == original_owner
                    assert_current_state()
                # Also exercise Mochi starting while the helper already exists.
                for adapter in adapters:
                    adapter.stop()
                start_adapters()
                wait_for(connected)
                assert_current_state()
            helper.terminate()
            helper.communicate(timeout=5)
            helper = None
            wait_for(disconnected)
            assert_cleared_state()
        # Five attachments, each with one snapshot and one loss notification.
        for key in ("presence", "files", "video"):
            assert events[key] == [True, False] * 5
        assert events["category"] == ["terminal", "unknown"] * 5
    finally:
        for adapter in adapters:
            adapter.stop()
        if helper is not None:
            helper.terminate()
            helper.communicate(timeout=5)
