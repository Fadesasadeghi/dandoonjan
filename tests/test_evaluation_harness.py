"""Regression/evaluation harness (P0-12 hardened).

Every key in a golden/adversarial/safety spec is ENFORCED. Unknown spec keys are
rejected (never silently ignored). Cases needing special providers use the
"provider" input key (deterministic in-repo test providers only).
"""
import json
import os

import pymupdf
import pytest

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "evaluation")

CASE_FILES = [
    (os.path.join(EVAL_DIR, "golden_cases", "golden_rct_treatment_plan.json"), None),
    (os.path.join(EVAL_DIR, "adversarial", "adversarial_injection.json"), None),
    (os.path.join(EVAL_DIR, "safety", "safety_urgent.json"), None),
    (os.path.join(EVAL_DIR, "safety", "safety_blocked.json"), None),
    (os.path.join(EVAL_DIR, "adversarial", "adversarial_tooth_900.json"), None),
    (os.path.join(EVAL_DIR, "adversarial", "adversarial_contradictory.json"), None),
]

ALLOWED_SPEC_KEYS = {"golden_case_id", "description", "inputs", "expected",
                     "forbidden_report_statements"}
ALLOWED_INPUT_KEYS = {"question", "dentist_recommendation", "context", "artifacts",
                      "provider"}
ALLOWED_ARTIFACT_KEYS = {"filename", "text", "classification", "extracted_fields",
                         "finding_types"}
ALLOWED_EXPECTED_KEYS = {"classification", "extracted_fields", "normalized_fields",
                         "findings", "claim_types", "claim_propositions",
                         "claim_source_types", "evidence_links_present",
                         "evidence_gaps_present", "gap_types",
                         "assessment_statuses", "forbidden_statuses", "safety_state",
                         "case_status", "report_sections", "report_must_contain",
                         "forbidden_relationships", "forbidden_claim_text", "no_report",
                         "treatment_item_pairs"}


def _text_to_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in text.split("\n"):
        page.insert_text((72, y), line)
        y += 16
    data = doc.tobytes()
    doc.close()
    return data


def _load_spec(path):
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    unknown = set(spec) - ALLOWED_SPEC_KEYS
    assert not unknown, f"{path}: unsupported spec keys {unknown} (must be enforced)"
    unknown_in = set(spec.get("inputs", {})) - ALLOWED_INPUT_KEYS
    assert not unknown_in, f"{path}: unsupported input keys {unknown_in}"
    for a in spec["inputs"].get("artifacts", []):
        unknown_a = set(a) - ALLOWED_ARTIFACT_KEYS
        assert not unknown_a, f"{path}: unsupported artifact keys {unknown_a}"
    unknown_exp = set(spec.get("expected", {})) - ALLOWED_EXPECTED_KEYS
    assert not unknown_exp, f"{path}: unsupported expected keys {unknown_exp}"
    return spec


def _load_case(db, spec):
    from app.core.artifacts.ingestion import ingest_artifact
    from app.domain.enums import CaseStatus
    from app.domain.models import Case, User, public_id
    user = User(public_id=public_id("USR"))
    db.add(user)
    db.flush()
    case = Case(public_id=public_id("CASE"), user_id=user.id, status=CaseStatus.CREATED,
                question_text=spec["inputs"].get("question", ""),
                context_text=spec["inputs"].get("context", ""),
                dentist_recommendation_text=spec["inputs"].get("dentist_recommendation", ""))
    db.add(case)
    db.flush()
    for a in spec["inputs"]["artifacts"]:
        ingest_artifact(db, case, filename=a["filename"],
                        declared_mime="application/pdf", data=_text_to_pdf(a["text"]))
    return case


def _make_gateway(db, provider_name):
    """Deterministic in-repo test providers only (no external calls)."""
    from app.ai.gateway import ModelGateway

    class GW(ModelGateway):
        def __init__(self, db_):
            super().__init__(db_)
            if provider_name == "invalid_tooth":
                class P:
                    name = "invalid_tooth"

                    def run(self, prompt, content, params):
                        if prompt.prompt_id == "claim_builder":
                            return {"claims": [
                                {"claim_type": "ROOT_CANAL_REQUIRED",
                                 "subject": "TOOTH_900", "predicate": "RECOMMENDS",
                                 "object_value": "TREATMENT_ROOT_CANAL",
                                 "confidence": 0.9}]}
                        from app.ai.providers import MockProvider
                        return MockProvider().run(prompt, content, params)
                self.provider = P()
            elif provider_name == "empty_extraction":
                class P:
                    name = "empty_extraction"

                    def run(self, prompt, content, params):
                        if prompt.prompt_id in ("treatment_plan_extractor",
                                                "invoice_extractor"):
                            return {"fields": []}
                        from app.ai.providers import MockProvider
                        return MockProvider().run(prompt, content, params)
                self.provider = P()
            else:
                raise ValueError(f"unknown test provider {provider_name}")

    return GW


@pytest.mark.parametrize("case_path,provider", CASE_FILES,
                         ids=lambda p: os.path.basename(p) if isinstance(p, str) else "")
