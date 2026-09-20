"""P0.1 regression tests: derivation isolation (D-Q1), retry safety (D1),
NEEDS_MORE_EVIDENCE idempotency (D2), safety ordering (D3), immutability depth
(D-Q4), locator propagation (D5), ontology patch (D6), reuse contract (D8)."""
import pymupdf
import pytest


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _ingest(db, case, text="Treatment Plan\nTooth 46: RCT", filename="plan.pdf"):
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename=filename, declared_mime="application/pdf",
                    data=_pdf(text))


def _run(db, case):
    from app.pipeline.orchestrator import run_case_pipeline
    return run_case_pipeline(db, case)


# ---------------- D-Q1: derivation isolation ----------------

DERIVED_COUNTS = {
    "claims": "Claim", "findings": "Finding", "gaps": "EvidenceGap",
    "assessments": "Assessment", "links": "EvidenceLink",
}


def _active_counts(db, case):
    from app.domain.enums import DerivationStatus
    from app.domain.models import (Assessment, Claim, EvidenceGap, EvidenceLink, Finding)
    out = {}
    for name, model in (("claims", Claim), ("findings", Finding),
                        ("gaps", EvidenceGap), ("assessments", Assessment),
                        ("links", EvidenceLink)):
        if hasattr(model, "case_id"):
            q = db.query(model).filter(model.case_id == case.id)
        else:
            q = db.query(model).join(
                Claim, model.claim_id == Claim.id).filter(Claim.case_id == case.id)
        out[name] = q.filter(model.derivation_status == DerivationStatus.ACTIVE).count()
    return out


def test_dq1_revision_rerun_does_not_accumulate(db, case):
    """Proposition D: historical derived state cannot contaminate current assessment."""
    _ingest(db, case)
    r1 = _run(db, case)
    c1 = _active_counts(db, case)
    # material revision change
    case.question_text = "REVISED: آیا کشیدن دندان لازم است؟"
    case.dentist_recommendation_text = "دکتر گفت کشیدن لازم است"
    case.version += 1
    db.commit()
    r2 = _run(db, case)
    c2 = _active_counts(db, case)
    assert r2["reused"] is False
    # ACTIVE set replaced, not accumulated (counts never grow across revisions)
    assert c2["claims"] <= c1["claims"], f"claims accumulated: {c1} -> {c2}"
    assert c2["gaps"] <= c1["gaps"], f"gaps accumulated: {c1} -> {c2}"
    # old revision rows preserved as SUPERSEDED
    from app.domain.enums import DerivationStatus
    from app.domain.models import Claim
    superseded = db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.derivation_status == DerivationStatus.SUPERSEDED).count()
    assert superseded >= c1["claims"]
    # the ACTIVE set contains ONLY the new revision's claims (extraction claim
    # about tooth 36 must not exist; question/rec changed to extraction)
    from app.domain.models import Claim
    active_claims = db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.derivation_status == DerivationStatus.ACTIVE,
        Claim.claim_type == "TREATMENT").all()
    from app.domain.enums import TruthType
    clinician_active = [c for c in active_claims
                        if c.source_type == TruthType.CLINICIAN_REPORTED]
    assert clinician_active
    assert all(c.treatment_id == "TREATMENT_EXTRACTION" for c in clinician_active)
    # no ACTIVE clinician claim from the previous revision remains
    assert all(c.treatment_id != "TREATMENT_ROOT_CANAL"
               for c in clinician_active)


def test_dq1_no_authority_vacuum_on_failure(db, case):
    """V1 ACTIVE stays authoritative when V2 processing fails."""
    from app.ai.gateway import ModelGateway
    from app.domain.enums import DerivationStatus, RunAuthority
    from app.domain.models import Claim, ProcessingRun
    from app.pipeline import orchestrator as orc

    _ingest(db, case)
    r1 = _run(db, case)
    assert r1["status"] == "REPORT_READY"
    active_before = db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.derivation_status == DerivationStatus.ACTIVE).count()
    assert active_before > 0

    # material change + malicious provider -> V2 fails
    class Malicious:
        name = "malicious"

        def run(self, prompt, content, params):
            if prompt.prompt_id == "claim_builder":
                return {"claims": [{"claim_type": "TREATMENT", "subject": "TOOTH_900",
                                    "predicate": "REQUIRES_TREATMENT",
                                    "object_value": "TREATMENT_ROOT_CANAL",
                                    "treatment": "TREATMENT_ROOT_CANAL",
                                    "modality": "REQUIRED", "confidence": 0.9}]}
            from app.ai.providers import MockProvider
            return MockProvider().run(prompt, content, params)

    class GW(ModelGateway):
        def __init__(self, db_):
            super().__init__(db_)
            self.provider = Malicious()

    case.question_text = "revised question?"
    case.version += 1
    db.commit()
    orc.ModelGateway = GW
    try:
        r2 = _run(db, case)
    finally:
        orc.ModelGateway = ModelGateway
    assert r2["status"] == "FAILED"
    # V1 remains authoritative
    active_after = db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.derivation_status == DerivationStatus.ACTIVE).count()
    assert active_after == active_before
    failed_run = db.query(ProcessingRun).filter(
        ProcessingRun.case_id == case.id, ProcessingRun.module == "pipeline",
        ProcessingRun.status == "FAILED").order_by(
        ProcessingRun.id.desc()).first()
    assert failed_run.authority == RunAuthority.NON_AUTHORITATIVE
    authoritative = db.query(ProcessingRun).filter(
        ProcessingRun.case_id == case.id, ProcessingRun.module == "pipeline",
        ProcessingRun.authority == RunAuthority.ACTIVE).all()
    assert len(authoritative) == 1


