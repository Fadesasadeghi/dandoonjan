"""Ingestion security tests."""
import pytest


def _ingest(db, case, data, filename="doc.pdf", mime="application/pdf"):
    from app.core.artifacts.ingestion import ingest_artifact
    return ingest_artifact(db, case, filename, mime, data)


def test_valid_pdf_ingests(db, case, pdf_bytes):
    result = _ingest(db, case, pdf_bytes)
    assert result.artifact.sha256
    assert result.artifact.storage_key
    assert result.artifact.immutable


def test_duplicate_same_content(db, case, pdf_bytes):
    first = _ingest(db, case, pdf_bytes)
    second = _ingest(db, case, pdf_bytes)
    assert second.duplicate_of == first.artifact.public_id


def test_unsupported_type_rejected(db, case):
    from app.errors import UnsupportedArtifactError
    with pytest.raises(UnsupportedArtifactError):
        _ingest(db, case, b"PK\x03\x04-zip-content", filename="evil.zip")


def test_malformed_pdf_rejected(db, case):
    from app.errors import UnreadableArtifactError
    with pytest.raises(UnreadableArtifactError):
        _ingest(db, case, b"%PDF-1.4 broken", filename="broken.pdf")


def test_empty_file_rejected(db, case):
    from app.errors import UnreadableArtifactError
    with pytest.raises(UnreadableArtifactError):
        _ingest(db, case, b"")


def test_storage_keys_opaque_and_no_original_path(db, case, pdf_bytes):
    result = _ingest(db, case, pdf_bytes, filename="../../etc/passwd.pdf")
    assert ".." not in result.artifact.storage_key
    assert result.artifact.original_filename == "../../etc/passwd.pdf"  # preserved as label
    assert "/etc/" not in result.artifact.storage_key
