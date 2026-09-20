"""P0 acceptance tests updated to P0.1 locked semantics (D-Q2/D-Q3):
- Claims are compositional: claim_type=TREATMENT + treatment_id + modality.
- Findings of type TREATMENT_ITEM carry the atomic tooth-treatment relationship.
- No cartesian reconstruction; subject-safe evidence links; no circular evidence."""
import pymupdf
import pytest


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


PLAN_PDF_TEXT = "Treatment Plan\nTooth 46: RCT\nCrown recommended after RCT"


@pytest.fixture()
def case_with_plan(db, case):
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf",
                    data=_pdf(PLAN_PDF_TEXT))
    return case


def _run(db, case):
    from app.pipeline.orchestrator import run_case_pipeline
    return run_case_pipeline(db, case)


def _treatment_claims(db, case, treatment_id):
    from app.domain.models import Claim
    return db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.claim_type == "TREATMENT",
        Claim.treatment_id == treatment_id).all()


# ---------------- P0-01 ----------------

def test_p0_01_a_evidence_links_point_to_clinician_claim(db, case_with_plan):
    _run(db, case_with_plan)
    from app.domain.enums import TruthType
    from app.domain.models import EvidenceLink
    clinician = [c for c in _treatment_claims(db, case_with_plan, "TREATMENT_ROOT_CANAL")
                 if c.source_type == TruthType.CLINICIAN_REPORTED]
    assert clinician, "clinician-reported RCT claim must exist"
    links = db.query(EvidenceLink).filter(
        EvidenceLink.claim_id == clinician[0].id).all()
    assert links, "clinician-reported claim must be connected in the evidence graph"
    assert all(l.claim_id == clinician[0].id for l in links)


def test_p0_01_b_no_duplicate_model_inferred_claim(db, case_with_plan):
    _run(db, case_with_plan)
    from app.domain.enums import TruthType
    claims = _treatment_claims(db, case_with_plan, "TREATMENT_ROOT_CANAL")
    keys = [(c.source_type, c.subject, c.treatment_id,
             c.modality.value if c.modality else None) for c in claims]
    assert len(set(keys)) == len(keys), "no duplicate (source, subject, treatment, modality)"
    clinician_keys = {(c.subject, c.modality.value if c.modality else None)
                      for c in claims if c.source_type == TruthType.CLINICIAN_REPORTED}
    inferred_keys = {(c.subject, c.modality.value if c.modality else None)
                     for c in claims if c.source_type == TruthType.MODEL_INFERRED}
    assert not (clinician_keys & inferred_keys)


def test_p0_01_c_reported_claims_distinguishable_after_assessment(db, case_with_plan):
    _run(db, case_with_plan)
    from app.domain.enums import TruthType
    from app.domain.models import Assessment, Claim
    assessments = db.query(Assessment).filter(
        Assessment.case_id == case_with_plan.id).all()
    assert assessments
    for a in assessments:
        claim = db.query(Claim).filter(Claim.id == a.claim_id).one()
        assert claim.source_type in tuple(TruthType)
    clinician_ids = {c.id for c in db.query(Claim).filter(
        Claim.case_id == case_with_plan.id,
        Claim.source_type == TruthType.CLINICIAN_REPORTED).all()}
    assert any(a.claim_id in clinician_ids for a in assessments)


# ---------------- P0-02 ----------------

class EmptyExtractionProvider:
    """Deterministic test provider: extraction returns nothing (P0-02-A)."""
    name = "empty_extraction"

    def run(self, prompt, content, params):
        if prompt.prompt_id in ("treatment_plan_extractor", "invoice_extractor"):
            return {"fields": [], "treatment_items": []}
        from app.ai.providers import MockProvider
        return MockProvider().run(prompt, content, params)


def test_p0_02_a_no_finding_without_extraction(db, case_with_plan):
    from app.ai.gateway import ModelGateway
    gw = ModelGateway(db)
    gw.provider = EmptyExtractionProvider()

    from app.pipeline import stages
    artifact = case_with_plan.artifacts[0]
    artifact.text_content = PLAN_PDF_TEXT
    stages.classify_artifact(db, gw, artifact)
    stages.run_quality_gate(db, artifact)
    extraction = stages.extract_structured(db, gw, artifact)
    findings = stages.build_findings_from_extraction(db, artifact, extraction)
    treatment_findings = [f for f in findings
                          if f.finding_type in ("TREATMENT_ITEM", "TREATMENT_MENTION")]
    assert treatment_findings == [], "raw text must not become findings without extraction"


def test_p0_02_b_finding_created_from_valid_extraction(db, case_with_plan):
    _run(db, case_with_plan)
    from app.domain.models import Finding
    findings = db.query(Finding).filter(
        Finding.case_id == case_with_plan.id,
        Finding.finding_type == "TREATMENT_ITEM").all()
    assert findings
    assert {f.normalized_object for f in findings} >= {"TREATMENT_ROOT_CANAL",
                                                       "TREATMENT_CROWN"}
    assert all(f.treatment_item_id is not None for f in findings)


