"""Pipeline orchestrator (P0.1: D-Q1 derivation isolation, D1/D2 idempotency,
D3 safety ordering, §16/§17).

Canonical order:
1. materialize artifact text;
2. compute effective_input_hash; if an authoritative terminal result exists for the
   same hash → return the reused result; NO new derivation run is created;
3. create the derivation ProcessingRun (RUNNING, attempt = max(prev)+1,
   non-authoritative) — its id is the derivation_run_id stamped on all derived rows;
4. run stages (each commits; completed stages stay auditable);
5. on full success: ONE atomic commit — old ACTIVE rows → SUPERSEDED, new rows
   stay ACTIVE, derivation → SUCCEEDED + authoritative;
6. on failure: failed stage's partial state rolled back, the derivation's committed
   rows → NON_AUTHORITATIVE, derivation → FAILED (never reusable), previous
   derivation remains ACTIVE (no authority vacuum).
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.ai.gateway import ModelGateway
from app.core.artifacts.ingestion import extract_text_if_supported
from app.core.cases import state_machine
from app.domain.enums import (CaseStatus, DerivationStatus, ProcessingRunStatus,
                              RunAuthority, SafetyState)
from app.domain.models import (ArtifactClassification, ArtifactQualityAssessment,
                               Assessment, Case, Claim, EvidenceGap, EvidenceLink,
                               Extraction, Finding, ProcessingRun, SafetyResult,
                               TreatmentItem, public_id, utcnow)
from app.errors import InvalidTransitionError
from app.governance.record import audit
from app.pipeline import claims as claims_mod
from app.pipeline import assessment as assessment_mod
from app.pipeline import reporting as reporting_mod
from app.pipeline import stages
from app.pipeline.assessment import screen_case_text
from app.pipeline.runs import next_attempt, processing_run

PIPELINE_SCHEMA_VERSION = "pipeline-v3"

MODULE_VERSIONS = {
    "classification": "classifier-mock-v3",
    "quality_gate": "quality-rules-v2",
    "extraction": "extraction-mock-v3",
    "claims": "claim-engine-v3",
    "assessment": "assessment-rules-v2",
    "snapshot_report": "report-composer-v3",
}

# Tables whose rows belong to a derivation and are switched atomically.
DERIVED_TABLES = [ArtifactClassification, ArtifactQualityAssessment, Extraction,
                  TreatmentItem, Finding, Claim, EvidenceLink, EvidenceGap,
                  Assessment, SafetyResult]


def _advance(case: Case, target: CaseStatus) -> None:
    """Walk the state machine along its shortest allowed path to the target."""
    from collections import deque
    graph = state_machine.ALLOWED_TRANSITIONS
    start = case.status
    if start == target:
        return
    queue, parents = deque([start]), {start: None}
    while queue:
        current = queue.popleft()
        for nxt in graph.get(current, set()):
            if nxt in parents:
                continue
            parents[nxt] = current
            if nxt == target:
                queue.clear()
                break
            queue.append(nxt)
    if target not in parents:
        raise InvalidTransitionError(f"no path from {start} to {target}")
    path, node = [], target
    while node != start:
        path.append(node)
        node = parents[node]
    for step in reversed(path):
        state_machine.transition(case, step)


def effective_input_hash(case: Case) -> str:
    """Hash of everything that materially determines pipeline output."""
    material = {
        "schema": PIPELINE_SCHEMA_VERSION,
        "modules": MODULE_VERSIONS,
        "question": case.question_text,
        "context": case.context_text,
        "dentist_recommendation": case.dentist_recommendation_text,
        "case_version": case.version,
        # Only source inputs — derived fields (classification) are outputs.
        "artifacts": sorted(
            [a.public_id, a.sha256, a.text_content or ""]
            for a in case.artifacts),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def _reusable_derivation(db: Session, case: Case, input_hash: str) -> ProcessingRun | None:
    """Authoritative terminal result for the same effective input (D2/D-Q1).
    FAILED runs are never reusable."""
    return (db.query(ProcessingRun)
            .filter(ProcessingRun.case_id == case.id,
                    ProcessingRun.module == "pipeline",
                    ProcessingRun.status == ProcessingRunStatus.SUCCEEDED,
                    ProcessingRun.authority == RunAuthority.ACTIVE,
                    ProcessingRun.input_hash == input_hash)
            .order_by(ProcessingRun.id.desc()).first())


def _reused_result(db: Session, case: Case, prior: ProcessingRun) -> dict:
    """Same public contract as a fresh result (D8), sourced from the reused
    derivation's authoritative rows."""
    from app.domain.models import AssessmentSnapshot, Report
    snap = (db.query(AssessmentSnapshot)
            .filter(AssessmentSnapshot.derivation_run_id == prior.id)
            .order_by(AssessmentSnapshot.id.desc()).first())
    rep = (db.query(Report)
           .filter(Report.derivation_run_id == prior.id)
           .order_by(Report.id.desc()).first())
    # EvidenceLink is claim-scoped (no case_id); derivation_run_id identifies scope.
    active = {t: db.query(t)
              .filter(t.derivation_run_id == prior.id,
                      t.derivation_status == DerivationStatus.ACTIVE).count()
              for t in (Claim, EvidenceLink, EvidenceGap, Assessment)}
    return {
        "case_public_id": case.public_id,
        "reused": True,
        "pipeline_run_id": prior.public_id,
        "snapshot": snap.public_id if snap else None,
        "report": rep.public_id if rep else None,
        "report_kind": rep.content.get("report_kind") if rep else None,
        "safety_state": snap.safety_state.value if snap else None,
        "status": case.status.value,
        "claims": active[Claim],
        "evidence_links": active[EvidenceLink],
        "gaps": active[EvidenceGap],
        "assessments": active[Assessment],
        "rejected_artifacts": [],
        "limitations": [],
        "needs_more_evidence": [],
    }


