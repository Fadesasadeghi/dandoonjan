"""Domain-resource API (V0 surface). No internal pipeline mutation endpoints."""
from __future__ import annotations
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.core.artifacts.ingestion import ingest_artifact
from app.core.cases import state_machine
from app import db as database
from app.db import get_db
from app.domain.enums import CaseStatus, DerivationStatus, ProcessingRunStatus, RunAuthority
from app.domain.models import (Artifact, Assessment, AssessmentSnapshot, Case, ProcessingRun, Report,
                               public_id)
from app.errors import DandoonjanError, InvalidTransitionError, KnowledgePackUnavailableError
from app.governance.record import audit
from app.pipeline.orchestrator import run_case_pipeline
from app.security import case_access

router = APIRouter(route_class=case_access.CaseAdmissionRoute)
from app.core.cases import dossier


@router.get('/cases/{case_public_id}/dossier')
def get_dossier(case_public_id: str, case: Case = Depends(case_access.read_case),
                db: Session = Depends(get_db, scope='function')):
    return dossier.presentation(case)


@router.put('/cases/{case_public_id}/dossier')
def put_dossier(case_public_id: str, patch: dossier.DossierPatch,
                case: Case = Depends(case_access.mutate_case),
                db: Session = Depends(get_db, scope='function')):
    result = dossier.update(db, case, patch)
    audit(db, 'dossier_saved', case_id=case.id, case_version=case.version)
    return result

from app.core.cases.sample import SAMPLE_TEXT as DEMO_SAMPLE_TEXT


@router.get("/demo/sample", response_class=PlainTextResponse)
def demo_sample():
    """Return synthetic, non-sensitive evidence for the real demo flow."""
    return DEMO_SAMPLE_TEXT


@router.get('/demo/sample-image')
def demo_image():
    from app.core.cases.sample import image_pattern
    return Response(image_pattern(), media_type='image/png')


@router.get('/demo/sample-plan')
def demo_plan():
    from app.core.cases.sample import plan_pdf
    return Response(plan_pdf(), media_type='application/pdf')


def _handle_domain_error(exc: DandoonjanError):
    status = 400 if isinstance(exc, InvalidTransitionError) else 422
    raise HTTPException(status_code=status, detail={"code": exc.code,
                                                    "message_fa": exc.user_message_fa})


@router.post("/cases", status_code=201)
def create_case(question: str = Form(...), dentist_recommendation: str = Form(""),
                context: str = Form(""),
                principal: case_access.Principal = Depends(case_access.account_mutation),
                db: Session = Depends(get_db, scope="function")):
    case_access.touch(db, principal)
    return create_owned_case(db, principal.user_id, question, dentist_recommendation, context)


def create_owned_case(db, user_id, question, dentist_recommendation="", context=""):
    """Shared creation logic; HTTP callers supply an admitted principal."""
    from app.core.ontology import ontology as ont
    case = Case(public_id=public_id("CASE"), user_id=user_id, status=CaseStatus.CREATED,
                question_text=question, context_text=context,
                dentist_recommendation_text=dentist_recommendation,
                ontology_version=ont.ONTOLOGY_VERSION)
    db.add(case)
    db.flush()
    state_machine.transition(case, CaseStatus.INTAKE_COMPLETE)
    audit(db, "case_created", case_id=case.id, case_public_id=case.public_id)
    return {"case_id": case.public_id, "status": case.status.value}


@router.get("/cases/{case_public_id}")
def get_case(case_public_id: str, case: Case = Depends(case_access.read_case),
             db: Session = Depends(get_db, scope="function")):
    artifacts = db.query(Artifact).filter(Artifact.case_id == case.id).all()
    return {
        "case_id": case.public_id, "status": case.status.value, "version": case.version,
        "question": case.question_text,
        "dentist_recommendation": case.dentist_recommendation_text,
        "artifacts": [{"artifact_id": a.public_id, "filename": a.original_filename,
                       "category": a.category.value, "subtype": a.subtype.value,
                       "size": a.file_size} for a in artifacts],
    }


@router.post("/cases/{case_public_id}/artifacts", status_code=201)
def upload_artifact(case_public_id: str, file: UploadFile = File(...),
                    document_role: Literal['unspecified', 'treatment_plan', 'prescription', 'dental_image', 'previous_report'] = Form('unspecified'),
                    case: Case = Depends(case_access.upload_case),
                    db: Session = Depends(get_db, scope="function")):
    # Admission dependency retains the capacity lock through insertion/commit.
    try:
        from app.config import get_settings
        data = read_upload_bounded(file.file, get_settings().max_upload_bytes)
        result = ingest_artifact(db, case, file.filename or "file",
                                 file.content_type or "", data, document_role=document_role)
    except DandoonjanError as exc:
        case_id = case.id
        db.rollback()  # Release the capacity lock before independent audit.
        audit_db = database.SessionLocal()
        try:
            audit(audit_db, "artifact_rejected", case_id=case_id, reason=exc.code)
            audit_db.commit()
        finally:
            audit_db.close()
        _handle_domain_error(exc)
        return
    audit(db, "artifact_uploaded", case_id=case.id,
          artifact_public_id=result.artifact.public_id,
          duplicate_of=result.duplicate_of)
    return {"artifact_id": result.artifact.public_id,
            "duplicate_of": result.duplicate_of,
            "status": result.artifact.category.value}


