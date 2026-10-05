"""Claim engine, evidence graph construction, gap engine (D-Q1/D-Q2/D-Q3).

Semantics rules (binding, docs/P0_1_DECISIONS_LOCK.md):
- Claims are compositional: (claim_type=TREATMENT, treatment_id, modality).
  Recommendation is NOT necessity (C): a plan listing RCT yields PLANNED/RECOMMENDED;
  REQUIRED requires explicit necessity language from the source.
- Claims/findings come ONLY from atomic TreatmentItems — no cartesian reconstruction.
- Truth types never merged; MODEL_INFERRED duplicates of existing claims are skipped.
- Evidence links require treatment AND subject compatibility; a mention of a
  treatment can never prove necessity (§15): mention-links are RELEVANT_TO only.
- All canonical values pass semantic validation before persistence (P0-03).
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.ai.gateway import ModelGateway
from app.ai.schemas import ClaimsOutput
from app.core.knowledge.pack import get_active_pack
from app.core.ontology import ontology as ont
from app.domain.enums import (ArtifactCategory, ClaimType, DerivationStatus, Modality,
                              EvidenceRelationship, GapImportance, GapStatus, TruthType)
from app.domain.models import (Case, Claim, EvidenceGap, EvidenceLink, Finding,
                               TreatmentItem, public_id)
from app.errors import ExtractionValidationError, OntologyValidationError
from app.governance.record import audit, create_provenance

# Patient-relayed dentist statements: map treatment synonyms + necessity language
# to (treatment, modality). Recommendation is NOT necessity (D-Q3).
_NECESITY_MARKERS = ["لازم است", "لازمه", "باید", "نیاز", "required", "necessary",
                     "needs", "must be", "must"]
_TREATMENT_SYNONYM_ORDER = [
    "TREATMENT_ROOT_CANAL", "TREATMENT_EXTRACTION", "TREATMENT_CROWN",
    "TREATMENT_FILLING", "TREATMENT_SCALING", "TREATMENT_IMPLANT",
    "TREATMENT_BRIDGE", "TREATMENT_ORTHODONTICS",
]


def validate_claim_semantics(claim_type: ClaimType, subject: str,
                             treatment_id: str | None, modality: Modality | None) -> None:
    """Ontology + semantic validation before persistence (P0-03)."""
    ont.validate_claim_type(claim_type.value)
    if subject:
        if not subject.startswith("TOOTH_"):
            raise OntologyValidationError(f"claim subject must be a TOOTH_ id, got {subject!r}")
        ont.validate_tooth(subject)
    if claim_type == ClaimType.TREATMENT:
        if not treatment_id:
            raise OntologyValidationError("TREATMENT claim requires a treatment id")
        ont.validate_treatment(treatment_id)
        if modality is None:
            raise OntologyValidationError("TREATMENT claim requires a modality")
    if treatment_id and not treatment_id.startswith("TREATMENT_"):
        raise OntologyValidationError(f"invalid treatment identifier: {treatment_id!r}")


def _parse_recommendation(text: str) -> list[tuple[str, Modality]]:
    """Extract (treatment, modality) pairs from free text. Necessity language in the
    same sentence upgrades modality to REQUIRED; otherwise RECOMMENDED."""
    low = text.lower()
    required = any(m in low for m in _NECESITY_MARKERS)
    pairs: list[tuple[str, Modality]] = []
    for treatment_id in _TREATMENT_SYNONYM_ORDER:
        for synonym in ont._TREATMENT_SYNONYMS.get(treatment_id, []):
            if synonym in low:
                pairs.append((treatment_id,
                              Modality.REQUIRED if required else Modality.RECOMMENDED))
                break
    return pairs


def build_case_claims(db: Session, gw: ModelGateway, case: Case,
                      derivation_run_id: int | None = None) -> list[Claim]:
    claims: list[Claim] = []

    def add_claim(claim_type: ClaimType, subject: str, predicate: str, value: str,
                  source_type: TruthType, source_ref: str, confidence: float = 1.0,
                  treatment_id: str | None = None,
                  modality: Modality | None = None) -> Claim:
        validate_claim_semantics(claim_type, subject, treatment_id, modality)
        # Preserve independent sources for equivalent propositions. Model-generated
        # restatements still defer to existing claims (P0-01-B).
        for existing in claims:
            if (existing.claim_type == claim_type and existing.subject == subject
                    and existing.treatment_id == treatment_id
                    and existing.modality == modality
                    and (source_type == TruthType.MODEL_INFERRED
                         or (existing.source_type == source_type
                             and existing.source_reference == source_ref[:1000]))):
                return existing
        prov = create_provenance(db, truth_type=source_type, confidence=confidence,
                                 description=source_ref[:500])
        claim = Claim(
            public_id=public_id("CLM"), case_id=case.id, claim_type=claim_type,
            subject=subject, predicate=predicate, object_value=value,
            treatment_id=treatment_id, modality=modality,
            source_type=source_type, source_reference=source_ref[:1000],
            confidence=confidence, provenance_id=prov.id,
            derivation_run_id=derivation_run_id,
            derivation_status=DerivationStatus.ACTIVE,
        )
        db.add(claim)
        claims.append(claim)
        return claim

    # 1. Patient question (PATIENT_REPORTED) — captured, not clinically assessable
    if case.question_text.strip():
        add_claim(ClaimType.OTHER, "", "ASKS", case.question_text,
                  TruthType.PATIENT_REPORTED, "patient question")

    # 2. Dentist recommendation as relayed by patient (CLINICIAN_REPORTED).
    #    Modality: REQUIRED only with explicit necessity language (D-Q3).
    rec_text = case.dentist_recommendation_text.strip()
    if rec_text:
        tooth = ont.normalize_tooth(rec_text) or ont.normalize_tooth(case.question_text)
        for treatment_id, modality in _parse_recommendation(rec_text):
            add_claim(ClaimType.TREATMENT, tooth or "", "RECOMMENDS", rec_text,
                      TruthType.CLINICIAN_REPORTED,
                      "dentist recommendation as reported by patient",
                      confidence=1.0, treatment_id=treatment_id, modality=modality)

    # 3. Document-derived claims: one per atomic TreatmentItem finding (D-Q2).
    item_findings = db.query(Finding).filter(
        Finding.case_id == case.id,
        Finding.finding_type == "TREATMENT_ITEM",
        Finding.derivation_run_id == derivation_run_id).all()
    for finding in item_findings:
        artifact = finding.artifact
        modality = Modality(finding.predicate)
        source_ref = (f"treatment item in {artifact.public_id}"
                      if artifact else "document")
        add_claim(ClaimType.TREATMENT, finding.normalized_subject or "",
                  "PROPOSES", source_ref,
                  TruthType.DOCUMENT_EXTRACTED, source_ref,
                  confidence=finding.confidence,
                  treatment_id=finding.normalized_object, modality=modality)

    # 3.5 Quoted-price claim from financial findings
    price_findings = db.query(Finding).filter(
        Finding.case_id == case.id,
        Finding.finding_type == "TREATMENT_QUOTED",
        Finding.derivation_run_id == derivation_run_id).all()
    for pf in price_findings:
        add_claim(ClaimType.TREATMENT_QUOTED, pf.normalized_subject or "", "QUOTED_PRICE",
                  pf.statement, TruthType.DOCUMENT_EXTRACTED,
                  f"financial document {pf.artifact.public_id if pf.artifact else '?'}",
                  confidence=pf.confidence)

    # 4. AI claim candidates (MODEL_INFERRED) from atomic TreatmentItem facts,
    #    through the gateway schema firewall + semantic validation + dedupe
    #    (P0-01-B/P0-03). One candidate per item — NO cartesian reconstruction.
    items = db.query(TreatmentItem).filter(
        TreatmentItem.derivation_run_id == derivation_run_id).all() \
        if derivation_run_id else []
    price_facts = [{"subject": pf.normalized_subject or "",
                    "object_value": pf.statement, "confidence": pf.confidence}
                   for pf in price_findings]
    facts = {"treatment_items": [
        {"tooth": it.tooth_id, "treatment": it.treatment_id,
         "predicate": it.predicate.value, "confidence": it.confidence}
        for it in items],
        "price_facts": price_facts}
    if facts["treatment_items"] or facts["price_facts"]:
        out, run = gw.run("claim_builder", ClaimsOutput, json.dumps(facts))
        from app.ai.grounding import validate_claim_sources
        validate_claim_sources(out, facts)
        for c in out.claims:
            try:
                ct = ClaimType(c.claim_type)
                modality = Modality(c.modality) if c.modality else None
            except ValueError as exc:
                raise ExtractionValidationError(
                    f"claim candidate not in ontology: {c.claim_type}/{c.modality}") from exc
            try:
                add_claim(ct, c.subject, c.predicate or "PROPOSES", c.object_value,
                          TruthType.MODEL_INFERRED, f"claim_builder@{run.prompt_version}",
                          c.confidence, treatment_id=c.treatment, modality=modality)
            except OntologyValidationError as exc:
                # invalid candidate never persists; controlled stage failure
                raise ExtractionValidationError(f"claim candidate rejected: {exc}") from exc

    db.flush()
    audit(db, "claims_built", case_id=case.id, claim_count=len(claims))
    return claims


def build_evidence_graph(db: Session, case: Case, claims: list[Claim],
                         derivation_run_id: int | None = None) -> list[EvidenceLink]:
    """Subject-safe linking (D-Q2 Step 3): a finding links to a claim only when the
    treatment matches AND the subject is compatible (equal, or one side unknown).
    MENTIONED/PLANNED findings are RELEVANT_TO, never SUPPORTS (§15)."""
    findings = db.query(Finding).filter(
        Finding.case_id == case.id,
        Finding.derivation_run_id == derivation_run_id).all()
    links: list[EvidenceLink] = []

    def subject_compatible(claim_subject: str, finding_subject: str | None) -> bool:
        if not claim_subject:
            return True
        if not finding_subject:
            return True
        return claim_subject == finding_subject

    for claim in claims:
        if claim.claim_type == ClaimType.OTHER:
            continue
        for finding in findings:
            if finding.finding_type == "TREATMENT_ITEM":
                # Treatment must match AND subject must be compatible.
                if finding.normalized_object != claim.treatment_id:
                    continue
                if not subject_compatible(claim.subject, finding.normalized_subject):
                    continue
                # Recommendation-existence evidence only: the document that
                # proposes a treatment never proves its necessity (§15).
                rel = EvidenceRelationship.RELEVANT_TO
                strength = 0.5
            elif finding.finding_type == "TOOTH_REFERENCE" and \
                    claim.subject and \
                    finding.normalized_subject == claim.subject:
                rel = EvidenceRelationship.RELEVANT_TO
                strength = 0.4
            elif finding.finding_type == "TREATMENT_QUOTED" and \
                    claim.claim_type == ClaimType.TREATMENT_QUOTED and \
                    subject_compatible(claim.subject, finding.normalized_subject):
                rel = EvidenceRelationship.SUPPORTS
                strength = 0.8
            else:
                continue
            links.append(EvidenceLink(
                public_id=public_id("LNK"), claim_id=claim.id, finding_id=finding.id,
                evidence_reference=f"finding:{finding.public_id}",
                relationship_type=rel,
                strength=strength, source_type=finding.truth_type,
                confidence=finding.confidence, provenance_id=finding.provenance_id,
                derivation_run_id=derivation_run_id,
                derivation_status=DerivationStatus.ACTIVE,
            ))
    db.add_all(links)
    db.flush()
    audit(db, "evidence_graph_built", case_id=case.id, link_count=len(links))
    return links


def run_gap_engine(db: Session, case: Case, claims: list[Claim],
                   derivation_run_id: int | None = None) -> list[EvidenceGap]:
    """Requirements come ONLY from the active Knowledge Pack (INV-05), keyed by
    treatment|modality (D-Q3). Nothing is invented for unknown propositions."""
    pack = get_active_pack(db)
    gaps: list[EvidenceGap] = []
    findings = db.query(Finding).filter(
        Finding.case_id == case.id,
        Finding.derivation_run_id == derivation_run_id).all()
    has_radiograph = any(f.artifact and f.artifact.category == ArtifactCategory.RADIOGRAPH
                         for f in findings)
    has_clinical_exam = False  # V0: not derivable from documents; conservative

    for claim in claims:
        if claim.claim_type == ClaimType.OTHER:
            continue
        if claim.claim_type == ClaimType.TREATMENT_QUOTED:
            continue  # price claims have no clinical evidence requirements
        spec = None
        from app.core.knowledge.pack import requirements_for
        spec = requirements_for(pack, claim.treatment_id,
                                claim.modality.value if claim.modality else None)
        if spec is None:
            continue  # pack has no requirement for this proposition; invent nothing
        for req in spec.get("required_evidence", []):
            gap_type = req["gap_type"]
            importance = GapImportance(req["importance"])
            satisfied = {
                "APPROPRIATE_RADIOGRAPH": has_radiograph,
                "CLINICAL_EXAMINATION": has_clinical_exam,
            }.get(gap_type, False)
            gaps.append(EvidenceGap(
                public_id=public_id("GAP"), case_id=case.id, claim_id=claim.id,
                gap_type=gap_type, importance=importance,
                status=GapStatus.RESOLVED if satisfied else GapStatus.MISSING,
                reason="" if satisfied else f"required by knowledge pack {pack.version}",
                knowledge_pack_version=pack.version,
                derivation_run_id=derivation_run_id,
                derivation_status=DerivationStatus.ACTIVE,
            ))
    db.add_all(gaps)
    db.flush()
    audit(db, "gap_analysis_completed", case_id=case.id, gap_count=len(gaps))
    return gaps
