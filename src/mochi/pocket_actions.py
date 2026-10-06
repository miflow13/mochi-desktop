"""GTK-free rules for what Pocket hands to the desktop."""

from __future__ import annotations

from pathlib import Path

from mochi.pocket import PocketItem, PocketItemKind


def launch_uri_for(item: PocketItem) -> str:
    """Return the only URI Pocket may launch for this item.

    URL items were validated as HTTP(S) when they entered the Pocket. Files
    and saved images launch as file URIs. Text is never launched.
    """
    if item.kind is PocketItemKind.URL:
        return item.value
    if item.kind is PocketItemKind.TEXT:
        raise ValueError("Pocket text is viewed or copied, never launched")
    return Path(item.value).as_uri()


def folder_uri_for(item: PocketItem) -> str:
    """Return the containing folder of a local Pocket file."""
    if item.kind is not PocketItemKind.LOCAL_FILE:
        raise ValueError("Only local Pocket files have a containing folder")
    return Path(item.value).parent.as_uri()
