"""Assessment Engine (deterministic policy) + Safety Gate (fail closed, P0-06).

Assessment policy: contradiction wins; then missing Knowledge-Pack requirements
(importance >= MEDIUM) force INSUFFICIENT_EVIDENCE; SUPPORTS links can support;
RELEVANT_TO links never confirm. A mention of a treatment can never become proof
of necessity (§15).

Safety report policy (P0-06):
  NORMAL            -> normal report allowed
  CAUTION           -> report allowed with constrained safety language
  URGENT_EVALUATION -> only urgent-safe content
  MANUAL_REVIEW     -> normal report BLOCKED; explicit review-pending report only
  BLOCKED           -> no report
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.knowledge.pack import get_active_pack, requirements_for
from app.domain.enums import (AssessmentStatus, ClaimType, ConfidenceLevel, DerivationStatus,
                              EvidenceRelationship, GapImportance, GapStatus, Modality,
                              SafetyState, TruthType)
from app.domain.models import (Assessment, Case, Claim, EvidenceGap, EvidenceLink, SafetyResult,
                               public_id)
from app.governance.record import audit

ASSESSMENT_RULES_VERSION = "assessment-rules-v2"
SAFETY_RULES_VERSION = "safety-rules-v2"

LOW_CONFIDENCE_THRESHOLD = 0.5

URGENT_PATTERNS = [
    "خونریزی شدید", "خونریزی بند نیامدن", "severe bleeding",
    "تورم صورت", "تورم شدید", "swelling of face", "facial swelling",
    "مشکل تنفس", "نفس کشیدن", "بلع", "breathing", "swallowing difficulty",
    "ضربه شدید", "شکستگی فک", "trauma", "jaw fracture",
    "درد شدید و رو به افزایش", "worsening rapidly", "تب بالا", "high fever",
]
CAUTION_PATTERNS = ["درد", "تورم", "تب", "pain", "swelling", "fever"]
# Requests the system must refuse outright (unsafe medication/self-treatment advice)
BLOCKED_PATTERNS = ["چه دارویی بخرم", "بدون نسخه", "دوز دارو بگو", "prescribe me",
                    "what drug should i take"]

# Forbidden report claims (overclaim protection)
FORBIDDEN_PHRASES = [
    "قطعاً نیاز دارید", "حتماً باید", "قطعاً لازم است", "you definitely need",
    "you definitely don't need", "دندانپزشک شما اشتباه", "your dentist is wrong",
    "your dentist is correct", "این دارو را مصرف", "این دارو را قطع",
]


def run_assessment_engine(db: Session, case: Case,
                          derivation_run_id: int | None = None) -> list[Assessment]:
    pack = get_active_pack(db)
    claims = db.query(Claim).filter(Claim.case_id == case.id,
                                    Claim.claim_type != ClaimType.OTHER,
                                    Claim.derivation_run_id == derivation_run_id).all()
    gaps = db.query(EvidenceGap).filter(EvidenceGap.case_id == case.id,
                                        EvidenceGap.derivation_run_id == derivation_run_id).all()
    assessments = []
    for claim in claims:
        links = db.query(EvidenceLink).filter(EvidenceLink.claim_id == claim.id).all()
        supporting = [l for l in links
                      if l.relationship_type == EvidenceRelationship.SUPPORTS]
        partial = [l for l in links
                   if l.relationship_type == EvidenceRelationship.PARTIALLY_SUPPORTS]
        contradicting = [l for l in links
                         if l.relationship_type == EvidenceRelationship.CONTRADICTS]
        claim_gaps = [g for g in gaps if g.claim_id == claim.id]
        missing = [g for g in claim_gaps if g.status == GapStatus.MISSING]
        blocking_missing = [g for g in missing
                            if g.importance in (GapImportance.MEDIUM, GapImportance.HIGH,
                                                GapImportance.CRITICAL)]

        if contradicting:
            status = AssessmentStatus.CONTRADICTED
        elif blocking_missing:
            # Knowledge-Pack requirements unmet -> never assert clinical support
            status = AssessmentStatus.INSUFFICIENT_EVIDENCE
        elif supporting or partial:
            status = AssessmentStatus.PARTIALLY_SUPPORTED
        else:
            status = AssessmentStatus.INSUFFICIENT_EVIDENCE

        if status in (AssessmentStatus.PARTIALLY_SUPPORTED, AssessmentStatus.SUPPORTED):
            confidence = ConfidenceLevel.MEDIUM  # HIGH reserved for reviewed packs
        elif status == AssessmentStatus.CONTRADICTED:
            confidence = ConfidenceLevel.LOW
        else:
            confidence = ConfidenceLevel.INSUFFICIENT

        a = Assessment(
            public_id=public_id("ASM"), case_id=case.id, claim_id=claim.id, status=status,
            supporting_evidence=[l.evidence_reference for l in supporting + partial],
            contradicting_evidence=[l.evidence_reference for l in contradicting],
            missing_evidence=[g.gap_type for g in missing],
            confidence=confidence, knowledge_pack_version=pack.version,
            assessment_rules_version=ASSESSMENT_RULES_VERSION,
            derivation_run_id=derivation_run_id,
            derivation_status=DerivationStatus.ACTIVE,
        )
        db.add(a)
        assessments.append(a)
    db.flush()
    audit(db, "assessment_generated", case_id=case.id, assessment_count=len(assessments))
    return assessments


def screen_case_text(case: Case) -> tuple[SafetyState, list[str]]:
    """Intake safety screening (D3): text-only, artifact-independent. Runs BEFORE
    any document-dependent early exit so safety and evidence sufficiency stay
    orthogonal."""
    joined = " ".join(filter(None, [case.question_text or "", case.context_text or "",
                                    case.dentist_recommendation_text or ""])).lower()
    if any(p in joined for p in BLOCKED_PATTERNS):
        return SafetyState.BLOCKED, ["unsafe request pattern"]
    if any(p in joined for p in URGENT_PATTERNS):
        return SafetyState.URGENT_EVALUATION, ["urgent symptom pattern"]
    if any(p in joined for p in CAUTION_PATTERNS):
        return SafetyState.CAUTION, ["caution symptom pattern"]
    return SafetyState.NORMAL, []


def run_safety_gate(db: Session, case: Case,
                    derivation_run_id: int | None = None) -> SafetyResult:
    """Separate engine; the composer may never downgrade its state (P0-06-D)."""
    state, reasons = screen_case_text(case)

    # Fail closed: critical missing evidence
    critical_missing = (db.query(EvidenceGap)
                        .filter(EvidenceGap.case_id == case.id,
                                EvidenceGap.derivation_run_id == derivation_run_id,
                                EvidenceGap.derivation_status == DerivationStatus.ACTIVE,
                                EvidenceGap.status == GapStatus.MISSING,
                                EvidenceGap.importance == GapImportance.CRITICAL)
                        .count())
    if critical_missing and state in (SafetyState.NORMAL, SafetyState.CAUTION):
        state = SafetyState.MANUAL_REVIEW
        reasons.append("critical evidence gap unresolved")

    # Fail closed: low-confidence extraction feeding material claims
    low_conf = (db.query(Claim)
                .filter(Claim.case_id == case.id,
                        Claim.derivation_run_id == derivation_run_id,
                        Claim.derivation_status == DerivationStatus.ACTIVE,
                        Claim.claim_type != ClaimType.OTHER,
                        Claim.source_type.in_([TruthType.MODEL_INFERRED,
                                               TruthType.DOCUMENT_EXTRACTED]),
                        Claim.confidence < LOW_CONFIDENCE_THRESHOLD)
                .count())
    if low_conf and state == SafetyState.NORMAL:
        state = SafetyState.MANUAL_REVIEW
        reasons.append("low-confidence extraction on material claim")

    result = SafetyResult(case_id=case.id, state=state, reasons=reasons,
                          rules_version=SAFETY_RULES_VERSION,
                          derivation_run_id=derivation_run_id,
                          derivation_status=DerivationStatus.ACTIVE)
    db.add(result)
    db.flush()
    audit(db, "safety_gate_executed", case_id=case.id, state=state.value,
          reasons=reasons)
    return result
