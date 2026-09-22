"""Secure artifact storage. Opaque keys, content-addressed, never overwritten."""
from __future__ import annotations

import os
from pathlib import Path
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


def _contained_path(root: Path, candidate: Path) -> Path:
    """Resolve existing parents/symlinks even when the final file is new.

    Callers must use the returned path for I/O, not the unresolved candidate.
    The root is already resolved and stays fixed throughout the operation.
    """
    path = candidate.resolve()
    if not path.is_relative_to(root):
        raise StorageError("path traversal rejected")
    return path


def store_bytes(case_public_id: str, filename: str, data: bytes) -> str:
    """Write bytes under an opaque storage key. Same content may repeat (duplicate
    awareness is upstream); keys are unique so files are never overwritten."""
    key = f"cases/{case_public_id}/{uuid.uuid4().hex}/{sanitize_filename(filename)}"
    try:
        root = Path(get_settings().artifact_storage_dir).resolve()
        path = _contained_path(root, root / key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Recheck the created parents, and open the resolved target rather than
        # following the original key through any symlink alias again.
        path = _contained_path(root, path)
        with path.open("xb") as fh:
            fh.write(data)
    except (OSError, RuntimeError) as exc:
        raise StorageError(str(exc)) from exc
    return key


def read_bytes(storage_key: str) -> bytes:
    try:
        root = Path(get_settings().artifact_storage_dir).resolve()
        path = _contained_path(root, root / storage_key)
        if not path.exists():
            raise StorageError("artifact missing from storage")
        with path.open("rb") as fh:
            return fh.read()
    except (OSError, RuntimeError) as exc:
        raise StorageError(str(exc)) from exc
