"""Immutable Assessment Snapshot + Patient Report Composer (D-Q1/D-Q3/D4).

RULE 11: reports are generated ONLY from immutable, integrity-verified snapshots,
scoped to ONE authoritative derivation (B): never "whatever rows exist for the case".
Composer may never downgrade the Safety Gate state (RULE 10). MANUAL_REVIEW yields
an explicit review-pending report only; BLOCKED yields no report. Recommendation is
not necessity (C): report wording distinguishes recommendation-existence from need.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.schemas import ReportOutput
from app.domain.enums import (AssessmentStatus, ClaimType, ConfidenceLevel,
                              DerivationStatus, Modality, SafetyState)
from app.domain.models import (Assessment, AssessmentSnapshot, Case, Claim, EvidenceGap,
                               EvidenceLink, Extraction, ExtractedField, Finding,
                               ModelRun, ProcessingRun, ProvenanceRecord, Report,
                               SafetyResult, TreatmentItem, public_id)
from app.errors import SafetyBlockedError
from app.governance.immutability import snapshot_content_hash, verify_snapshot_integrity
from app.governance.record import audit
from app.pipeline.assessment import FORBIDDEN_PHRASES

REPORT_SCHEMA_VERSION = "report-schema-v2"
ONTOLOGY_VERSION = "onto-v1.0.0"

SAFETY_NOTE_FA = {
    SafetyState.NORMAL: "این گزارش توضیح شواهد است و جایگزین معاینه دندان‌پزشک نیست.",
    SafetyState.CAUTION: "در صورت وجود درد یا تورم، پیگیری با دندان‌پزشک لازم است. "
                         "این گزارش جایگزین معاینه نیست.",
    SafetyState.URGENT_EVALUATION: "⚠️ بر اساس توصیف شما، این وضعیت نیاز به بررسی "
                                   "فوری توسط دندان‌پزشک یا خدمات اورژانس دارد. "
                                   "لطفاً منتظر نمانید و در اسرع وقت مراجعه کنید.",
}
REVIEW_PENDING_NOTE_FA = ("⏸ این پرونده در وضعیت بررسی دستی است. گزارش ارزیابی شواهد "
                          "هنوز تولید نشده و تا تکمیل بررسی در دسترس نیست.")

STATUS_FA = {
    AssessmentStatus.SUPPORTED: "شواهد فعلی از این ادعا پشتیبانی می‌کند",
    AssessmentStatus.PARTIALLY_SUPPORTED: "شواهد فعلی تا حدی از این ادعا پشتیبانی می‌کند",
    AssessmentStatus.INSUFFICIENT_EVIDENCE:
        "مدارک فعلی برای قضاوت درباره این ادعا کافی نیست",
    AssessmentStatus.CONTRADICTED: "بین مدارک شما تناقض دیده می‌شود",
    AssessmentStatus.NOT_ASSESSABLE: "این ادعا با اطلاعات فعلی قابل ارزیابی نیست",
}

MODALITY_FA = {
    Modality.PLANNED: "در طرح درمان ثبت شده",
    Modality.RECOMMENDED: "پیشنهاد شده",
    Modality.REQUIRED: "لازم اعلام شده",
    Modality.QUOTED: "قیمت‌گذاری شده",
    Modality.MENTIONED: "اشاره شده",
    Modality.PERFORMED: "انجام شده",
}

GAP_FA = {
    "CLINICAL_EXAMINATION": "معاینه حضوری بالینی",
    "SYMPTOM_HISTORY": "شرح کامل علائم و سابقه",
    "PULP_TEST_RESULT": "تست حیات عصب دندان (پالپ)",
    "APPROPRIATE_RADIOGRAPH": "رادیوگرافی مناسب",
    "TREATMENT_PLAN_ENTRY": "ثبت رسمی طرح درمان",
}


def label_of(a: dict) -> str:
    """Treatment + modality label from a snapshot assessment entry (D-Q3)."""
    if a["claim_type"] == "TREATMENT_QUOTED":
        return "قیمت‌گذاری درمان"
    treatment = (a.get("claim_treatment") or "").replace("TREATMENT_", "")
    modality = MODALITY_FA.get(Modality(a["claim_modality"]), "") \
        if a.get("claim_modality") else ""
    tooth = f" دندان {a['subject'][6:]}" if a.get("subject", "").startswith("TOOTH_") else ""
    return f"{treatment}{tooth} ({modality})" if modality else f"{treatment}{tooth}"


def _scoped(db: Session, model, case: Case, derivation_run_id: int | None):
    return db.query(model).filter(
        model.case_id == case.id,
        model.derivation_run_id == derivation_run_id,
        model.derivation_status == DerivationStatus.ACTIVE).all()


def _collect_model_runs(db: Session, case: Case, derivation_run_id: int | None):
    """All ModelRuns reachable from this derivation's provenance chain (D4)."""
    claims = db.query(Claim).filter(
        Claim.case_id == case.id, Claim.derivation_run_id == derivation_run_id).all()
    findings = db.query(Finding).filter(
        Finding.case_id == case.id, Finding.derivation_run_id == derivation_run_id).all()
    prov_ids = [p for p in
                [c.provenance_id for c in claims] +
                [f.provenance_id for f in findings]
                if p]
    provs = db.query(ProvenanceRecord).filter(ProvenanceRecord.id.in_(prov_ids)).all() \
        if prov_ids else []
    model_run_ids = {p.model_run_id for p in provs if p.model_run_id}
    extractions = db.query(Extraction).filter(
        Extraction.derivation_run_id == derivation_run_id).all()
    model_run_ids |= {e.model_run_id for e in extractions if e.model_run_id}
    return db.query(ModelRun).filter(ModelRun.id.in_(list(model_run_ids))).all() \
        if model_run_ids else []


