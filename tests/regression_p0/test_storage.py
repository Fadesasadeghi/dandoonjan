"""A: storage keys must resolve to true descendants, not string prefixes."""
from pathlib import Path

import pytest

from app.errors import StorageError
from app.security.ingestion import read_bytes, store_bytes


def test_storage_descendant_round_trip(regression_settings):
    key = store_bytes("CASE-synthetic", "plan.txt", b"synthetic evidence")
    root = Path(regression_settings.artifact_storage_dir).resolve()
    assert (root / key).resolve().is_relative_to(root)
    assert read_bytes(key) == b"synthetic evidence"


@pytest.mark.parametrize("escape", ["sibling-prefix", "parent", "absolute-outside",
                                     "absolute-sibling-prefix"])
def test_storage_read_rejects_escape(regression_settings, tmp_path, escape):
    root = Path(regression_settings.artifact_storage_dir)
    root.mkdir()
    outside = tmp_path / ("store-neighbor" if "sibling" in escape else "outside")
    outside.mkdir()
    target = outside / "private.txt"
    target.write_bytes(b"outside synthetic evidence")
    key = str(target) if escape.startswith("absolute") else f"../{outside.name}/private.txt"
    assert not target.resolve().is_relative_to(root.resolve())
    with pytest.raises(StorageError):
        read_bytes(key)
    assert target.read_bytes() == b"outside synthetic evidence"


@pytest.mark.parametrize("neighbor", ["store-neighbor", "outside"])
def test_storage_write_rejects_parent_escape(regression_settings, tmp_path, neighbor):
    outside = tmp_path / neighbor
    with pytest.raises(StorageError):
        store_bytes(f"../../{neighbor}", "plan.txt", b"must stay inside")
    assert not outside.exists(), "rejected storage write left files outside the root"


@pytest.mark.parametrize("operation", ["read", "write"])
def test_storage_rejects_symlink_escape(regression_settings, tmp_path, operation):
    root = Path(regression_settings.artifact_storage_dir)
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "private.txt"
    target.write_bytes(b"outside synthetic evidence")
    try:
        (root / "cases").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlinks unavailable on this platform: {exc}")
    before = sorted(p.relative_to(outside) for p in outside.rglob("*"))
    with pytest.raises(StorageError):
        if operation == "read":
            read_bytes("cases/private.txt")
        else:
            store_bytes("CASE-synthetic", "plan.txt", b"must stay inside")
    assert sorted(p.relative_to(outside) for p in outside.rglob("*")) == before
    assert target.read_bytes() == b"outside synthetic evidence"