def test_p0_02_c_finding_provenance_chain_to_artifact(db, case_with_plan):
    _run(db, case_with_plan)
    from app.domain.models import Artifact, Finding, ProvenanceRecord
    findings = db.query(Finding).filter(
        Finding.case_id == case_with_plan.id,
        Finding.finding_type == "TREATMENT_ITEM").all()
    assert findings
    for f in findings:
        prov = db.query(ProvenanceRecord).filter(
            ProvenanceRecord.id == f.provenance_id).one()
        artifact = db.query(Artifact).filter(Artifact.id == prov.artifact_id).one()
        assert artifact.public_id == case_with_plan.artifacts[0].public_id
        # D5: locator inherited from source (line span), never a hardcoded page lie
        assert prov.source_span is not None


# ---------------- P0-03 ----------------

class InvalidToothProvider:
    """Malicious test provider: emits TOOTH_900 claim candidate (P0-03-A)."""
    name = "invalid_tooth"

    def run(self, prompt, content, params):
        if prompt.prompt_id == "claim_builder":
            return {"claims": [{"claim_type": "TREATMENT", "subject": "TOOTH_900",
                                "predicate": "REQUIRES_TREATMENT",
                                "object_value": "TREATMENT_ROOT_CANAL",
                                "treatment": "TREATMENT_ROOT_CANAL",
                                "modality": "REQUIRED",
                                "confidence": 0.9}]}
        from app.ai.providers import MockProvider
        return MockProvider().run(prompt, content, params)


def test_p0_03_a_invalid_tooth_claim_not_persisted(db, case_with_plan, monkeypatch):
    from app.ai.gateway import ModelGateway
    from app.pipeline import orchestrator as orc

    class GW(ModelGateway):
        def __init__(self, db_):
            super().__init__(db_)
            self.provider = InvalidToothProvider()

    monkeypatch.setattr(orc, "ModelGateway", GW)
    result = _run(db, case_with_plan)
    from app.domain.models import Claim
    bad = db.query(Claim).filter(Claim.case_id == case_with_plan.id,
                                 Claim.subject == "TOOTH_900").all()
    assert bad == [], "TOOTH_900 claim must never persist"
    assert result["status"] in ("FAILED", "MANUAL_REVIEW_REQUIRED")


def test_p0_03_b_unknown_treatment_rejected(db, case_with_plan, monkeypatch):
    from app.ai.gateway import ModelGateway
    from app.core.ontology.ontology import OntologyValidationError, validate_treatment
    from app.domain.enums import ClaimType, Modality
    from app.pipeline import orchestrator as orc
    from app.pipeline.claims import validate_claim_semantics

    class UnknownTreatment(InvalidToothProvider):
        def run(self, prompt, content, params):
            if prompt.prompt_id == "claim_builder":
                return {"claims": [{"claim_type": "TREATMENT",
                                    "subject": "TOOTH_46",
                                    "predicate": "REQUIRES_TREATMENT",
                                    "object_value": "TREATMENT_WHITENING",
                                    "treatment": "TREATMENT_WHITENING",
                                    "modality": "REQUIRED",
                                    "confidence": 0.9}]}
            return InvalidToothProvider.run(self, prompt, content, params)

    class GW(ModelGateway):
        def __init__(self, db_):
            super().__init__(db_)
            self.provider = UnknownTreatment()

    monkeypatch.setattr(orc, "ModelGateway", GW)
    result = _run(db, case_with_plan)
    from app.domain.models import Claim
    bad = db.query(Claim).filter(Claim.case_id == case_with_plan.id,
                                 Claim.treatment_id == "TREATMENT_WHITENING").all()
    assert bad == []

    with pytest.raises(OntologyValidationError):
        validate_claim_semantics(ClaimType.TREATMENT, "TOOTH_46",
                                 "TREATMENT_WHITENING", Modality.REQUIRED)
    with pytest.raises(OntologyValidationError):
        validate_treatment("TREATMENT_WHITENING")


def test_p0_03_c_no_invalid_ontology_ids_in_core_state(db, case_with_plan):
    from app.core.ontology.ontology import TOOTH_IDENTIFIERS, TREATMENT_IDENTIFIERS
    from app.domain.models import Claim, ExtractedField, Finding, TreatmentItem
    _run(db, case_with_plan)
    for field in db.query(ExtractedField).all():
        v = field.normalized_value
        if v and v.startswith("TOOTH_"):
            assert v in TOOTH_IDENTIFIERS
    for it in db.query(TreatmentItem).all():
        assert it.treatment_id in TREATMENT_IDENTIFIERS
        if it.tooth_id:
            assert it.tooth_id in TOOTH_IDENTIFIERS
    for f in db.query(Finding).all():
        for v in (f.normalized_subject, f.normalized_object):
            if v and v.startswith("TOOTH_"):
                assert v in TOOTH_IDENTIFIERS
            if v and v.startswith("TREATMENT_"):
                assert v in TREATMENT_IDENTIFIERS
    for c in db.query(Claim).all():
        if c.subject.startswith("TOOTH_"):
            assert c.subject in TOOTH_IDENTIFIERS
        if c.treatment_id:
            assert c.treatment_id in TREATMENT_IDENTIFIERS


