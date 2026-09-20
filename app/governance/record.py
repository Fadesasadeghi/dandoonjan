"""Provenance + audit helpers (Append-only audit; field-level provenance)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.enums import TruthType
from app.domain.models import AuditEvent, ProvenanceRecord, public_id


def create_provenance(db: Session, *, truth_type: TruthType, artifact_id: int | None = None,
                      page: int | None = None, source_span: str | None = None,
                      bounding_box: str | None = None,
                      model_run_id: int | None = None, confidence: float | None = None,
                      description: str = "") -> ProvenanceRecord:
    record = ProvenanceRecord(
        public_id=public_id("PRV"),
        artifact_id=artifact_id, page=page, source_span=source_span,
        bounding_box=bounding_box, model_run_id=model_run_id, confidence=confidence,
        truth_type=truth_type, description=description[:500],
    )
    db.add(record)
    db.flush()
    return record


def audit(db: Session, event_type: str, case_id: int | None = None,
          actor: str = "system", **detail) -> None:
    """Append-only. Never log raw file content or secrets."""
    db.add(AuditEvent(event_type=event_type, case_id=case_id, actor=actor, detail=detail))