def test_dq1_snapshot_scoped_to_one_derivation(db, case):
    """Proposition B: snapshot content comes from exactly one derivation."""
    from app.domain.models import AssessmentSnapshot
    _ingest(db, case)
    _run(db, case)
    case.question_text = "revised?"
    case.version += 1
    db.commit()
    _run(db, case)
    snaps = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.case_id == case.id).order_by(AssessmentSnapshot.id).all()
    assert len(snaps) == 2
    derivations = {s.versions["derivation_run"] for s in snaps}
    assert len(derivations) == 2
    for s in snaps:
        rp = s.payload["run_provenance"]
        assert rp["derivation_run_id"] == s.versions["derivation_run"]


# ---------------- D1: retry safety ----------------

def test_d1_failed_then_retry_same_input_no_integrity_error(db, case):
    from app.ai.gateway import ModelGateway
    from app.pipeline import orchestrator as orc

    class Malicious:
        name = "malicious"

        def run(self, prompt, content, params):
            if prompt.prompt_id == "claim_builder":
                return {"claims": [{"claim_type": "TREATMENT", "subject": "TOOTH_900",
                                    "predicate": "REQUIRES_TREATMENT",
                                    "object_value": "TREATMENT_ROOT_CANAL",
                                    "treatment": "TREATMENT_ROOT_CANAL",
                                    "modality": "REQUIRED", "confidence": 0.9}]}
            from app.ai.providers import MockProvider
            return MockProvider().run(prompt, content, params)

    class GWBad(ModelGateway):
        def __init__(self, db_):
            super().__init__(db_)
            self.provider = Malicious()

    _ingest(db, case)
    orc.ModelGateway = GWBad
    try:
        rf = _run(db, case)
        assert rf["status"] == "FAILED"
    finally:
        orc.ModelGateway = ModelGateway
    # retry with the SAME effective input must succeed (V4 repro inverted)
    rs = _run(db, case)
    assert rs["status"] == "REPORT_READY"
    from app.domain.enums import RunAuthority
    from app.domain.models import ProcessingRun
    runs = db.query(ProcessingRun).filter(
        ProcessingRun.case_id == case.id, ProcessingRun.module == "pipeline").order_by(
        ProcessingRun.id).all()
    attempts = [r.attempt for r in runs]
    assert attempts == sorted(attempts) and len(set(attempts)) == len(attempts)
    assert runs[-1].authority == RunAuthority.ACTIVE
    assert runs[0].status == "FAILED"  # failed + successful coexist


def test_d1_double_failure_is_handled(db, case):
    from app.ai.gateway import ModelGateway
    from app.pipeline import orchestrator as orc

    class Malicious:
        name = "malicious"

        def run(self, prompt, content, params):
            if prompt.prompt_id == "claim_builder":
                return {"claims": [{"claim_type": "TREATMENT", "subject": "TOOTH_900",
                                    "predicate": "REQUIRES_TREATMENT",
                                    "object_value": "TREATMENT_ROOT_CANAL",
                                    "treatment": "TREATMENT_ROOT_CANAL",
                                    "modality": "REQUIRED", "confidence": 0.9}]}
            from app.ai.providers import MockProvider
            return MockProvider().run(prompt, content, params)

    class GWBad(ModelGateway):
        def __init__(self, db_):
            super().__init__(db_)
            self.provider = Malicious()

    _ingest(db, case)
    orc.ModelGateway = GWBad
    try:
        r1 = _run(db, case)
        r2 = _run(db, case)  # must not raise unhandled (V4 repro inverted)
        assert r1["status"] == r2["status"] == "FAILED"
    finally:
        orc.ModelGateway = ModelGateway


# ---------------- D2: NEEDS_MORE_EVIDENCE idempotent ----------------

def test_d2_needs_more_evidence_reused(db, case):
    from app.domain.models import ArtifactClassification
    _ingest(db, case, text="", filename="blank.pdf")
    r1 = _run(db, case)
    assert r1["status"] == "NEEDS_MORE_EVIDENCE"
    n_cls = db.query(ArtifactClassification).count()
    r2 = _run(db, case)
    assert r2["reused"] is True
    assert db.query(ArtifactClassification).count() == n_cls


# ---------------- D3: safety before document-dependent exit ----------------