def _run_provenance_payload(db: Session, case: Case,
                            derivation_run_id: int | None) -> dict:
    """D4: stable references to everything that produced this derivation."""
    derivation = db.query(ProcessingRun).filter(
        ProcessingRun.id == derivation_run_id).one_or_none()
    stage_runs = (db.query(ProcessingRun)
                  .filter(ProcessingRun.derivation_run_id == derivation_run_id,
                          ProcessingRun.module != "pipeline")
                  .order_by(ProcessingRun.id).all())         if derivation_run_id else []
    stage_refs = [{"run_id": r.public_id, "module": r.module,
                   "status": r.status.value, "attempt": r.attempt}
                  for r in stage_runs]
    extractions = db.query(Extraction).filter(
        Extraction.derivation_run_id == derivation_run_id).all()
    fields = db.query(ExtractedField).filter(
        ExtractedField.extraction_id.in_([e.id for e in extractions])).all() \
        if extractions else []
    items = db.query(TreatmentItem).filter(
        TreatmentItem.derivation_run_id == derivation_run_id).all()
    claims = db.query(Claim).filter(
        Claim.derivation_run_id == derivation_run_id).all()
    prov_ids = sorted({
        p.id for p in db.query(ProvenanceRecord)
        .filter(ProvenanceRecord.id.in_(
            [i.provenance_id for i in items if i.provenance_id] +
            [c.provenance_id for c in claims if c.provenance_id])).all()
    }) if (items or claims) else []
    model_runs = _collect_model_runs(db, case, derivation_run_id)
    return {
        "derivation_run_id": derivation.public_id if derivation else None,
        "derivation_attempt": derivation.attempt if derivation else None,
        "stage_runs": stage_refs,
        "extractions": [{"extraction_id": e.public_id, "artifact_id": e.artifact_id,
                         "schema_version": e.schema_version,
                         "prompt_version": e.prompt_version} for e in extractions],
        "extracted_field_ids": [f.id for f in fields],
        "treatment_item_ids": [i.public_id for i in items],
        "provenance_ids": prov_ids,
        "model_runs": [{"model_run_id": m.id, "provider": m.provider, "model": m.model,
                        "prompt_id": m.prompt_id, "prompt_version": m.prompt_version,
                        "schema_version": m.schema_version, "input_hash": m.input_hash,
                        "status": m.status} for m in model_runs],
    }


