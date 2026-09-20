"""Centralized Case state machine. Invalid transitions are rejected (Phase 23 of spec)."""
from __future__ import annotations

from app.domain.enums import CaseStatus
from app.errors import InvalidTransitionError

ALLOWED_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.CREATED: {CaseStatus.INTAKE_COMPLETE, CaseStatus.CANCELLED, CaseStatus.FAILED},
    CaseStatus.INTAKE_COMPLETE: {CaseStatus.PROCESSING, CaseStatus.CANCELLED, CaseStatus.FAILED},
    CaseStatus.PROCESSING: {
        CaseStatus.READY_FOR_ASSESSMENT, CaseStatus.NEEDS_MORE_EVIDENCE,
        CaseStatus.MANUAL_REVIEW_REQUIRED, CaseStatus.FAILED, CaseStatus.CANCELLED,
    },
    CaseStatus.NEEDS_MORE_EVIDENCE: {CaseStatus.INTAKE_COMPLETE, CaseStatus.PROCESSING,
                                     CaseStatus.CANCELLED},
    CaseStatus.READY_FOR_ASSESSMENT: {CaseStatus.PROCESSING, CaseStatus.ASSESSED,
                                      CaseStatus.FAILED},
    CaseStatus.ASSESSED: {CaseStatus.REPORT_READY, CaseStatus.MANUAL_REVIEW_REQUIRED,
                          CaseStatus.FAILED},
    CaseStatus.REPORT_READY: {CaseStatus.PROCESSING},  # reprocess creates new versions
    CaseStatus.MANUAL_REVIEW_REQUIRED: {CaseStatus.PROCESSING, CaseStatus.CANCELLED},
    CaseStatus.FAILED: {CaseStatus.PROCESSING, CaseStatus.CANCELLED},
    CaseStatus.CANCELLED: set(),
}


def transition(case, new_status: CaseStatus) -> CaseStatus:
    current = case.status
    if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(f"cannot transition case from {current} to {new_status}")
    case.status = new_status
    return new_status
