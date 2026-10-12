from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.config import DocumentStorageDriver, get_settings


@dataclass(slots=True)
class StoredArtifact:
    key: str
    content: bytes


class DocumentStorage:
    def write_bytes(self, key: str, content: bytes) -> None:
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError


class LocalDocumentStorage(DocumentStorage):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, key: str, content: bytes) -> None:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as handle:
            handle.write(content)

    def read_bytes(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class AzureBlobDocumentStorage(DocumentStorage):
    def __init__(self) -> None:
        raise NotImplementedError(
            "Azure document storage is intentionally unavailable until it is validated "
            "against Azurite in this repository."
        )


def get_document_storage() -> DocumentStorage:
    settings = get_settings()
    if settings.document_storage_driver == DocumentStorageDriver.AZURE:
        return AzureBlobDocumentStorage()
    return LocalDocumentStorage(settings.document_storage_root)


def exclusive_path_exists(path: Path) -> bool:
    try:
        os.stat(path)
    except FileNotFoundError:
        return False
    return True