def create_snapshot(db: Session, case: Case, safety: SafetyResult,
                    derivation_run_id: int | None) -> AssessmentSnapshot:
    """Freeze the authoritative derivation's assessments PLUS full run provenance
    (D4). Scoped to derivation_run_id — never 'all rows for the case' (B)."""
    from app.core.knowledge.pack import get_active_pack
    pack = get_active_pack(db)

    assessments = _scoped(db, Assessment, case, derivation_run_id)
    claims = _scoped(db, Claim, case, derivation_run_id)
    gaps = _scoped(db, EvidenceGap, case, derivation_run_id)
    findings = _scoped(db, Finding, case, derivation_run_id)
    links = db.query(EvidenceLink).join(Claim, EvidenceLink.claim_id == Claim.id).filter(
        Claim.case_id == case.id,
        EvidenceLink.derivation_run_id == derivation_run_id,
        EvidenceLink.derivation_status == DerivationStatus.ACTIVE).all()
    claim_by_id = {c.id: c for c in claims}

    payload = {
        "question": case.question_text,
        "dentist_recommendation": case.dentist_recommendation_text,
        "artifacts": [{"artifact_id": a.public_id, "sha256": a.sha256,
                       "category": a.category.value, "subtype": a.subtype.value}
                      for a in case.artifacts],
        "claims": [{"claim_id": c.public_id, "claim_type": c.claim_type.value,
                    "source_type": c.source_type.value, "subject": c.subject,
                    "treatment": c.treatment_id,
                    "modality": c.modality.value if c.modality else None,
                    "predicate": c.predicate} for c in claims],
        "findings": [{"finding_id": f.public_id, "type": f.finding_type,
                      "subject": f.normalized_subject, "object": f.normalized_object,
                      "predicate": f.predicate} for f in findings],
        "evidence_links": [{"link_id": l.public_id, "claim_id": l.claim_id,
                            "finding_id": l.finding_id,
                            "relationship": l.relationship_type.value}
                           for l in links],
        "assessments": [
            {
                "claim_id": a.claim_id,
                "claim_public_id": claim_by_id[a.claim_id].public_id,
                "claim_type": claim_by_id[a.claim_id].claim_type.value,
                "claim_source_type": claim_by_id[a.claim_id].source_type.value,
                "claim_treatment": claim_by_id[a.claim_id].treatment_id,
                "claim_modality": (claim_by_id[a.claim_id].modality.value
                                   if claim_by_id[a.claim_id].modality else None),
                "claim_predicate": claim_by_id[a.claim_id].predicate,
                "subject": claim_by_id[a.claim_id].subject,
                "status": a.status.value, "confidence": a.confidence.value,
                "supporting_evidence": a.supporting_evidence,
                "contradicting_evidence": a.contradicting_evidence,
                "missing_evidence": a.missing_evidence,
            } for a in assessments
        ],
        "gaps": [
            {"gap_type": g.gap_type, "importance": g.importance.value,
             "status": g.status.value, "claim_id": g.claim_id}
            for g in gaps
        ],
        "safety_state": safety.state.value,
        "safety_reasons": safety.reasons,
        # D4: frozen run provenance — reconstruction without rerunning AI
        "run_provenance": _run_provenance_payload(db, case, derivation_run_id),
    }

    derivation = db.query(ProcessingRun).filter(
        ProcessingRun.id == derivation_run_id).one_or_none()
    from app.core.cases.sample import execution_identity
    provider, model = execution_identity(case)
    versions = {
        "case_schema": "case-schema-v1",
        "ontology": ONTOLOGY_VERSION,
        "knowledge_pack_id": pack.knowledge_pack_id,
        "knowledge_pack": pack.version,
        "knowledge_pack_status": pack.status.value,
        "assessment_rules": "assessment-rules-v2",
        "report_schema": REPORT_SCHEMA_VERSION,
        "safety_rules": "safety-rules-v2",
        "quality_rules": "quality-rules-v2",
        "ai_provider": provider,
        "ai_model": model,
        "case_version": case.version,
        "derivation_run": derivation.public_id if derivation else None,
        "derivation_attempt": derivation.attempt if derivation else None,
    }
    from app.domain.models import ReviewRun
    from app.core.cases.dossier import fields
    review = db.query(ReviewRun).filter_by(case_id=case.id,
        derivation_run_id=derivation_run_id, status='SUCCEEDED').order_by(ReviewRun.id.desc()).first()
    if review:
        payload['review'] = {**review.output, 'source_index': review.source_index,
            'run': {'run_id': review.public_id, 'provider': review.provider,
                    'model': review.model, 'runtime_ms': review.runtime_ms,
                    'created_at': review.created_at.isoformat(),
                    'schema_version': review.schema_version, 'mode': 'MOCK' if review.provider == 'mock' else 'REAL'}}
        payload['dossier'] = fields(case)
        versions['review_schema'] = review.schema_version
    content_hash = snapshot_content_hash(payload, versions)
    snapshot = AssessmentSnapshot(
        public_id=public_id("SNP"), case_id=case.id, case_version=case.version,
        payload=payload, safety_state=safety.state, versions=versions,
        content_hash=content_hash, derivation_run_id=derivation_run_id,
    )
    db.add(snapshot)
    db.flush()
    audit(db, "snapshot_created", case_id=case.id, snapshot_public_id=snapshot.public_id,
          derivation_run_id=derivation_run_id,
          integrity=verify_snapshot_integrity(snapshot))
    return snapshot


