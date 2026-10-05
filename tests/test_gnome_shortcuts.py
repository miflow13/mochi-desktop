"""Static contract checks for Mochi's GNOME Shell global shortcuts."""

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


def test_browser_tab_pulse_constants_are_declared() -> None:
    source = _extension_source()

    assert "const BROWSER_TAB_SIGNAL_NAME = 'BrowserTabChanged';" in source
    assert "const TAB_INPUT_WINDOW_MS = 2000;" in source
    assert "const TAB_TITLE_BADGE_PATTERN = /^\\(\\d+\\+?\\)\\s*/;" in source


def test_tab_title_change_stores_digest_before_input_gate_and_emits_no_payload() -> None:
    handler = _method_body(_extension_source(), "_onBrowserTabTitleChanged() {")

    stored = handler.index("this._tabTitleDigest = digest;")
    gated = handler.index("shouldEmitTabPulse(")
    emitted = handler.index("this._emitSignal(BROWSER_TAB_SIGNAL_NAME);")
    assert stored < gated < emitted
    assert "get_idletime()" in handler


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
    assert "console." not in tracking
    assert "GLib.Variant" not in tracking
    assert "this._tabTitle =" not in source


def test_tab_title_tracking_is_browser_only_and_cleaned_up() -> None:
    source = _extension_source()
    track = _method_body(source, "_trackBrowserTabTitle(window, category) {")
    disable = source[source.index("    disable() {"):]

    assert "category === 'browser' ? window : null" in track
    assert "'notify::title'" in track
    assert "this._trackBrowserTabTitle(focusedWindow, category);" in source
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
