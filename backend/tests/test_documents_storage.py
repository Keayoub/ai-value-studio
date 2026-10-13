from __future__ import annotations

from pathlib import Path

import pytest
from app.documents.storage import LocalDocumentStorage


def test_local_document_storage_allows_nested_relative_paths(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / "documents")

    storage.write_bytes("nested/folder/report.txt", b"safe")

    assert storage.read_bytes("nested/folder/report.txt") == b"safe"


@pytest.mark.parametrize(
    "key",
    [str(Path("/").joinpath("tmp", "escape.txt")), "../escape.txt", "nested/../escape.txt"],
)
def test_local_document_storage_rejects_absolute_and_traversal_paths(
    tmp_path: Path, key: str
) -> None:
    storage = LocalDocumentStorage(tmp_path / "documents")

    with pytest.raises(ValueError, match="document storage root"):
        storage.write_bytes(key, b"blocked")
    with pytest.raises(ValueError, match="document storage root"):
        storage.read_bytes(key)


def test_local_document_storage_rejects_symlink_parent_escape_on_write(tmp_path: Path) -> None:
    storage_root = tmp_path / "documents"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    storage = LocalDocumentStorage(storage_root)
    (storage_root / "linked").symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(ValueError, match="document storage root"):
        storage.write_bytes("linked/escape.txt", b"blocked")


def test_local_document_storage_rejects_symlink_file_escape_on_write(tmp_path: Path) -> None:
    storage_root = tmp_path / "documents"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    storage = LocalDocumentStorage(storage_root)

    outside_file = outside_root / "escape.txt"
    outside_file.write_bytes(b"secret")
    (storage_root / "escape.txt").symlink_to(outside_file)

    with pytest.raises(ValueError, match="document storage root"):
        storage.write_bytes("escape.txt", b"blocked")


def test_local_document_storage_rejects_symlink_escapes_on_read(tmp_path: Path) -> None:
    storage_root = tmp_path / "documents"
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    storage = LocalDocumentStorage(storage_root)

    outside_file = outside_root / "escape.txt"
    outside_file.write_bytes(b"secret")
    (storage_root / "linked").symlink_to(outside_root, target_is_directory=True)
    safe_parent = storage_root / "nested"
    safe_parent.mkdir()
    (safe_parent / "escape.txt").symlink_to(outside_file)

    with pytest.raises(ValueError, match="document storage root"):
        storage.read_bytes("linked/escape.txt")
    with pytest.raises(ValueError, match="document storage root"):
        storage.read_bytes("nested/escape.txt")
