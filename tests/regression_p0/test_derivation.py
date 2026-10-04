"""B/C/E/F/G: approved derivation, provenance, and reuse invariants."""
from copy import deepcopy

import pytest

from app.ai.gateway import ModelGateway
from app.ai.providers import MockProvider
from app.domain.enums import DerivationStatus, RunAuthority, TruthType
from app.domain.models import (Assessment, AssessmentSnapshot, Case, Claim,
                               EvidenceLink, Finding, KnowledgePack, ModelRun,
                               ProcessingRun, ProvenanceRecord, SafetyResult, public_id)
from app.pipeline.orchestrator import DERIVED_TABLES, run_case_pipeline


def _derivation(db, case):
    return db.query(ProcessingRun).filter(
        ProcessingRun.case_id == case.id, ProcessingRun.module == "pipeline",
        ProcessingRun.authority == RunAuthority.ACTIVE).one()


def _rows(db, run_id):
    """Include artifact/claim-scoped tables as well as those with case_id."""
    db.expire_all()  # authority switches use bulk SQL; do not trust identity-map state
    return {table.__tablename__: [(r.id, r.derivation_status) for r in
            db.query(table).filter(table.derivation_run_id == run_id).order_by(table.id)]
            for table in DERIVED_TABLES}


@pytest.mark.parametrize("check", ["authority", "reuse"])
def test_processing_other_case_preserves_authority_and_evidence(db, case, ingest_plan, check):
    ingest_plan(db, case)
    first = run_case_pipeline(db, case)
    assert first["status"] == "REPORT_READY" and first["evidence_links"] > 0
    run_a_id = _derivation(db, case).id
    before = _rows(db, run_a_id)
    assert before["evidence_links"]
    assert all(status == DerivationStatus.ACTIVE for rows in before.values()
               for _, status in rows)
    snap = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.derivation_run_id == run_a_id).one()
    frozen = deepcopy(snap.payload)

    other = Case(public_id=public_id("CASE"), user_id=case.user_id,
                 question_text="Explain tooth 36 treatment", dentist_recommendation_text="")
    db.add(other)
    db.flush()
    ingest_plan(db, other, "Treatment Plan\nTooth 36: Filling")
    second = run_case_pipeline(db, other)
    assert second["status"] == "REPORT_READY"
    run_b_id = _derivation(db, other).id
    other_before_reuse = _rows(db, run_b_id)
    after_b = _rows(db, run_a_id)
    reused = run_case_pipeline(db, case)
    assert reused["reused"] is True
    assert _derivation(db, case).id == run_a_id
    assert _rows(db, run_b_id) == other_before_reuse
    assert db.get(AssessmentSnapshot, snap.id).payload == frozen
    links = db.query(EvidenceLink).filter(EvidenceLink.derivation_run_id == run_a_id).all()
    assert links and all(db.get(Claim, link.claim_id).case_id == case.id and
                         db.get(Finding, link.finding_id).case_id == case.id for link in links)
    if check == "authority":
        assert after_b == before, "processing B changed A's derived authority"
        assert _rows(db, run_a_id) == before
    else:
        assert reused["evidence_links"] == first["evidence_links"], "A lost reusable evidence after B"


@pytest.fixture()
def revised_low_confidence_case(db, case, ingest_plan, monkeypatch):
    from app.pipeline import orchestrator

    class LowConfidence(MockProvider):
        def run(self, prompt, content, params):
            out = super().run(prompt, content, params)
            if prompt.prompt_id in ("treatment_plan_extractor", "invoice_extractor"):
                out["fields"] = [{**f, "confidence": 0.3} for f in out["fields"]]
                out["treatment_items"] = [{**i, "confidence": 0.3}
                                          for i in out.get("treatment_items", [])]
            return out

    class LowGateway(ModelGateway):
        def __init__(self, session):
            super().__init__(session)
            self.provider = LowConfidence()

    ingest_plan(db, case)
    with monkeypatch.context() as patch:
        patch.setattr(orchestrator, "ModelGateway", LowGateway)
        old = run_case_pipeline(db, case)
    assert old["safety_state"] == "MANUAL_REVIEW"
    old_run = _derivation(db, case).id
    low_ids = [c.id for c in db.query(Claim).filter(
        Claim.derivation_run_id == old_run, Claim.confidence < 0.5)]
    assert low_ids
    snap = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.derivation_run_id == old_run).one()
    frozen = deepcopy(snap.payload)
    case.question_text = "Explain this revised treatment plan for tooth 46"
    case.version += 1
    db.commit()
    current = run_case_pipeline(db, case)
    assert current["reused"] is False and current["status"] != "FAILED"
    new_run = _derivation(db, case).id
    assert new_run != old_run
    db.expire_all()
    assert all(db.get(Claim, i).derivation_status == DerivationStatus.SUPERSEDED
               and db.get(Claim, i).confidence == 0.3 for i in low_ids)
    assert db.get(AssessmentSnapshot, snap.id).payload == frozen
    assert db.query(SafetyResult).filter(SafetyResult.derivation_run_id == old_run).one().state.value == "MANUAL_REVIEW"
    material = db.query(Claim).filter(Claim.derivation_run_id == new_run,
                                     Claim.source_type == TruthType.DOCUMENT_EXTRACTED).all()
    assert material and all(c.confidence >= 0.5 for c in material)
    return case, current, new_run


def test_historical_low_confidence_does_not_contaminate_current_safety(db, revised_low_confidence_case):
    case, result, run_id = revised_low_confidence_case
    assert result["safety_state"] == "NORMAL", "historical low confidence leaked into current safety"
    assert db.query(SafetyResult).filter(SafetyResult.derivation_run_id == run_id).one().state.value == "NORMAL"