def _mark_derivation_rows(db: Session, case: Case, derivation_run_id: int,
                          status: DerivationStatus) -> None:
    """Flip all committed rows of one derivation to the given status. Bulk updates
    on derived tables are allowed (they are not immutability-protected entities).
    Artifact-scoped tables (classifications/quality/extractions) have no case_id;
    derivation_run_id alone identifies their scope."""
    for table in DERIVED_TABLES:
        (db.query(table)
         .filter(table.derivation_run_id == derivation_run_id)
         .update({"derivation_status": status}, synchronize_session=False))


def _activate_derivation(db: Session, case: Case, derivation: ProcessingRun) -> None:
    """Atomic authority switch (D-Q1): old ACTIVE → SUPERSEDED, this derivation's
    rows stay ACTIVE, derivation run → SUCCEEDED + ACTIVE. Callers commit."""
    for table in DERIVED_TABLES:
        if hasattr(table, "case_id"):
            q = db.query(table).filter(
                table.case_id == case.id,
                table.derivation_status == DerivationStatus.ACTIVE,
                table.derivation_run_id != derivation.id)
        else:
            # Artifact/claim-scoped rows inherit case ownership from their
            # derivation run; never supersede another case's derived evidence.
            q = db.query(table).filter(
                table.derivation_run_id.in_(
                    db.query(ProcessingRun.id).filter(
                        ProcessingRun.case_id == case.id)),
                table.derivation_status == DerivationStatus.ACTIVE,
                table.derivation_run_id != derivation.id)
        q.update({"derivation_status": DerivationStatus.SUPERSEDED},
                 synchronize_session=False)
    (db.query(ProcessingRun)
     .filter(ProcessingRun.case_id == case.id,
             ProcessingRun.module == "pipeline",
             ProcessingRun.authority == RunAuthority.ACTIVE,
             ProcessingRun.id != derivation.id)
     .update({"authority": RunAuthority.SUPERSEDED}, synchronize_session=False))
    derivation.status = ProcessingRunStatus.SUCCEEDED
    derivation.authority = RunAuthority.ACTIVE
    derivation.finished_at = utcnow()


