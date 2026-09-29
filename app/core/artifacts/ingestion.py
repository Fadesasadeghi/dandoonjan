"""Secure ingestion: treat every upload as untrusted. (Phase 2)"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pymupdf
from PIL import Image
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import ArtifactCategory
from app.domain.models import Artifact, Case
from app.errors import UnreadableArtifactError, UnsupportedArtifactError
from app.security import ingestion as storage

# Allowed MIME types (sniffed, not client-asserted)
SUPPORTED_MIMES = {
    "application/pdf": {"pdf"},
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/heic": {"heic"},
    "text/plain": {"txt"},
}

EXT_TO_MIME = {ext: mime for mime, exts in SUPPORTED_MIMES.items() for ext in exts}


def sniff_mime(data: bytes, filename: str) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "txt":
        try:
            data.decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            pass
    if ext == "heic":
        return "image/heic"
    return "application/octet-stream"


@dataclass
class IngestResult:
    artifact: Artifact
    duplicate_of: str | None = None


def ingest_artifact(db: Session, case: Case, filename: str, declared_mime: str,
                    data: bytes, document_role: str = 'unspecified') -> IngestResult:
    settings = get_settings()
    if len(data) == 0:
        raise UnreadableArtifactError("empty file")
    if len(data) > settings.max_upload_bytes:
        raise UnsupportedArtifactError("file too large")

    detected = sniff_mime(data, filename)
    if detected not in SUPPORTED_MIMES:
        raise UnsupportedArtifactError(f"unsupported content type: {detected}")

    sha256 = hashlib.sha256(data).hexdigest()

    # basic malformed-file detection
    if detected == "application/pdf":
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
            if doc.page_count == 0:
                raise UnreadableArtifactError("empty pdf")
            doc.close()
        except UnreadableArtifactError:
            raise
        except Exception as exc:
            raise UnreadableArtifactError(f"malformed pdf: {exc}") from exc
    elif detected.startswith("image/"):
        try:
            img = Image.open(__import__("io").BytesIO(data))
            img.verify()
        except Exception as exc:
            raise UnreadableArtifactError(f"malformed image: {exc}") from exc

    # duplicate awareness (same case, same hash)
    existing = (db.query(Artifact)
                .filter(Artifact.case_id == case.id, Artifact.sha256 == sha256)
                .first())
    if existing:
        return IngestResult(artifact=existing, duplicate_of=existing.public_id)

    key = storage.store_bytes(case.public_id, filename, data)
    artifact = Artifact(
        public_id=f"ART-{hashlib.sha1(key.encode()).hexdigest()[:12]}",
        case_id=case.id,
        original_filename=filename[:500],
        document_role=document_role,
        safe_filename=storage.sanitize_filename(filename),
        mime_type=declared_mime[:250],
        detected_mime_type=detected,
        file_size=len(data),
        sha256=sha256,
        storage_key=key,
        category=ArtifactCategory.UNKNOWN,
    )
    db.add(artifact)
    # Material case change: new artifact bumps Case version (P0-04-C)
    case.version = (case.version or 1) + 1
    db.flush()
    return IngestResult(artifact=artifact)


def extract_text_if_supported(artifact: Artifact, data: bytes) -> str | None:
    """Extracted text is DATA only. Never interpreted as instructions downstream."""
    if artifact.detected_mime_type == "application/pdf":
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
            pages = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(pages)
        except Exception as exc:
            raise UnreadableArtifactError(str(exc)) from exc
    if artifact.detected_mime_type == "text/plain":
        return data.decode("utf-8", errors="replace")
    return None


def describe_for_ai(artifact: Artifact) -> str:
    """Fenced content envelope: metadata header + document body (untrusted DATA)."""
    meta = json.dumps({"mime": artifact.detected_mime_type,
                       "filename": artifact.original_filename})
    body = (artifact.text_content or "")[:20000]
    return f"{meta}\n{body}"
