"""Architectural invariant tests (release blockers INV-01..INV-08)."""


def test_inv02_no_unvalidated_llm_output(db, case, pdf_bytes):
    """Gateway rejects outputs violating the schema; e.g. confidence > 1 or tooth 900."""
    import pytest
    from app.ai.gateway import ModelGateway
    from app.ai.prompts import get_prompt
    from app.ai.providers import MockProvider
    from app.ai.schemas import ClassificationOutput
    from app.errors import ExtractionValidationError

    class RogueProvider(MockProvider):
        name = "rogue"

        def run(self, prompt, content, params):
            return {"category": "RADIOGRAPH", "subtype": "OPG", "confidence": 1.43}

    gw = ModelGateway(db)
    gw.provider = RogueProvider()
    with pytest.raises(ExtractionValidationError):
        gw.run("artifact_classifier", ClassificationOutput, "{},x")


def test_inv03_extracted_facts_have_provenance(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import Finding
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    from app.pipeline.orchestrator import run_case_pipeline
    run_case_pipeline(db, case)
    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    assert all(f.provenance_id is not None for f in findings)


def test_inv04_truth_types_distinguishable(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import Claim
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    from app.pipeline.orchestrator import run_case_pipeline
    run_case_pipeline(db, case)
    claims = db.query(Claim).filter(Claim.case_id == case.id).all()
    source_types = {c.source_type for c in claims}
    assert len(source_types) >= 2  # not silently merged


def test_inv05_assessment_uses_knowledge_pack(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import Assessment
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    from app.pipeline.orchestrator import run_case_pipeline
    run_case_pipeline(db, case)
    assessments = db.query(Assessment).filter(Assessment.case_id == case.id).all()
    assert assessments
    assert all(a.knowledge_pack_version for a in assessments)


def test_inv06_report_from_immutable_snapshot(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import AssessmentSnapshot, Report
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    from app.pipeline.orchestrator import run_case_pipeline
    run_case_pipeline(db, case)
    report = db.query(Report).filter(Report.case_id == case.id).one()
    snapshot = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.id == report.snapshot_id).one()
    assert snapshot.immutable is True
    assert snapshot.versions["knowledge_pack"]
    assert snapshot.versions["ontology"]
    # mutating case afterwards does not mutate snapshot
    old_hash = snapshot.content_hash
    case.question_text = "changed question"
    db.flush()
    db.refresh(snapshot)
    assert snapshot.content_hash == old_hash
    assert snapshot.payload["question"] != "changed question"


def test_inv07_low_confidence_fails_closed(db, case):
    """Case with no artifacts at all: pipeline must not fabricate certainty."""
    from app.domain.models import Assessment
    from app.pipeline.orchestrator import run_case_pipeline
    _run = run_case_pipeline(db, case)
    statuses = {a.status.value for a in db.query(Assessment).filter(
        Assessment.case_id == case.id).all()}
    assert statuses <= {"INSUFFICIENT_EVIDENCE", "NOT_ASSESSABLE"}


def test_inv08_versions_recorded_on_model_runs(db, case, pdf_bytes):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.models import ModelRun
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf", data=pdf_bytes)
    from app.pipeline.orchestrator import run_case_pipeline
    run_case_pipeline(db, case)
    runs = db.query(ModelRun).all()
    assert runs
    for r in runs:
        assert r.prompt_id and r.prompt_version and r.schema_version
        assert r.provider and r.model