# ---------------- D-Q3: modality semantics ----------------

def test_dq3_recommendation_is_not_necessity(db, case_with_plan):
    """A plan listing RCT yields PLANNED/RECOMMENDED, never REQUIRED (C)."""
    from app.domain.enums import Modality, TruthType
    _run(db, case_with_plan)
    documented = [c for c in _treatment_claims(db, case_with_plan,
                                               "TREATMENT_ROOT_CANAL")
                  if c.source_type == TruthType.DOCUMENT_EXTRACTED]
    assert documented
    assert all(c.modality != Modality.REQUIRED for c in documented)


def test_dq3_explicit_necessity_language_yields_required(db, case):
    case.dentist_recommendation_text = "دکتر گفت این دندان حتماً باید عصب‌کشی شود"
    case.question_text = "آیا واقعاً لازم است؟"
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf",
                    data=_pdf("Treatment Plan\nTooth 46: RCT"))
    _run(db, case)
    from app.domain.enums import Modality, TruthType
    clinician = [c for c in _treatment_claims(db, case, "TREATMENT_ROOT_CANAL")
                 if c.source_type == TruthType.CLINICIAN_REPORTED]
    assert clinician
    assert clinician[0].modality == Modality.REQUIRED


def test_dq3_plan_listing_stays_planned(db, case):
    case.dentist_recommendation_text = ""
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf",
                    data=_pdf("Treatment Plan\nTooth 46: RCT"))
    _run(db, case)
    from app.domain.enums import Modality, TruthType
    documented = [c for c in _treatment_claims(db, case, "TREATMENT_ROOT_CANAL")
                  if c.source_type == TruthType.DOCUMENT_EXTRACTED]
    assert documented
    assert documented[0].modality == Modality.PLANNED
    assert documented[0].subject == "TOOTH_46"


# ---------------- D-Q2: no cartesian, atomic relationships ----------------

def test_dq2_two_teeth_two_treatments_no_cartesian(db, case):
    """'Tooth 46: RCT / Tooth 36: Filling' must yield exactly two atomic
    relationships — not a teeth x treatments product."""
    from app.core.artifacts.ingestion import ingest_artifact
    case.dentist_recommendation_text = ""
    ingest_artifact(db, case, filename="plan.pdf", declared_mime="application/pdf",
                    data=_pdf("Treatment Plan\nTooth 46: RCT\nTooth 36: Filling"))
    _run(db, case)
    from app.domain.models import Claim, TreatmentItem
    items = db.query(TreatmentItem).all()
    pairs = {(i.tooth_id, i.treatment_id) for i in items}
    assert pairs == {("TOOTH_46", "TREATMENT_ROOT_CANAL"),
                     ("TOOTH_36", "TREATMENT_FILLING")}
    document_claims = db.query(Claim).filter(
        Claim.case_id == case.id, Claim.claim_type == "TREATMENT").all()
    pairs_claims = {(c.subject, c.treatment_id) for c in document_claims}
    assert pairs_claims == {("TOOTH_46", "TREATMENT_ROOT_CANAL"),
                            ("TOOTH_36", "TREATMENT_FILLING")}


def test_dq2_tooth_only_reference_stays_independent(db, case):
    case.dentist_recommendation_text = ""
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename="note.pdf", declared_mime="application/pdf",
                    data=_pdf("Clinical note\nTooth 46 is sensitive"))
    _run(db, case)
    from app.domain.models import Finding
    teeth = db.query(Finding).filter(Finding.case_id == case.id,
                                     Finding.finding_type == "TOOTH_REFERENCE").all()
    assert teeth and teeth[0].normalized_subject == "TOOTH_46"
    assert _treatment_claims(db, case, "TREATMENT_ROOT_CANAL") == []


# ---------------- §15 no circular evidence ----------------

def test_no_circular_evidence_mention_is_not_proof(db, case_with_plan):
    from app.domain.enums import EvidenceRelationship, TruthType
    from app.domain.models import Assessment, EvidenceLink
    _run(db, case_with_plan)
    claims = _treatment_claims(db, case_with_plan, "TREATMENT_ROOT_CANAL")
    assert claims
    for c in claims:
        links = db.query(EvidenceLink).filter(EvidenceLink.claim_id == c.id).all()
        # a mention/plan/recommendation never SUPPORTS the treatment proposition
        assert all(l.relationship_type != EvidenceRelationship.SUPPORTS for l in links)
    clinician = [c for c in claims if c.source_type == TruthType.CLINICIAN_REPORTED]
    a = db.query(Assessment).filter(Assessment.claim_id == clinician[0].id).one()
    assert a.status.value == "INSUFFICIENT_EVIDENCE"