def test_d3_urgent_without_artifacts_still_screened(db, case):
    case.question_text = "خونریزی شدید دارم و تورم صورت دارم"
    result = _run(db, case)
    # evidence dimension
    assert result["status"] == "NEEDS_MORE_EVIDENCE"
    # safety dimension preserved and urgent-safe report produced
    assert result["safety_state"] == "URGENT_EVALUATION"
    assert result["report_kind"] == "URGENT"
    from app.domain.models import Report
    report = db.query(Report).filter(Report.case_id == case.id).one()
    assert {s["section"] for s in report.content["sections"]} == {"safety_note"}


def test_d3_blocked_without_artifacts_no_report(db, case):
    case.question_text = "بدون نسخه چه دارویی بخرم؟"
    result = _run(db, case)
    assert result["safety_state"] == "BLOCKED"
    assert result["report"] is None
    from app.domain.models import Report
    assert db.query(Report).filter(Report.case_id == case.id).count() == 0


# ---------------- D-Q4: immutability depth ----------------

def test_dq4_snapshot_delete_rejected(db, case):
    _ingest(db, case)
    _run(db, case)
    from app.domain.models import AssessmentSnapshot
    from app.governance.immutability import ImmutabilityViolationError
    snap = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.case_id == case.id).one()
    db.delete(snap)
    with pytest.raises(ImmutabilityViolationError):
        db.flush()
    db.rollback()


def test_dq4_audit_delete_rejected(db, case):
    _ingest(db, case)
    _run(db, case)
    from app.domain.models import AuditEvent
    from app.governance.immutability import ImmutabilityViolationError
    ev = db.query(AuditEvent).filter(AuditEvent.case_id == case.id).first()
    db.delete(ev)
    with pytest.raises(ImmutabilityViolationError):
        db.flush()
    db.rollback()


def test_dq4_artifact_delete_rejected_explicitly(db, case):
    _ingest(db, case)
    db.commit()
    from app.governance.immutability import ImmutabilityViolationError
    art = case.artifacts[0]
    db.delete(art)
    with pytest.raises(ImmutabilityViolationError):
        db.flush()
    db.rollback()


def test_dq4_bulk_ops_on_protected_entities_banned_in_app_code():
    """Static architectural test: application code must not bulk-update/delete the
    immutability-protected entities (D-Q4). Derived-table authority switches are
    allowed (those tables are not protected)."""
    import os
    import re
    protected = ("AssessmentSnapshot", "AuditEvent", "Artifact")
    patterns = [
        re.compile(r"update\(\s*(" + "|".join(protected) + r")\b"),
        re.compile(r"delete\(\s*(" + "|".join(protected) + r")\b"),
        re.compile(r"query\(\s*(" + "|".join(protected) + r")\s*\)\s*\.\s*(update|delete)\("),
    ]
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "app")
    violations = []
    for root, _dirs, files in os.walk(app_dir):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    for pat in patterns:
                        if pat.search(line):
                            violations.append(f"{path}:{i}: {line.strip()}")
    assert violations == [], f"bulk ops on protected entities: {violations}"


# ---------------- D5: locator propagation ----------------

def test_d5_finding_locator_inherited_not_hardcoded(db, case):
    _ingest(db, case, text="Treatment Plan\nline one\nTooth 46: RCT\nlast")
    _run(db, case)
    from app.domain.models import Finding, ProvenanceRecord
    findings = db.query(Finding).filter(
        Finding.case_id == case.id, Finding.finding_type == "TREATMENT_ITEM").all()
    assert findings
    # expected line index comes from the actual extracted text, not an assumption
    text = case.artifacts[0].text_content
    line_index = next(i for i, line in enumerate(text.split("\n"))
                      if "RCT" in line)
    for f in findings:
        prov = db.query(ProvenanceRecord).filter(
            ProvenanceRecord.id == f.provenance_id).one()
        assert prov.source_span and prov.source_span.startswith("line:")
        assert prov.source_span.split(":")[1] == str(line_index)


# ---------------- D6: ontology scaling bug ----------------

def test_d6_scaling_synonym_fixed():
    from app.core.ontology.ontology import normalize_treatment
    assert normalize_treatment("جرم گیری") == "TREATMENT_SCALING"
    assert normalize_treatment("جرم‌گیری") == "TREATMENT_SCALING"


def test_d6_scaling_not_extraction():
    from app.core.ontology.ontology import normalize_treatment
    assert normalize_treatment("جرم گیری") != "TREATMENT_EXTRACTION"


# ---------------- D8: reuse contract parity ----------------

def test_d8_reuse_result_same_contract(db, case):
    _ingest(db, case)
    fresh = _run(db, case)
    reused = _run(db, case)
    fresh_keys = {k for k in fresh.keys() if k != "derivation_run_id"}
    reused_keys = {k for k in reused.keys() if k != "derivation_run_id"}
    assert fresh_keys == reused_keys, f"contract drift: {fresh_keys ^ reused_keys}"
    assert reused["reused"] is True
    assert reused["report_kind"] == fresh["report_kind"] == "STANDARD"
