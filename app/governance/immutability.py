"""Real immutability enforcement (P0-05).

A Boolean flag is not immutability. ORM event listeners reject, at flush time:
- ANY update to AssessmentSnapshot rows (append-only after creation);
- ANY update to AuditEvent rows (append-only audit);
- update of Artifact source-identity fields (storage_key, sha256, file_size,
  filenames, detected MIME). Metadata (category/subtype/text_content) stays mutable.

- DELETE of AssessmentSnapshot / AuditEvent / Artifact (explicit guards).

Also provides verify_snapshot_integrity() to detect content-hash tampering.

Known limitation (accepted for V0, docs/P0_1_DECISIONS_LOCK.md D-Q4): a privileged
database operator can bypass application architecture with raw SQL; the snapshot
integrity hash detects such tampering after the fact. Database-level triggers are
a reserved production-hardening path. Application code must not use ORM bulk
update/delete against protected entities (enforced by tests/test_immutability_static).
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import event
from sqlalchemy.orm import attributes

SNAPSHOT_PROTECTED_FIELDS = ("payload", "versions", "content_hash", "case_version",
                             "safety_state", "immutable", "case_id", "public_id")

ARTIFACT_IDENTITY_FIELDS = ("storage_key", "sha256", "file_size", "original_filename",
                            "safe_filename", "detected_mime_type")


class ImmutabilityViolationError(Exception):
    """Raised when protected immutable state is mutated through normal persistence."""


def snapshot_content_hash(payload: dict, versions: dict) -> str:
    canonical = json.dumps({"payload": payload, "versions": versions},
                           sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_snapshot_integrity(snapshot: AssessmentSnapshot) -> bool:
    """True iff stored content matches the hash frozen at creation time."""
    if not snapshot.content_hash:
        return False
    return snapshot_content_hash(snapshot.payload, snapshot.versions) == snapshot.content_hash


def _check_frozen(mapper, connection, target, protected_fields, entity):
    state = attributes.instance_state(target)
    history_map = {k: attributes.get_history(target, k) for k in protected_fields}
    for field, history in history_map.items():
        if history.has_changes():
            raise ImmutabilityViolationError(
                f"{entity}.{field} is immutable (row id={getattr(target, 'id', '?')}); "
                "create a new versioned row instead")


def _reject_delete(mapper, connection, target, entity):
    raise ImmutabilityViolationError(
        f"{entity} row (id={getattr(target, 'id', '?')}) is append-only; "
        "DELETE is forbidden")


def register_immutability_guards() -> None:
    # Imported lazily to avoid a circular import with app.domain.models
    from app.domain.models import Artifact, AssessmentSnapshot, AuditEvent, DossierRevision
    event.listen(DossierRevision, "before_update", lambda m, c, t: _check_frozen(
        m, c, t, tuple(col.name for col in DossierRevision.__table__.columns), "DossierRevision"))
    event.listen(DossierRevision, "before_delete",
                 lambda m, c, t: _reject_delete(m, c, t, "DossierRevision"))
    event.listen(AssessmentSnapshot, "before_update", lambda m, c, t: _check_frozen(
        m, c, t, SNAPSHOT_PROTECTED_FIELDS, "AssessmentSnapshot"))
    event.listen(AuditEvent, "before_update", lambda m, c, t: _check_frozen(
        m, c, t, ("event_type", "case_id", "actor", "detail"), "AuditEvent"))
    event.listen(Artifact, "before_update", lambda m, c, t: _check_frozen(
        m, c, t, ARTIFACT_IDENTITY_FIELDS, "Artifact"))
    event.listen(AssessmentSnapshot, "before_delete",
                 lambda m, c, t: _reject_delete(m, c, t, "AssessmentSnapshot"))
    event.listen(AuditEvent, "before_delete",
                 lambda m, c, t: _reject_delete(m, c, t, "AuditEvent"))
    event.listen(Artifact, "before_delete",
                 lambda m, c, t: _reject_delete(m, c, t, "Artifact"))
