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
