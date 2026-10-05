"""Secure ingestion: treat every upload as untrusted. (Phase 2)"""
from __future__ import annotations

import hashlib
import json
import io
from types import SimpleNamespace
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
    return "application/octet-stream"


@dataclass
class IngestResult:
    artifact: Artifact
    duplicate_of: str | None = None


def ingest_artifact(db: Session, case: Case, filename: str, declared_mime: str,
                    data: bytes, document_role: str = 'unspecified') -> IngestResult:
    settings = get_settings()
    if len(data) == 0:
        raise UnreadableArtifactError("empty file", user_message_fa='فایل خالی است؛ فایل خوانا و غیرخالی انتخاب کنید.')
    if len(data) > settings.max_upload_bytes:
        limit = str(settings.max_upload_bytes // (1024*1024)).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
        raise UnsupportedArtifactError("file too large", user_message_fa=f"حجم فایل بیش از حد مجاز {limit} مگابایت (MiB) است.")

    detected = sniff_mime(data, filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in EXT_TO_MIME:
        raise UnsupportedArtifactError('unsupported extension')
    if ext == 'txt':
        try:
            data.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise UnreadableArtifactError('invalid UTF-8', user_message_fa='TXT باید با رمزگذاری UTF-8 قابل خواندن باشد.') from exc
    if detected != EXT_TO_MIME[ext]:
        raise UnsupportedArtifactError(f"unsupported content type: {detected}", user_message_fa='محتوای واقعی فایل با پسوند آن تطابق ندارد یا پشتیبانی نمی‌شود.')
    claimed = declared_mime.split(';', 1)[0].strip().lower()
    if claimed not in ('', 'application/octet-stream') and claimed != detected:
        raise UnsupportedArtifactError('declared MIME mismatch', user_message_fa='نوع اعلام‌شدهٔ فایل با محتوای واقعی آن تطابق ندارد.')

    sha256 = hashlib.sha256(data).hexdigest()

    # basic malformed-file detection
    if detected == "application/pdf":
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass or doc.is_encrypted or (doc.metadata or {}).get('encryption'):
                    raise UnreadableArtifactError('encrypted PDF', user_message_fa='PDF رمزگذاری‌شده یا دارای گذرواژه پشتیبانی نمی‌شود؛ نسخهٔ بدون رمز را بارگذاری کنید.')
                if doc.page_count == 0:
                    raise UnreadableArtifactError("empty pdf")
        except UnreadableArtifactError:
            raise
        except Exception as exc:
            raise UnreadableArtifactError(f"malformed pdf: {exc}") from exc
    elif detected.startswith("image/"):
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.format != ('PNG' if detected == 'image/png' else 'JPEG'):
                    raise UnreadableArtifactError('image format mismatch')
                img.verify()
            from app.core.cases.dossier import latest
            # Reviewed cases decode through bounded derivative preparation below.
            if latest(case) is None:
                with Image.open(io.BytesIO(data)) as img:
                    img.load()
        except Exception as exc:
            raise UnreadableArtifactError(f"malformed image: {exc}") from exc
    elif detected == 'text/plain':
        text_content = data.decode('utf-8-sig')
        if not text_content.strip() or '\x00' in text_content:
            raise UnreadableArtifactError('empty or binary TXT', user_message_fa='TXT باید متن خوانای UTF-8 و غیرخالی باشد و نویسهٔ NUL نداشته باشد.')

    # duplicate awareness (same case, same hash)
    existing = (db.query(Artifact)
                .filter(Artifact.case_id == case.id, Artifact.sha256 == sha256)
                .first())
    if existing:
        return IngestResult(artifact=existing, duplicate_of=existing.public_id)

    # Review preparation is side-effect-free and provider-independent. The API
    # holds the case lock through its transaction, including this measurement.
    from app.core.cases.dossier import latest
    if latest(case) is not None:
        from app.ai.multimodal import bundle
        candidate = SimpleNamespace(public_id='candidate', detected_mime_type=detected,
            document_role=document_role, sha256=sha256, text_content=data.decode('utf-8-sig') if detected == 'text/plain' else None)
        def read(artifact):
            return data if artifact is candidate else storage.read_bytes(artifact.storage_key)
        # Persisted text may not yet have been extracted by processing.
        artifacts = []
        for artifact in case.artifacts:
            artifacts.append(SimpleNamespace(public_id=artifact.public_id,
                detected_mime_type=artifact.detected_mime_type, document_role=artifact.document_role,
                sha256=artifact.sha256, storage_key=artifact.storage_key,
                text_content=artifact.text_content if artifact.text_content is not None else
                    extract_text_if_supported(artifact, storage.read_bytes(artifact.storage_key))))
        try:
            bundle(case, artifacts=[*artifacts, candidate], read_artifact=read)
        except ValueError as exc:
            raise UnsupportedArtifactError(str(exc), user_message_fa='این فایل یا مجموع مدارک از ظرفیت پردازش فعلی فراتر می‌رود (PDF تا ۸ صفحه، تصویر تا ۲۰ میلیون پیکسل، مجموع تا ۱۶ تصویر و ۱۲ MiB مشتق، ۱۰۰ هزار نویسه و ۱۰۰ منبع).') from exc

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


TEXT_EXTRACTION_LIMIT = 20001  # 20k input plus one explicit truncation sentinel.


def pdf_text_pages_bounded(data: bytes) -> list[str]:
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        if doc.needs_pass or doc.is_encrypted or (doc.metadata or {}).get('encryption'):
            raise UnreadableArtifactError('encrypted PDF')
        pages, remaining = [], TEXT_EXTRACTION_LIMIT
        for page in doc:
            if pages:
                remaining -= 1  # Joining newline belongs to the extraction budget.
            if remaining <= 0: break
            value = page.get_text()[:remaining]
            pages.append(value)
            remaining -= len(value)
        return pages


def extract_text_if_supported(artifact: Artifact, data: bytes) -> str | None:
    """Extracted text is DATA only. Never interpreted as instructions downstream."""
    if artifact.detected_mime_type == "application/pdf":
        try:
            return "\n".join(pdf_text_pages_bounded(data))
        except Exception as exc:
            raise UnreadableArtifactError(str(exc)) from exc
    if artifact.detected_mime_type == "text/plain":
        return data.decode("utf-8-sig")[:TEXT_EXTRACTION_LIMIT]
    return None


def describe_for_ai(artifact: Artifact) -> str:
    """Fenced content envelope: metadata header + document body (untrusted DATA)."""
    meta = json.dumps({"mime": artifact.detected_mime_type,
                       "filename": artifact.original_filename})
    body = (artifact.text_content or "")[:20000]
    return f"{meta}\n{body}"
