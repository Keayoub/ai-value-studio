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
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, key: str, content: bytes) -> None:
        target = _resolve_storage_path(self.root, key, require_exists=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as handle:
            handle.write(content)

    def read_bytes(self, key: str) -> bytes:
        target = _resolve_storage_path(self.root, key, require_exists=True)
        return target.read_bytes()


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


def _resolve_storage_path(root: Path, key: str, *, require_exists: bool) -> Path:
    if not key.strip():
        raise ValueError("Storage key must stay within the document storage root.")

    key_path = Path(key)
    if key_path.is_absolute() or any(part in {"", ".", ".."} for part in key_path.parts):
        raise ValueError("Storage key must stay within the document storage root.")

    candidate = root.joinpath(*key_path.parts)
    _ensure_within_root(root, candidate.parent.resolve(strict=False))

    if require_exists:
        resolved_candidate = candidate.resolve(strict=True)
        _ensure_within_root(root, resolved_candidate)
        return resolved_candidate

    if candidate.exists():
        _ensure_within_root(root, candidate.resolve(strict=True))
    return candidate


def _ensure_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Storage key must stay within the document storage root.") from exc