def compose_report(db: Session, case: Case, snapshot: AssessmentSnapshot) -> Report:
    """Compose a report ONLY from an immutable, integrity-verified snapshot (INV-06)."""
    if snapshot.case_id != case.id:
        raise SafetyBlockedError("snapshot does not belong to this case")
    if not verify_snapshot_integrity(snapshot):
        raise SafetyBlockedError(
            "snapshot integrity check failed; refusing to compose report")
    if snapshot.safety_state == SafetyState.BLOCKED:
        raise SafetyBlockedError("safety gate blocked report generation")
    if snapshot.safety_state == SafetyState.MANUAL_REVIEW:
        # explicit review-pending report; NOT a completed evidence report
        content = {"safety_state": SafetyState.MANUAL_REVIEW.value,
                   "report_kind": "REVIEW_PENDING",
                   "sections": [{"section": "review_pending",
                                 "text": REVIEW_PENDING_NOTE_FA}]}
        report = Report(public_id=public_id("RPT"), case_id=case.id,
                        snapshot_id=snapshot.id,
                        derivation_run_id=snapshot.derivation_run_id,
                        schema_version=REPORT_SCHEMA_VERSION, content=content)
        db.add(report)
        db.flush()
        audit(db, "review_pending_report_created", case_id=case.id,
              report_public_id=report.public_id)
        return report

    if snapshot.safety_state == SafetyState.URGENT_EVALUATION:
        content = {"safety_state": snapshot.safety_state.value, "report_kind": "URGENT",
                   "sections": [
                       {"section": "safety_note",
                        "text": SAFETY_NOTE_FA[SafetyState.URGENT_EVALUATION]},
                   ]}
        report = Report(public_id=public_id("RPT"), case_id=case.id,
                        snapshot_id=snapshot.id,
                        derivation_run_id=snapshot.derivation_run_id,
                        schema_version=REPORT_SCHEMA_VERSION, content=content)
        db.add(report)
        db.flush()
        audit(db, "report_generated", case_id=case.id, report_public_id=report.public_id,
              urgent=True)
        return report

    p = snapshot.payload
    sections: list[dict[str, str]] = []

    sections.append({"section": "your_question",
                     "text": p.get("question") or "(ثبت نشده)"})
    sections.append({"section": "dentist_recommendation",
                     "text": p.get("dentist_recommendation") or "(ثبت نشده)"})

    found_lines = []
    for a in p["assessments"]:
        if a["claim_source_type"] == "CLINICIAN_REPORTED":
            found_lines.append(f"پیشنهاد دندان‌پزشک: {label_of(a)}.")
        elif a["claim_source_type"] == "DOCUMENT_EXTRACTED" and \
                a["status"] != "NOT_ASSESSABLE":
            found_lines.append(f"در مدارک، {label_of(a)} دیده شد.")
    sections.append({"section": "found_in_documents",
                     "text": "\n".join(found_lines) if found_lines else
                             "در مدارک بارگذاری‌شده مورد مستقیمی یافت نشد."})

    evidence_lines = []
    for a in p["assessments"]:
        if a["status"] == "NOT_ASSESSABLE":
            continue
        note = ""
        if a.get("claim_modality") in ("PLANNED", "RECOMMENDED") and \
                a["claim_type"] == "TREATMENT":
            note = " (این به معنی اثبات ضرورت پزشکی نیست)"
        evidence_lines.append(f"• {STATUS_FA[a['status']]} — {label_of(a)}{note}.")
    sections.append({"section": "evidence_status",
                     "text": "\n".join(evidence_lines) or
                             "ادعایی برای ارزیابی وجود ندارد."})

    uncertain = [a for a in p["assessments"] if a["status"] in
                 ("INSUFFICIENT_EVIDENCE", "PARTIALLY_SUPPORTED")]
    sections.append({"section": "still_unclear",
                     "text": "\n".join(f"• {label_of(a)}: {STATUS_FA[a['status']]}"
                                       for a in uncertain) or "موردی باقی نمانده است."})

    missing = sorted({GAP_FA.get(g["gap_type"], g["gap_type"])
                      for g in p["gaps"] if g["status"] == "MISSING"})
    sections.append({"section": "missing_evidence",
                     "text": "\n".join(f"• {m}" for m in missing) if missing else
                             "شواهد کاملی ثبت شده است."})

    sections.append({"section": "topics_to_discuss",
                     "text": "نتایج تست‌های لازم و دلیل بالینی پیشنهاد درمان"})
    sections.append({"section": "questions_to_ask",
                     "text": "\n".join([
                         "• چه یافته‌هایی در معاینه و رادیوگرافی باعث این پیشنهاد شده است؟",
                         "• آیا گزینه‌های درمانی جایگزینی وجود دارد؟",
                         "• اگر درمان انجام نشود چه اتفاقی ممکن است بیفتد؟",
                     ])})

    confs = {a["confidence"] for a in p["assessments"]} or {"INSUFFICIENT"}
    overall = "متوسط" if confs <= {"HIGH", "MEDIUM"} else "نامشخص (شواهد ناکافی)"
    sections.append({"section": "confidence", "text": f"سطح اطمینان کلی: {overall}"})
    sections.append({"section": "safety_note",
                     "text": SAFETY_NOTE_FA.get(snapshot.safety_state,
                                                SAFETY_NOTE_FA[SafetyState.NORMAL])})

    # Schema firewall for composed sections
    validated = ReportOutput.model_validate({"sections": sections})
    _forbidden_check(validated)

    content = {"safety_state": snapshot.safety_state.value, "report_kind": "STANDARD",
               "sections": [s.model_dump() for s in validated.sections]}
    report = Report(public_id=public_id("RPT"), case_id=case.id, snapshot_id=snapshot.id,
                    derivation_run_id=snapshot.derivation_run_id,
                    schema_version=REPORT_SCHEMA_VERSION, content=content)
    db.add(report)
    db.flush()
    audit(db, "report_generated", case_id=case.id, report_public_id=report.public_id)
    return report


def _forbidden_check(report: ReportOutput) -> None:
    joined = " ".join(s.text for s in report.sections).lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in joined:
            raise SafetyBlockedError(f"report contains forbidden claim: {phrase}")
