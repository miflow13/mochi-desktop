"""The only URIs Pocket hands to the desktop."""

from __future__ import annotations

from pathlib import Path

import pytest

from mochi.pocket import (
    make_local_file_item,
    make_saved_image_item,
    make_text_item,
    make_url_item,
)
from mochi.pocket_actions import folder_uri_for, launch_uri_for


def test_files_and_saved_images_launch_as_file_uris(tmp_path: Path) -> None:
    document = tmp_path / "notes v2.txt"
    document.write_text("hello")
    image = tmp_path / "drop.png"
    image.write_bytes(b"png")

    assert launch_uri_for(make_local_file_item(document)) == document.as_uri()
    assert launch_uri_for(make_saved_image_item(image)) == image.as_uri()


def test_urls_launch_their_validated_value() -> None:
    item = make_url_item("https://docs.gtk.org/gtk4/class.DragSource.html")

    uri = launch_uri_for(item)

    assert uri == item.value
    assert uri.startswith("https://")


def test_text_is_never_launched() -> None:
    with pytest.raises(ValueError):
        launch_uri_for(make_text_item("rm -rf ~"))


def test_folder_uri_is_the_parent_of_a_local_file(tmp_path: Path) -> None:
    document = tmp_path / "report.pdf"
    document.write_bytes(b"%PDF")

    assert folder_uri_for(make_local_file_item(document)) == tmp_path.as_uri()


def test_only_local_files_have_a_containing_folder(tmp_path: Path) -> None:
    image = tmp_path / "drop.png"
    image.write_bytes(b"png")
    for item in (
        make_url_item("https://example.org/"),
        make_text_item("hello"),
        make_saved_image_item(image),
    ):
        with pytest.raises(ValueError):
            folder_uri_for(item)
