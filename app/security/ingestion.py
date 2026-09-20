"""Secure artifact storage. Opaque keys, content-addressed, never overwritten."""
from __future__ import annotations

import os
import re
import shutil
import uuid

from app.config import get_settings
from app.errors import StorageError

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    base = os.path.basename(name or "file")
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "file"
    return cleaned[:180]


def store_bytes(case_public_id: str, filename: str, data: bytes) -> str:
    """Write bytes under an opaque storage key. Same content may repeat (duplicate
    awareness is upstream); keys are unique so files are never overwritten."""
    settings = get_settings()
    root = os.path.abspath(settings.artifact_storage_dir)
    key = f"cases/{case_public_id}/{uuid.uuid4().hex}/{sanitize_filename(filename)}"
    path = os.path.join(root, key)
    if not os.path.abspath(path).startswith(root):
        raise StorageError("path traversal rejected")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError as exc:
        raise StorageError(str(exc)) from exc
    return key


def read_bytes(storage_key: str) -> bytes:
    root = os.path.abspath(get_settings().artifact_storage_dir)
    path = os.path.join(root, storage_key)
    if not os.path.abspath(path).startswith(root):
        raise StorageError("path traversal rejected")
    if not os.path.exists(path):
        raise StorageError("artifact missing from storage")
    with open(path, "rb") as fh:
        return fh.read()
