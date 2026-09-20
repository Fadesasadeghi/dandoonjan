"""Pipeline integration tests (offline, mock provider)."""


def _run_pipeline(db, case):
    from app.pipeline.orchestrator import run_case_pipeline
    return run_case_pipeline(db, case)


def test_full_pipeline_with_treatment_plan(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename="treatment_plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    result = _run_pipeline(db, case)
    assert result["report"] is not None
    assert case.status.value == "REPORT_READY"


def test_invoice_only_yields_insufficient_evidence(db, case):
    """Only invoice uploaded + RCT question -> INSUFFICIENT_EVIDENCE, not a diagnosis."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice / صورت حساب - جمع کل: 2,000,000 toman")
    data = doc.tobytes()
    doc.close()
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename="invoice.pdf", declared_mime="application/pdf", data=data)
    result = _run_pipeline(db, case)
    from app.domain.models import Assessment
    statuses = {a.status.value for a in db.query(Assessment).filter(
        Assessment.case_id == case.id).all()}
    assert "INSUFFICIENT_EVIDENCE" in statuses
    assert "SUPPORTED" not in statuses


def test_processing_runs_recorded(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.enums import ProcessingRunStatus
    from app.domain.models import ProcessingRun
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    _run_pipeline(db, case)
    runs = db.query(ProcessingRun).filter(ProcessingRun.case_id == case.id).all()
    modules = {r.module for r in runs}
    assert {"classification", "quality_gate", "extraction", "claims", "assessment",
            "snapshot_report"} <= modules
    assert all(r.status == ProcessingRunStatus.SUCCEEDED for r in runs)


def test_snapshot_created_and_report_derives_from_it(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import Report
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    result = _run_pipeline(db, case)
    report = db.query(Report).filter(Report.case_id == case.id).one()
    assert result["snapshot"] is not None
    assert report.snapshot_id


def test_findings_have_provenance(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.enums import TruthType
    from app.domain.models import Finding, ProvenanceRecord
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    _run_pipeline(db, case)
    findings = db.query(Finding).filter(Finding.case_id == case.id,
                                        Finding.truth_type == TruthType.DOCUMENT_EXTRACTED).all()
    assert findings
    for f in findings:
        assert f.provenance_id is not None
        prov = db.query(ProvenanceRecord).filter(
            ProvenanceRecord.id == f.provenance_id).one()
        assert prov.artifact_id is not None


def test_claim_vs_finding_kept_apart(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import Claim, Finding
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    _run_pipeline(db, case)
    claims = db.query(Claim).filter(Claim.case_id == case.id).all()
    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    assert claims and findings
    # Treatment proposition claim exists (reported or document-derived)
    assert any(c.claim_type.value == "TREATMENT"
               and c.treatment_id == "TREATMENT_ROOT_CANAL" for c in claims)
    assert any(f.finding_type == "TREATMENT_ITEM"
               and f.normalized_object == "TREATMENT_ROOT_CANAL" for f in findings)


def test_patient_reported_vs_document_extracted_distinct(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.enums import TruthType
    from app.domain.models import Claim
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    _run_pipeline(db, case)
    claims = db.query(Claim).filter(Claim.case_id == case.id).all()
    sources = {c.source_type.value for c in claims}
    assert "PATIENT_REPORTED" in sources
    assert "CLINICIAN_REPORTED" in sources
    # P0-01-B: clinician-reported treatment claims are NOT duplicated by
    # MODEL_INFERRED claims of the same type + subject
    clinician = {(c.claim_type.value, c.subject) for c in claims
                 if c.source_type == TruthType.CLINICIAN_REPORTED}
    inferred = {(c.claim_type.value, c.subject) for c in claims
                if c.source_type == TruthType.MODEL_INFERRED}
    assert not (clinician & inferred), f"duplicated claims: {clinician & inferred}"