def run_case_pipeline(db: Session, case: Case) -> dict:
    gw = ModelGateway(db)
    result: dict = {"case_public_id": case.public_id}

    # Materialize artifact text so the effective-input hash is stable (P0-04).
    for artifact in case.artifacts:
        if artifact.text_content is None:
            from app.security.ingestion import read_bytes
            data = read_bytes(artifact.storage_key)
            artifact.text_content = extract_text_if_supported(artifact, data)
    db.commit()

    # ---- Reuse resolution BEFORE creating a derivation run (Correction 2)
    input_hash = effective_input_hash(case)
    prior = _reusable_derivation(db, case, input_hash)
    if prior is not None:
        return _reused_result(db, case, prior)

    # ---- Create the derivation run (attempt = max(prev)+1, D1)
    attempt = next_attempt(db, case.id, "pipeline", input_hash)
    derivation = ProcessingRun(
        public_id=public_id("RUN"), case_id=case.id, module="pipeline",
        status=ProcessingRunStatus.RUNNING, attempt=attempt,
        input_hash=input_hash, input_version=f"case-v{case.version}",
        authority=RunAuthority.NON_AUTHORITATIVE, started_at=utcnow())
    db.add(derivation)
    db.flush()
    derivation_run_id = derivation.id

    _advance(case, CaseStatus.PROCESSING)
    db.commit()

    # ---- Intake safety screening (D3): artifact-independent, runs before any
    # document-dependent early exit; safety ⊥ evidence sufficiency.
    intake_state, intake_reasons = screen_case_text(case)

    try:
        # ---- Classification
        with processing_run(db, case, "classification",
                            [a.public_id for a in case.artifacts],
                            module_version=MODULE_VERSIONS["classification"],
                            derivation_run_id=derivation_run_id):
            for artifact in case.artifacts:
                stages.classify_artifact(db, gw, artifact, derivation_run_id)
        db.commit()

        # ---- Quality gate (P0-07)
        decisions: dict[str, stages.QualityOutcome] = {}
        with processing_run(db, case, "quality_gate",
                            [a.public_id for a in case.artifacts],
                            module_version=MODULE_VERSIONS["quality_gate"],
                            derivation_run_id=derivation_run_id):
            for artifact in case.artifacts:
                decisions[artifact.public_id] = stages.run_quality_gate(
                    db, artifact, derivation_run_id)
        db.commit()

        rejected = [aid for aid, o in decisions.items()
                    if o.decision == stages.QualityDecision.REJECT_ARTIFACT]
        needs_more = [aid for aid, o in decisions.items()
                      if o.decision == stages.QualityDecision.NEEDS_MORE_EVIDENCE]
        limitations = [aid for aid, o in decisions.items()
                       if o.decision == stages.QualityDecision.CONTINUE_WITH_LIMITATIONS]
        processable = [a for a in case.artifacts
                       if decisions.get(a.public_id) and
                       decisions[a.public_id].decision !=
                       stages.QualityDecision.REJECT_ARTIFACT]

        if not processable or len(needs_more) == len(case.artifacts):
            # Evidence dimension: NEEDS_MORE_EVIDENCE (terminal, reusable — D2).
            # Safety dimension preserved from intake screening (D3).
            if intake_state == SafetyState.BLOCKED:
                _record_safety_result(db, case, SafetyState.BLOCKED,
                                      intake_reasons, derivation_run_id)
                _advance(case, CaseStatus.MANUAL_REVIEW_REQUIRED)
                _activate_derivation(db, case, derivation)
                db.commit()
                result.update({"status": case.status.value, "reused": False,
                               "safety_state": SafetyState.BLOCKED.value,
                               "report": None, "snapshot": None, "report_kind": None,
                               "rejected_artifacts": rejected,
                               "limitations": limitations,
                               "needs_more_evidence": needs_more})
                return result
            if intake_state == SafetyState.URGENT_EVALUATION:
                # urgent-safe report does not require documents (D3)
                safety = _record_safety_result(db, case, SafetyState.URGENT_EVALUATION,
                                               intake_reasons, derivation_run_id)
                snapshot = reporting_mod.create_snapshot(db, case, safety,
                                                         derivation_run_id)
                report = reporting_mod.compose_report(db, case, snapshot)
                _advance(case, CaseStatus.NEEDS_MORE_EVIDENCE)
                _activate_derivation(db, case, derivation)
                db.commit()
                result.update({"status": case.status.value, "reused": False,
                               "safety_state": safety.state.value,
                               "snapshot": snapshot.public_id,
                               "report": report.public_id,
                               "report_kind": report.content.get("report_kind"),
                               "claims": 0, "evidence_links": 0, "gaps": 0,
                               "assessments": 0, "rejected_artifacts": rejected,
                               "limitations": limitations,
                               "needs_more_evidence": needs_more})
                return result
            _advance(case, CaseStatus.NEEDS_MORE_EVIDENCE)
            _activate_derivation(db, case, derivation)
            db.commit()
            audit(db, "pipeline_needs_more_evidence", case_id=case.id,
                  rejected=rejected, needs_more=needs_more)
            db.commit()
            result.update({"status": case.status.value, "reused": False,
                           "safety_state": intake_state.value,
                           "report": None, "snapshot": None, "report_kind": None,
                           "claims": 0, "evidence_links": 0, "gaps": 0,
                           "assessments": 0, "rejected_artifacts": rejected,
                           "limitations": limitations,
                           "needs_more_evidence": needs_more})
            return result

        # ---- Extraction -> findings (canonical; no raw-text fallback)
        with processing_run(db, case, "extraction",
                            [a.public_id for a in processable],
                            module_version=MODULE_VERSIONS["extraction"],
                            derivation_run_id=derivation_run_id):
            for artifact in processable:
                extraction = stages.extract_structured(db, gw, artifact,
                                                       derivation_run_id)
                stages.build_findings_from_extraction(db, artifact, extraction,
                                                      derivation_run_id)
        db.commit()

        # ---- Claims -> evidence graph -> gaps
        with processing_run(db, case, "claims", f"case-v{case.version}",
                            module_version=MODULE_VERSIONS["claims"],
                            derivation_run_id=derivation_run_id):
            case_claims = claims_mod.build_case_claims(db, gw, case, derivation_run_id)
            links = claims_mod.build_evidence_graph(db, case, case_claims,
                                                    derivation_run_id)
            gaps = claims_mod.run_gap_engine(db, case, case_claims, derivation_run_id)
        db.commit()
        result["claims"] = len(case_claims)
        result["evidence_links"] = len(links)
        result["gaps"] = len(gaps)

        # ---- Assessment + safety
        with processing_run(db, case, "assessment", f"case-v{case.version}",
                            module_version=MODULE_VERSIONS["assessment"],
                            derivation_run_id=derivation_run_id):
            assessments = assessment_mod.run_assessment_engine(db, case,
                                                               derivation_run_id)
            safety = assessment_mod.run_safety_gate(db, case, derivation_run_id)
        db.commit()
        result["assessments"] = len(assessments)
        result["safety_state"] = safety.state.value

        _advance(case, CaseStatus.READY_FOR_ASSESSMENT)
        db.commit()

        # ---- Safety-driven report policy (P0-06)
        with processing_run(db, case, "snapshot_report", f"case-v{case.version}",
                            module_version=MODULE_VERSIONS["snapshot_report"],
                            derivation_run_id=derivation_run_id):
            snapshot = reporting_mod.create_snapshot(db, case, safety,
                                                     derivation_run_id)
            if safety.state == SafetyState.BLOCKED:
                _advance(case, CaseStatus.MANUAL_REVIEW_REQUIRED)
                result["snapshot"] = snapshot.public_id
                result["report"] = None
                result["report_kind"] = None
            elif safety.state == SafetyState.MANUAL_REVIEW:
                _advance(case, CaseStatus.MANUAL_REVIEW_REQUIRED)
                report = reporting_mod.compose_report(db, case, snapshot)
                result["snapshot"] = snapshot.public_id
                result["report"] = report.public_id
                result["report_kind"] = "REVIEW_PENDING"
            else:  # NORMAL / CAUTION / URGENT_EVALUATION
                _advance(case, CaseStatus.ASSESSED)
                report = reporting_mod.compose_report(db, case, snapshot)
                _advance(case, CaseStatus.REPORT_READY)
                result["snapshot"] = snapshot.public_id
                result["report"] = report.public_id
                result["report_kind"] = report.content.get("report_kind")
        db.commit()

        # ---- Atomic authority switch (D-Q1): old ACTIVE → SUPERSEDED, new → ACTIVE
        _activate_derivation(db, case, derivation)
        db.commit()

        result.update({"status": case.status.value, "reused": False,
                       "pipeline_run_id": derivation.public_id,
                       "rejected_artifacts": rejected, "limitations": limitations,
                       "needs_more_evidence": needs_more})
        return result

    except Exception as exc:
        # Transaction safety (§17) + D-Q1: previous derivation remains ACTIVE;
        # this derivation's committed rows become NON_AUTHORITATIVE; run FAILED.
        db.rollback()
        _mark_derivation_rows(db, case, derivation_run_id,
                              DerivationStatus.NON_AUTHORITATIVE)
        derivation.status = ProcessingRunStatus.FAILED
        derivation.authority = RunAuthority.NON_AUTHORITATIVE
        derivation.error = str(exc)[:2000]
        derivation.finished_at = utcnow()
        audit(db, "pipeline_failed", case_id=case.id, module="pipeline",
              attempt=derivation.attempt, error=str(exc)[:300])
        try:
            _advance(case, CaseStatus.FAILED)
        except InvalidTransitionError:
            _advance(case, CaseStatus.MANUAL_REVIEW_REQUIRED)
        db.commit()
        result.update({"status": case.status.value, "failed_module": "pipeline",
                       "error_code": getattr(exc, "code", "INTERNAL_ERROR"),
                       "snapshot": None, "report": None, "report_kind": None,
                       "reused": False,
                       "pipeline_run_id": derivation.public_id})
        return result


def _record_safety_result(db: Session, case: Case, state: SafetyState,
                          reasons: list[str], derivation_run_id: int) -> SafetyResult:
    safety = SafetyResult(case_id=case.id, state=state, reasons=reasons,
                          rules_version="safety-rules-v2",
                          derivation_run_id=derivation_run_id,
                          derivation_status=DerivationStatus.ACTIVE)
    db.add(safety)
    db.flush()
    return safety