def read_upload_bounded(stream, limit: int) -> bytes:
    """Bound application reads of an already-spooled multipart file."""
    chunks, remaining = [], limit + 1
    while remaining:
        chunk = stream.read(min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


@router.patch("/cases/{case_public_id}")
def update_case(case_public_id: str, question: str = Form(None),
                dentist_recommendation: str = Form(None), context: str = Form(None),
                case: Case = Depends(case_access.mutate_case),
                db: Session = Depends(get_db, scope="function")):
    """Material case-text change bumps Case version (P0-04)."""
    changed = False
    if question is not None and question != case.question_text:
        case.question_text = question
        changed = True
    if dentist_recommendation is not None and \
            dentist_recommendation != case.dentist_recommendation_text:
        case.dentist_recommendation_text = dentist_recommendation
        changed = True
    if context is not None and context != case.context_text:
        case.context_text = context
        changed = True
    if changed:
        case.version = (case.version or 1) + 1
        audit(db, "case_updated", case_id=case.id, case_public_id=case.public_id,
              new_version=case.version)
    return {"case_id": case.public_id, "version": case.version, "changed": changed}


@router.post("/cases/{case_public_id}/process")
def process_case(case_public_id: str, case: Case = Depends(case_access.mutate_case),
                 db: Session = Depends(get_db, scope="function")):
    try:
        return run_case_pipeline(db, case)
    except DandoonjanError as exc:
        _handle_domain_error(exc)
        return


@router.get("/cases/{case_public_id}/status")
def case_status(case_public_id: str, case: Case = Depends(case_access.read_case),
                db: Session = Depends(get_db, scope="function")):
    artifacts = db.query(Artifact).filter(Artifact.case_id == case.id).all()
    return {"case_id": case.public_id, "status": case.status.value,
            "artifacts": [{"artifact_id": a.public_id, "category": a.category.value,
                           "subtype": a.subtype.value} for a in artifacts]}


def _current_pipeline_filters(db: Session, case: Case) -> tuple:
    """Shared current-result boundary; stored ACTIVE history alone is not current."""
    from app.pipeline.orchestrator import effective_input_hash
    current_hash = effective_input_hash(db, case)
    latest_id = (db.query(ProcessingRun.id).filter(
        ProcessingRun.case_id == case.id, ProcessingRun.module == 'pipeline')
        .order_by(ProcessingRun.id.desc()).limit(1).scalar())
    return (ProcessingRun.case_id == case.id,
            ProcessingRun.module == 'pipeline',
            ProcessingRun.status == ProcessingRunStatus.SUCCEEDED,
            ProcessingRun.authority == RunAuthority.ACTIVE,
            ProcessingRun.input_hash == current_hash,
            ProcessingRun.id == latest_id)


@router.get("/cases/{case_public_id}/assessment")
def case_assessment(case_public_id: str, case: Case = Depends(case_access.read_case),
                    db: Session = Depends(get_db, scope="function")):
    try:
        current_filters = _current_pipeline_filters(db, case)
    except KnowledgePackUnavailableError:
        # No current authority can be established. Preserve the empty-list API.
        assessments = []
    else:
        assessments = (db.query(Assessment)
                       .join(ProcessingRun, Assessment.derivation_run_id == ProcessingRun.id)
                       .filter(Assessment.case_id == case.id,
                               Assessment.derivation_status == DerivationStatus.ACTIVE,
                               *current_filters).all())
    return {"case_id": case.public_id, "status": case.status.value,
            "assessments": [{"claim_type": a.claim.claim_type.value,
                             "treatment": a.claim.treatment_id,
                             "modality": a.claim.modality.value if a.claim.modality else None,
                             "subject": a.claim.subject,
                             "status": a.status.value, "confidence": a.confidence.value,
                             "missing_evidence": a.missing_evidence} for a in assessments]}


@router.get("/cases/{case_public_id}/report")
def case_report(case_public_id: str, case: Case = Depends(case_access.read_case),
                db: Session = Depends(get_db, scope="function")):
    # An earlier snapshot remains history after a failed/new processing contract.
    current_filters = _current_pipeline_filters(db, case)
    report = (db.query(Report)
              .join(ProcessingRun, Report.derivation_run_id == ProcessingRun.id)
              .join(AssessmentSnapshot, Report.snapshot_id == AssessmentSnapshot.id)
              .filter(Report.case_id == case.id,
                      *current_filters,
                      AssessmentSnapshot.case_id == case.id,
                      AssessmentSnapshot.derivation_run_id == ProcessingRun.id,
                      AssessmentSnapshot.case_version == case.version)
              .order_by(Report.id.desc()).first())
    if report is None:
        raise HTTPException(status_code=404, detail="REPORT_NOT_READY")
    from app.api.presentation import report_presentation
    snapshot = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.id == report.snapshot_id).one()
    return {"case_id": case.public_id, "report_id": report.public_id,
            "report_kind": report.content.get("report_kind"),
            "snapshot_id": snapshot.public_id,
            "safety_state": report.content.get("safety_state"),
            "sections": report.content.get("sections", []),
            "review": snapshot.payload.get('review') if report.content.get('report_kind') == 'STANDARD' else None,
            "presentation": report_presentation(db, report, snapshot)}