def test_current_assessment_excludes_historical_derivations(db, revised_low_confidence_case):
    # Call the existing endpoint function with the same session, as in existing
    # direct-route tests; HTTP serialization cannot change its selected rows.
    from app.api.routes import case_assessment
    case, result, run_id = revised_low_confidence_case
    current = db.query(Assessment).filter(Assessment.derivation_run_id == run_id).all()
    historical = db.query(Assessment).filter(Assessment.case_id == case.id,
                                            Assessment.derivation_run_id != run_id).all()
    assert current and historical
    assert all(a.derivation_status == DerivationStatus.SUPERSEDED for a in historical)
    response = case_assessment(case.public_id, case=case, db=db)
    assert len(response["assessments"]) == len(current), "current endpoint accumulated historical assessments"


def test_same_proposition_keeps_clinician_and_document_provenance(db, case, ingest_plan):
    case.question_text = "Explain the recommendation for tooth 46"
    case.dentist_recommendation_text = "Tooth 46: RCT recommended"
    artifact = ingest_plan(db, case, "Treatment Plan\nTooth 46: RCT recommended")
    result = run_case_pipeline(db, case)
    assert result["status"] == "REPORT_READY"
    run_id = _derivation(db, case).id
    finding = db.query(Finding).filter(Finding.derivation_run_id == run_id,
                                      Finding.finding_type == "TREATMENT_ITEM").one()
    assert finding.artifact_id == artifact.id
    assert (finding.normalized_subject, finding.normalized_object, finding.predicate) == (
        "TOOTH_46", "TREATMENT_ROOT_CANAL", "RECOMMENDED")
    claims = db.query(Claim).filter(Claim.derivation_run_id == run_id,
                                   Claim.subject == "TOOTH_46",
                                   Claim.treatment_id == "TREATMENT_ROOT_CANAL",
                                   Claim.modality == "RECOMMENDED").all()
    by_source = {source: [c for c in claims if c.source_type == source] for source in
                 (TruthType.CLINICIAN_REPORTED, TruthType.DOCUMENT_EXTRACTED)}
    assert all(by_source.values()), "same proposition lost independent clinician/document source"
    clinician, document = [by_source[s][0] for s in by_source]
    assert clinician.id != document.id and clinician.provenance_id != document.provenance_id
    assert artifact.public_id in document.source_reference
    for claim in (clinician, document):
        assert db.get(ProvenanceRecord, claim.provenance_id).truth_type == claim.source_type


@pytest.mark.parametrize("setting", ["model", "provider", "pack-version", "pack-identity"])
def test_material_processing_configuration_invalidates_reuse(
        db, case, ingest_plan, regression_settings, monkeypatch, setting):
    from app.ai import gateway
    from app.core.knowledge.pack import get_active_pack
    ingest_plan(db, case)
    first = run_case_pipeline(db, case)
    assert first["status"] == "REPORT_READY"
    old_run = _derivation(db, case).id
    snapshot = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.derivation_run_id == old_run).one()
    frozen = deepcopy(snapshot.payload)
    old_model_runs = db.query(ModelRun).count()
    if setting == "model":
        monkeypatch.setattr(regression_settings, "ai_model_name", "mock-evidence-v2")
    elif setting == "provider":
        class OfflineOpenRouter(MockProvider):
            name = "openrouter"

            def __init__(self, **kwargs):
                pass  # no credentials, HTTP client, or network

        monkeypatch.setattr(gateway, "OpenRouterProvider", OfflineOpenRouter)
        monkeypatch.setattr(regression_settings, "ai_provider", "openrouter")
        assert ModelGateway(db).provider.name == "openrouter"
    else:
        prior = get_active_pack(db)
        prior.active = False
        replacement = KnowledgePack(
            knowledge_pack_id=prior.knowledge_pack_id if setting == "pack-version" else "synthetic-alternate-pack",
            version="synthetic-v2" if setting == "pack-version" else prior.version,
            status=prior.status, review_status=prior.review_status,
            content=deepcopy(prior.content), active=True)
        db.add(replacement)
        db.commit()
        assert get_active_pack(db).id == replacement.id
    second = run_case_pipeline(db, case)
    db.expire_all()
    assert db.get(AssessmentSnapshot, snapshot.id).payload == frozen
    assert second["reused"] is False, f"material {setting} change reused an old derivation"
    assert second["status"] == "REPORT_READY"
    assert _derivation(db, case).id != old_run
    assert db.query(ModelRun).count() > old_model_runs


@pytest.mark.parametrize("question,safety,status", [
    ("Explain my options", "NORMAL", "NEEDS_MORE_EVIDENCE"),
    ("I have pain", "CAUTION", "NEEDS_MORE_EVIDENCE"),
    ("بدون نسخه چه دارویی بخرم؟", "BLOCKED", "MANUAL_REVIEW_REQUIRED"),
], ids=["normal", "caution", "blocked"])
def test_reused_reportless_terminal_result_preserves_safety(db, case, question, safety, status):
    case.question_text = question
    first = run_case_pipeline(db, case)
    assert first["safety_state"] == safety and first["status"] == status
    assert first["report"] is first["snapshot"] is None
    run_id = _derivation(db, case).id
    before = _rows(db, run_id)
    count = db.query(ProcessingRun).count()
    second = run_case_pipeline(db, case)
    assert second["reused"] is True
    assert _derivation(db, case).id == run_id
    assert db.query(ProcessingRun).count() == count
    assert _rows(db, run_id) == before
    keys = ("status", "safety_state", "report", "snapshot", "report_kind")
    assert {k: second[k] for k in keys} == {k: first[k] for k in keys}
