"""Static contract checks for the GNOME Shell helper: global shortcuts and the
AmbiSense focus and tab-pulse contracts, including the installer copy list."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "gnome-extension" / "mochi-typing@miflow13"


def test_emote_catalogue_shortcut_is_registered_and_removed() -> None:
    source = (EXTENSION / "extension.js").read_text(encoding="utf-8")

    assert "EMOTE_CATALOGUE_KEYBINDING = 'emote-catalogue-shortcut'" in source
    assert "EMOTE_CATALOGUE_SIGNAL_NAME = 'EmoteCatalogueRequested'" in source
    assert "Main.wm.addKeybinding(\n            EMOTE_CATALOGUE_KEYBINDING" in source
    assert "Main.wm.removeKeybinding(EMOTE_CATALOGUE_KEYBINDING)" in source


def test_emote_catalogue_shortcut_default_is_ctrl_alt_e() -> None:
    schema = (
        EXTENSION
        / "schemas"
        / "org.gnome.shell.extensions.mochi-activity.gschema.xml"
    ).read_text(encoding="utf-8")

    assert 'name="emote-catalogue-shortcut"' in schema
    assert "&lt;Ctrl&gt;&lt;Alt&gt;e" in schema


def test_focus_curiosity_pulse_requires_actual_window_change() -> None:
    source = (EXTENSION / "extension.js").read_text(encoding="utf-8")

    assert "this._lastFocusedWindow = global.display.get_focus_window();" in source
    assert "if (focusedWindow === this._lastFocusedWindow)" in source
    assert "this._lastFocusedWindow = focusedWindow;" in source
    assert "if (focusedWindow !== null)" in source
    assert "this._emitAppFocus(category);" in source

    non_null_guard = source.index("if (focusedWindow !== null)")
    remembered_window = source.index(
        "this._lastFocusedWindow = focusedWindow;",
        non_null_guard,
    )
    emitted_focus = source.index("this._emitAppFocus(category);", remembered_window)
    assert non_null_guard < remembered_window < emitted_focus


def _extension_source() -> str:
    return (EXTENSION / "extension.js").read_text(encoding="utf-8")


def _method_body(source: str, signature: str) -> str:
    """Text from a method signature up to the next four-space-indented method."""
    start = source.index(signature)
    following = source.find("\n    _", start + len(signature))
    return source[start:] if following == -1 else source[start:following]


def _top_level_function(source: str, signature: str) -> str:
    """Text from a top-level function signature up to its closing brace."""
    start = source.index(signature)
    return source[start:source.index("\n}\n", start)]


def test_browser_tab_pulse_constants_are_declared() -> None:
    source = _extension_source()

    assert "const BROWSER_TAB_SIGNAL_NAME = 'BrowserTabChanged';" in source
    assert "const TAB_INPUT_WINDOW_MS = 2000;" in source
    assert "const TAB_TITLE_BADGE_PATTERN = /^\\(\\d+\\+?\\)\\s*/;" in source


def test_tab_pulse_gate_is_strictly_inside_the_input_window() -> None:
    gate = _top_level_function(_extension_source(), "function shouldEmitTabPulse(idleMs) {")

    # Exactly TAB_INPUT_WINDOW_MS of idle time is already too late, and the
    # bound must come from the shared constant rather than a copied number.
    assert "idleMs < TAB_INPUT_WINDOW_MS" in gate
    assert "Number.isFinite(idleMs)" in gate
    assert "idleMs >= 0" in gate
    assert "2000" not in gate


def test_tab_title_change_stores_digest_before_input_gate_and_emits_no_payload() -> None:
    handler = _method_body(_extension_source(), "_onBrowserTabTitleChanged() {")

    unchanged = handler.index(
        "if (digest === null || digest === this._tabTitleDigest)\n            return;"
    )
    stored = handler.index("this._tabTitleDigest = digest;")
    gated = handler.index("shouldEmitTabPulse(")
    emitted = handler.index("this._emitSignal(BROWSER_TAB_SIGNAL_NAME);")
    assert unchanged < stored < gated < emitted
    assert "get_idletime()" in handler
    # The gate must guard the emit, not merely precede it: a failed gate
    # returns, and the only emit is the last statement after it.
    assert handler.rstrip().endswith(
        "        if (!shouldEmitTabPulse(Number(this._idleMonitor.get_idletime())))\n"
        "            return;\n"
        "\n"
        "        this._emitSignal(BROWSER_TAB_SIGNAL_NAME);\n"
        "    }"
    )
    assert handler.count("_emitSignal(") == 1


def test_unreadable_tab_baseline_is_adopted_without_a_pulse() -> None:
    handler = _method_body(_extension_source(), "_onBrowserTabTitleChanged() {")

    # A null baseline means the old title could not be read, so the first
    # readable title becomes the baseline instead of counting as a change.
    checked = handler.index("const hadBaseline = this._tabTitleDigest !== null;")
    stored = handler.index("this._tabTitleDigest = digest;")
    adopted = handler.index("if (!hadBaseline)\n            return;")
    gated = handler.index("shouldEmitTabPulse(")
    assert checked < stored < adopted < gated


def test_tab_titles_are_reduced_to_a_digest_and_never_leave_the_shell() -> None:
    source = _extension_source()
    digest = _method_body(source, "_tabTitleDigestFor(window) {")
    tracking = (
        digest
        + _method_body(source, "_trackBrowserTabTitle(window, category) {")
        + _method_body(source, "_onBrowserTabTitleChanged() {")
    )

    assert "GLib.ChecksumType.SHA256" in digest
    assert "normalizeTabTitle(" in digest
    # The title is a local of the digest helper only: no field, no state.
    assert "this." not in digest
    assert "console." not in tracking
    assert "GLib.Variant" not in tracking
    assert "this._tabTitle =" not in source


def test_tab_title_tracking_is_browser_only_and_cleaned_up() -> None:
    source = _extension_source()
    track = _method_body(source, "_trackBrowserTabTitle(window, category) {")
    untrack = _method_body(source, "_untrackBrowserTabTitle() {")
    disable = source[source.index("    disable() {"):]

    assert "category === 'browser' ? window : null" in track
    assert "'notify::title'" in track
    assert "this._trackBrowserTabTitle(focusedWindow, category);" in source
    # Initial sync, before the heartbeat exists, so an already focused browser
    # is tracked at enable() instead of up to one heartbeat later.
    assert (
        "        this._updateAppCategory();\n"
        "        this._trackBrowserTabTitle(global.display.get_focus_window(), this._appCategory);\n"
        "        this._videoFocusHeartbeatId = GLib.timeout_add("
    ) in source
    assert "this._tabWindow.disconnect(this._tabTitleChangedId);" in untrack
    assert "this._tabWindow = null;" in untrack
    assert "this._tabTitleChangedId = 0;" in untrack
    assert "this._tabTitleDigest = null;" in untrack
    assert "this._untrackBrowserTabTitle();" in disable


def test_leaving_media_for_a_tab_in_the_same_window_pulses_behind_the_input_gate() -> None:
    track = _method_body(_extension_source(), "_trackBrowserTabTitle(window, category) {")

    # media (a YouTube tab) -> browser in the SAME window is a tab change.
    # Any other window becoming the target is a window switch.
    # Heartbeats with an unchanged target AND pause change nothing.
    unchanged = track.index(
        "if (target === this._tabWindow && paused === this._tabPausedWindow)\n"
        "            return;"
    )
    # Read the pause before untracking clears it.
    resuming = track.index(
        "const resuming = target !== null && target === this._tabPausedWindow;"
    )
    released = track.index("this._untrackBrowserTabTitle();")
    baseline = track.index("this._tabTitleDigest = this._tabTitleDigestFor(target);")
    # The gate must guard the emit, not merely precede it: only a resume with
    # a readable baseline reaches the gate, and the only emit sits inside it.
    assert track.rstrip().endswith(
        "        if (!resuming || this._tabTitleDigest === null || this._idleMonitor === null)\n"
        "            return;\n"
        "        if (shouldEmitTabPulse(Number(this._idleMonitor.get_idletime())))\n"
        "            this._emitSignal(BROWSER_TAB_SIGNAL_NAME);\n"
        "    }"
    )
    gated = track.index("if (!resuming || this._tabTitleDigest === null")
    assert unchanged < released
    assert resuming < released < baseline < gated
    assert track.count("_emitSignal(") == 1


def test_media_pause_keeps_only_a_window_reference_and_is_released() -> None:
    source = _extension_source()
    enable = source[source.index("    enable() {"):source.index("    GetState() {")]
    track = _method_body(source, "_trackBrowserTabTitle(window, category) {")
    untrack = _method_body(source, "_untrackBrowserTabTitle() {")
    disable = source[source.index("    disable() {"):]

    assert "this._tabPausedWindow = null;" in enable
    # ANY focused media window pauses, whether or not it was tracked as a
    # browser first: focus can land straight on a YouTube tab. Pausing
    # returns before any title is read, so a media window's title is never
    # digested here.
    assert "const paused = category === 'media' ? window : null;" in track
    pause = track.index(
        "        this._untrackBrowserTabTitle();\n"
        "        if (paused !== null) {\n"
        "            this._tabPausedWindow = paused;\n"
        "            return;\n"
        "        }"
    )
    assert pause < track.index("this._tabTitleDigestFor(target)")
    assert track.count("_tabTitleDigestFor(") == 1
    assert set(re.findall(r"this\._tabPausedWindow = ([^;]+);", source)) == {
        "null",
        "paused",
    }
    # disable() releases the paused reference through the untrack helper.
    assert "this._tabPausedWindow = null;" in untrack
    assert "this._untrackBrowserTabTitle();" in disable


def test_category_heartbeat_resyncs_tab_tracking() -> None:
    source = _extension_source()
    start = source.index("VIDEO_FOCUS_HEARTBEAT_MS,")
    heartbeat = source[start:source.index("GLib.SOURCE_CONTINUE", start)]

    # A window can be focused before its identity classifies as a browser.
    assert "this._updateAppCategory();" in heartbeat
    assert (
        "this._trackBrowserTabTitle(global.display.get_focus_window(), this._appCategory);"
        in heartbeat
    )


def test_install_script_copies_every_extension_module() -> None:
    script = (ROOT / "scripts" / "install-typing-extension.sh").read_text(encoding="utf-8")
    copy_line = next(
        line
        for line in script.splitlines()
        if line.lstrip().startswith("cp ") and "extension.js" in line
    )

    modules = sorted(path.name for path in EXTENSION.glob("*.js"))
    assert modules, "expected at least extension.js"
    for module in modules:
        assert f'"$SOURCE_DIR/{module}"' in copy_line, (
            f"{module} would be left out of the installed extension"
        )
