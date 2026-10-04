"""Read-only Persian presentation of an already-authoritative report snapshot.

No assessment, source deduplication, policy change, or stored report rewrite.
Evidence relationships come from the frozen snapshot, never guessed from text.
"""
from sqlalchemy.orm import Session

from app.domain.models import Artifact, AssessmentSnapshot, Finding, Report
from app.errors import SafetyBlockedError
from app.governance.immutability import verify_snapshot_integrity
from app.pipeline.reporting import GAP_FA, STATUS_FA, label_of

TREATMENTS_FA = {
    "ROOT_CANAL": "عصب‌کشی", "EXTRACTION": "کشیدن دندان", "CROWN": "روکش",
    "FILLING": "ترمیم", "SCALING": "جرم‌گیری", "IMPLANT": "ایمپلنت",
    "BRIDGE": "بریج", "DENTURE": "دندان مصنوعی", "ORTHODONTICS": "ارتودنسی",
    "UNKNOWN": "درمان نامشخص",
}
SOURCES_FA = {
    "CLINICIAN_REPORTED": "گفتهٔ دندان‌پزشک به روایت شما",
    "DOCUMENT_EXTRACTED": "استخراج‌شده از سند",
    "MODEL_INFERRED": "برداشت مدل؛ نیازمند تأیید",
    "PATIENT_REPORTED": "گفتهٔ شما",
}
RELATIONSHIPS_FA = {
    "SUPPORTS": "پشتیبان ادعا در محدودهٔ سند",
    "PARTIALLY_SUPPORTS": "پشتیبان بخشی از ادعا",
    "CONTRADICTS": "در تعارض با ادعا",
    "RELEVANT_TO": "مرتبط با ادعا؛ اثبات ضرورت درمان نیست",
    "REQUIRES": "شاهد مورد نیاز", "MISSING": "شاهد موجود نیست",
}


def report_presentation(db: Session, report: Report, snapshot: AssessmentSnapshot) -> dict:
    if not verify_snapshot_integrity(snapshot):
        raise SafetyBlockedError("snapshot integrity check failed")
    # Never add routine evidence/decision content to restricted safety reports.
    if report.content.get("report_kind") != "STANDARD":
        return {}
    payload = snapshot.payload
    artifact_ids = [a["artifact_id"] for a in payload.get("artifacts", [])]
    artifacts = db.query(Artifact).filter(
        Artifact.case_id == snapshot.case_id, Artifact.public_id.in_(artifact_ids)).all()
    by_public_id = {a.public_id: a for a in artifacts}
    ordered_ids = []
    for source in (payload.get('review') or {}).get('source_index', []):
        identifier = source.get('artifact_id')
        if identifier is None:
            continue
        if identifier not in by_public_id:
            raise SafetyBlockedError('unresolvable frozen review source')
        if identifier not in ordered_ids:
            ordered_ids.append(identifier)
    for identifier in artifact_ids:
        if identifier not in by_public_id:
            raise SafetyBlockedError('unresolvable frozen artifact')
        if identifier not in ordered_ids:
            ordered_ids.append(identifier)
    artifacts = [by_public_id[identifier] for identifier in ordered_ids]
    by_id = {a.id: a for a in artifacts}
    finding_ids = [f["finding_id"] for f in payload.get("findings", [])]
    findings = db.query(Finding).filter(
        Finding.case_id == snapshot.case_id,
        Finding.derivation_run_id == snapshot.derivation_run_id,
        Finding.public_id.in_(finding_ids)).all()
    by_finding = {f.id: f for f in findings}
    claims = []
    for assessment in payload.get("assessments", []):
        label = label_of(assessment)
        for key, value in TREATMENTS_FA.items():
            label = label.replace(key, value)
        evidence = []
        for link in payload.get("evidence_links", []):
            if link["claim_id"] != assessment["claim_id"]:
                continue
            finding = by_finding.get(link["finding_id"])
            artifact = by_id.get(finding.artifact_id) if finding else None
            if artifact is not None:
                evidence.append({"filename": artifact.original_filename,
                    "relationship": RELATIONSHIPS_FA.get(link["relationship"], "رابطهٔ قابل ارزیابی نیست")})
        claims.append({
            "label": label,
            "source": SOURCES_FA.get(assessment["claim_source_type"], "منبع نیازمند بررسی"),
            "status": STATUS_FA.get(assessment["status"], "قابل ارزیابی نیست"),
            "evidence": evidence,
            "missing": [GAP_FA.get(g, "شاهد تکمیلی نیازمند بررسی")
                        for g in assessment.get("missing_evidence", [])],
        })
    return {"materials": [{"filename": a.original_filename,
                            "image_analysis_disabled": a.detected_mime_type.startswith("image/")}
                           for a in artifacts], "claims": claims}