def test_evaluation_case(db, case_path, provider):
    spec = _load_spec(case_path)
    case = _load_case(db, spec)
    from app.pipeline import orchestrator as orc
    if spec["inputs"].get("provider"):
        GW = _make_gateway(db, spec["inputs"]["provider"])
        monkey_provider = GW
        orig = orc.ModelGateway
        orc.ModelGateway = GW
        try:
            result = orc.run_case_pipeline(db, case)
        finally:
            orc.ModelGateway = orig
    else:
        result = orc.run_case_pipeline(db, case)

    expected = spec["expected"]
    from app.domain.enums import EvidenceRelationship
    from app.domain.models import (Assessment, Claim, EvidenceGap, EvidenceLink, Finding,
                                   ExtractedField, Report)

    claims = db.query(Claim).filter(Claim.case_id == case.id).all()
    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    gaps = db.query(EvidenceGap).filter(EvidenceGap.case_id == case.id).all()
    links = db.query(EvidenceLink).join(
        Claim, EvidenceLink.claim_id == Claim.id).filter(Claim.case_id == case.id).all()
    assessments = db.query(Assessment).filter(Assessment.case_id == case.id).all()
    reports = db.query(Report).filter(Report.case_id == case.id).all()

    # per-artifact expectations
    for a_spec, artifact in zip(spec["inputs"]["artifacts"], case.artifacts):
        if "classification" in a_spec:
            assert artifact.category.value == a_spec["classification"]["category"]
            assert artifact.subtype.value == a_spec["classification"]["subtype"]
        if "finding_types" in a_spec:
            types = {f.finding_type for f in findings
                     if f.artifact_id == artifact.id}
            for t in a_spec["finding_types"]:
                assert t in types, f"missing finding {t} for {a_spec['filename']}"
        if "extracted_fields" in a_spec:
            fields = db.query(ExtractedField).join(
                __import__("app.domain.models", fromlist=["Extraction"]).Extraction,
                ExtractedField.extraction_id ==
                __import__("app.domain.models", fromlist=["Extraction"]).Extraction.id
            ).filter(
                __import__("app.domain.models", fromlist=["Extraction"]).Extraction.artifact_id
                == artifact.id).all()
            for want in a_spec["extracted_fields"]:
                match = [f for f in fields
                         if f.field_name == want["field_name"]
                         and f.normalized_value == want["normalized_value"]]
                assert match, f"missing normalized field {want}"

    # claim-level expectations
    if "claim_types" in expected:
        got = {c.claim_type.value for c in claims
               if c.claim_type.value != "OTHER"}
        for t in expected["claim_types"]:
            assert t in got, f"missing claim type {t}; got {got}"
    if "claim_propositions" in expected:
        # compositional propositions: "<TREATMENT>|<MODALITY>" with any source
        got = {f"{c.treatment_id}|{c.modality.value}" for c in claims
               if c.claim_type.value == "TREATMENT" and c.modality}
        for prop in expected["claim_propositions"]:
            assert prop in got, f"missing proposition {prop}; got {got}"
    if "treatment_item_pairs" in expected:
        from app.domain.models import TreatmentItem
        pairs = {(i.tooth_id, i.treatment_id)
                 for i in db.query(TreatmentItem).all()}
        want = {(t, tr) for t, tr in expected["treatment_item_pairs"]}
        assert pairs == want, f"treatment item pairs {pairs} != {want}"
    if "claim_source_types" in expected:
        got = {c.source_type.value for c in claims}
        for t in expected["claim_source_types"]:
            assert t in got
    if "evidence_links_present" in expected:
        assert bool(links) == expected["evidence_links_present"]
    if "evidence_gaps_present" in expected:
        assert bool(gaps) == expected["evidence_gaps_present"]
    if "gap_types" in expected:
        got = {g.gap_type for g in gaps}
        for t in expected["gap_types"]:
            assert t in got, f"missing gap {t}; got {got}"
    if "assessment_statuses" in expected:
        got = {a.status.value for a in assessments}
        forbidden = set(expected.get("forbidden_statuses", []))
        assert got - forbidden <= set(expected["assessment_statuses"]), got
    if "forbidden_relationships" in expected:
        for l in links:
            assert l.relationship_type.value not in expected["forbidden_relationships"]
    if "forbidden_claim_text" in expected:
        blob = " ".join(c.object_value + " " + c.source_reference for c in claims).lower()
        for phrase in expected["forbidden_claim_text"]:
            assert phrase.lower() not in blob
    if "safety_state" in expected:
        assert result["safety_state"] == expected["safety_state"]
    if "case_status" in expected:
        assert case.status.value == expected["case_status"]
    if "no_report" in expected:
        assert reports == []
    if "report_sections" in expected:
        assert reports, "report expected"
        got_sections = {s["section"] for s in reports[-1].content["sections"]}
        assert got_sections == set(expected["report_sections"]), got_sections
    if "report_must_contain" in expected:
        text = " ".join(s["text"] for s in reports[-1].content["sections"])
        for phrase in expected["report_must_contain"]:
            assert phrase in text

    # forbidden statements never appear in any generated report
    for report in reports:
        text = " ".join(s["text"] for s in report.content["sections"]).lower()
        for phrase in spec.get("forbidden_report_statements", []):
            assert phrase.lower() not in text, f"forbidden phrase in report: {phrase}"
