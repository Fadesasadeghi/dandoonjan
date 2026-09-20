"""Pipeline stages: classification, quality gate, structured extraction, findings.

Canonical flow (P0-02 + D-Q2): Artifact -> Extraction -> ExtractedField /
TreatmentItem -> Normalization -> Finding. Findings are built only from validated
extraction outputs; raw artifact text is never re-read downstream. Tooth-treatment
relationships come exclusively from atomic TreatmentItems.

All derived rows are stamped with derivation_run_id (D-Q1). Quality Gate (P0-07)
produces explicit decisions that drive workflow.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.gateway import ModelGateway
from app.ai.schemas import ClassificationOutput, ExtractionOutput
from app.core.artifacts.ingestion import describe_for_ai
from app.core.ontology import ontology as ont
from app.domain.enums import (ArtifactCategory, ArtifactSubtype, DerivationStatus,
                              Modality, TruthType, UsabilityState)
from app.domain.models import (Artifact, ArtifactClassification, ArtifactQualityAssessment,
                               Extraction, ExtractedField, Finding, ProvenanceRecord,
                               TreatmentItem, public_id)
from app.errors import ExtractionValidationError
from app.governance.record import audit, create_provenance

ONTOLOGY_VERSION = ont.ONTOLOGY_VERSION
QUALITY_RULES_VERSION = "quality-rules-v2"
EXTRACTION_SCHEMA_VERSION = "ext-schema-v2"

TECHNICAL_DIM = "TECHNICAL_USABILITY"
SEMANTIC_DIM = "SEMANTIC_RELEVANCE"
EVIDENTIARY_DIM = "EVIDENTIARY_USABILITY"


class QualityDecision:
    CONTINUE = "CONTINUE"
    CONTINUE_WITH_LIMITATIONS = "CONTINUE_WITH_LIMITATIONS"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    REJECT_ARTIFACT = "REJECT_ARTIFACT"


@dataclass
class QualityOutcome:
    artifact_public_id: str
    decision: str
    details: dict


def classify_artifact(db: Session, gw: ModelGateway, artifact: Artifact,
                      derivation_run_id: int | None = None) -> ArtifactClassification:
    content = describe_for_ai(artifact)
    out, run = gw.run("artifact_classifier", ClassificationOutput, content)

    # ontology firewall: category/subtype must be known enum members (P0-03)
    try:
        category = ArtifactCategory(out.category)
        subtype = ArtifactSubtype(out.subtype)
    except ValueError as exc:
        raise ExtractionValidationError(f"classification not in ontology: {exc}") from exc

    cls = ArtifactClassification(
        artifact_id=artifact.id, category=category, subtype=subtype,
        confidence=out.confidence, truth_type=TruthType.MODEL_INFERRED,
        model_run_id=run.id, prompt_version=run.prompt_version,
        schema_version=run.schema_version,
        derivation_run_id=derivation_run_id,
        derivation_status=DerivationStatus.ACTIVE,
    )
    db.add(cls)
    artifact.category = category
    artifact.subtype = subtype
    db.flush()
    audit(db, "classification_completed", case_id=artifact.case_id,
          artifact_public_id=artifact.public_id, category=category.value)
    return cls


def run_quality_gate(db: Session, artifact: Artifact,
                     derivation_run_id: int | None = None) -> QualityOutcome:
    """Deterministic, multidimensional; dimensions stay separate. Never fabricates."""
    rows: list[tuple[str, UsabilityState, str]] = []
    if artifact.category == ArtifactCategory.UNKNOWN:
        rows.append((TECHNICAL_DIM, UsabilityState.INSUFFICIENT, "category unknown"))
    elif artifact.detected_mime_type == "application/octet-stream":
        rows.append((TECHNICAL_DIM, UsabilityState.INVALID, "unreadable content"))
    else:
        rows.append((TECHNICAL_DIM, UsabilityState.USABLE, ""))

    text = (artifact.text_content or "").strip()
    if artifact.category in (ArtifactCategory.CLINICAL_DOCUMENT,
                             ArtifactCategory.FINANCIAL_DOCUMENT):
        rows.append((SEMANTIC_DIM,
                     UsabilityState.USABLE if text else UsabilityState.INSUFFICIENT,
                     "" if text else "no extractable text"))
        # evidentiary usability stays a separate dimension (financial docs alone
        # cannot support clinical claims) — it informs gaps, not gate decisions
        if artifact.category == ArtifactCategory.FINANCIAL_DOCUMENT:
            rows.append((EVIDENTIARY_DIM, UsabilityState.INSUFFICIENT,
                         "financial document alone cannot support clinical claims"))
        elif artifact.subtype == ArtifactSubtype.TREATMENT_PLAN:
            rows.append((EVIDENTIARY_DIM, UsabilityState.USABLE, ""))
        else:
            rows.append((EVIDENTIARY_DIM, UsabilityState.PARTIALLY_USABLE, ""))
    else:
        rows.append((SEMANTIC_DIM, UsabilityState.PARTIALLY_USABLE,
                     "image stored; not diagnostically interpreted (V0 policy)"))
        rows.append((EVIDENTIARY_DIM, UsabilityState.PARTIALLY_USABLE, ""))

    for dim, state, reason in rows:
        db.add(ArtifactQualityAssessment(artifact_id=artifact.id, dimension=dim,
                                         state=state, reason=reason,
                                         rules_version=QUALITY_RULES_VERSION,
                                         derivation_run_id=derivation_run_id,
                                         derivation_status=DerivationStatus.ACTIVE))
    db.flush()

    by_dim = {dim: state for dim, state, _ in rows}
    technical = by_dim.get(TECHNICAL_DIM)
    semantic = by_dim.get(SEMANTIC_DIM)

    if technical in (UsabilityState.INVALID, UsabilityState.UNSUPPORTED):
        decision = QualityDecision.REJECT_ARTIFACT
    elif technical == UsabilityState.INSUFFICIENT or semantic == UsabilityState.INSUFFICIENT:
        decision = QualityDecision.NEEDS_MORE_EVIDENCE
    elif UsabilityState.PARTIALLY_USABLE in by_dim.values():
        decision = QualityDecision.CONTINUE_WITH_LIMITATIONS
    else:
        decision = QualityDecision.CONTINUE

    audit(db, "quality_gate_decided", case_id=artifact.case_id,
          artifact_public_id=artifact.public_id, decision=decision)
    return QualityOutcome(artifact.public_id, decision,
                          {dim: state.value for dim, state, _ in rows})


def extract_structured(db: Session, gw: ModelGateway, artifact: Artifact,
                       derivation_run_id: int | None = None) -> Extraction | None:
    """Dedicated extraction schema per supported artifact type (v2: TreatmentItems).
    Returns None when the artifact type/text is not extractable."""
    if artifact.category not in (ArtifactCategory.CLINICAL_DOCUMENT,
                                 ArtifactCategory.FINANCIAL_DOCUMENT) or \
            not (artifact.text_content or "").strip():
        return None
    prompt_id = ("invoice_extractor" if artifact.category == ArtifactCategory.FINANCIAL_DOCUMENT
                 else "treatment_plan_extractor")
    out, run = gw.run(prompt_id, ExtractionOutput, describe_for_ai(artifact))
    extraction = Extraction(
        public_id=public_id("EXT"), artifact_id=artifact.id,
        schema_name=prompt_id, schema_version=run.schema_version,
        prompt_version=run.prompt_version, model_run_id=run.id,
        derivation_run_id=derivation_run_id,
        derivation_status=DerivationStatus.ACTIVE,
    )
    db.add(extraction)
    db.flush()

    for f in out.fields:
        normalized = None
        if f.field_name == "tooth_reference":
            normalized = f.normalized_value or ont.normalize_tooth(f.raw_value)
            if normalized:
                ont.validate_tooth(normalized)
        elif f.field_name in ("price", "total_price"):
            normalized = f.normalized_value
        prov = create_provenance(
            db, truth_type=TruthType.DOCUMENT_EXTRACTED, artifact_id=artifact.id,
            page=f.page, source_span=f.source_span, model_run_id=run.id,
            confidence=f.confidence,
            description=f"extracted {f.field_name} from {artifact.public_id}")
        db.add(ExtractedField(
            extraction_id=extraction.id, field_name=f.field_name, raw_value=f.raw_value,
            normalized_value=normalized, confidence=f.confidence, provenance_id=prov.id,
        ))

    # Atomic tooth-treatment relationships (D-Q2): persisted explicitly.
    for item in out.treatment_items:
        loc = item.source_locator
        prov = create_provenance(
            db, truth_type=TruthType.DOCUMENT_EXTRACTED, artifact_id=artifact.id,
            page=loc.page if loc else None,
            source_span=loc.span if loc else None,
            bounding_box=loc.bounding_box if loc else None,
            model_run_id=run.id, confidence=item.confidence,
            description=f"treatment item {item.treatment}"
                        f"{'/' + item.tooth if item.tooth else ''} "
                        f"from {artifact.public_id}")
        db.add(TreatmentItem(
            public_id=public_id("ITM"), extraction_id=extraction.id,
            tooth_id=item.tooth, treatment_id=item.treatment,
            predicate=Modality(item.predicate), confidence=item.confidence,
            provenance_id=prov.id,
            page=loc.page if loc else None,
            source_span=loc.span if loc else None,
            derivation_run_id=derivation_run_id,
            derivation_status=DerivationStatus.ACTIVE,
        ))
    db.flush()
    audit(db, "extraction_completed", case_id=artifact.case_id,
          artifact_public_id=artifact.public_id)
    return extraction


def build_findings_from_extraction(db: Session, artifact: Artifact,
                                   extraction: Extraction | None,
                                   derivation_run_id: int | None = None) -> list[Finding]:
    """Findings are built ONLY from validated extraction outputs (P0-02/D-Q2).
    TreatmentItem findings carry the atomic tooth-treatment relationship; locator
    provenance is inherited from the source provenance record (D5) — never page 1.
    FINANCIAL_DOCUMENT_PRESENT is SYSTEM_DERIVED from classification (allowed truth
    source), not raw-text mining.
    """
    findings: list[Finding] = []

    def add_finding(finding_type: str, statement: str, subject: str | None,
                    obj: str | None, confidence: float, page: int | None = None,
                    span: str | None = None, model_run_id: int | None = None,
                    field: ExtractedField | None = None,
                    item: TreatmentItem | None = None,
                    predicate: Modality = Modality.MENTIONED,
                    truth_type: TruthType = TruthType.DOCUMENT_EXTRACTED):
        origin = (f"TreatmentItem {item.public_id}" if item
                  else f"ExtractedField {field.id if field else '-'}")
        prov = create_provenance(db, truth_type=truth_type, artifact_id=artifact.id,
                                 page=page, source_span=span, model_run_id=model_run_id,
                                 confidence=confidence,
                                 description=f"derived from {origin} of {artifact.public_id}")
        findings.append(Finding(
            public_id=public_id("FND"), case_id=artifact.case_id, artifact_id=artifact.id,
            finding_type=finding_type, statement=statement,
            normalized_subject=subject, normalized_object=obj,
            predicate=predicate.value, confidence=confidence,
            truth_type=truth_type, provenance_id=prov.id,
            extracted_field_id=field.id if field else None,
            treatment_item_id=item.id if item else None,
            derivation_run_id=derivation_run_id,
            derivation_status=DerivationStatus.ACTIVE,
        ))

    if extraction is not None:
        # Atomic treatment items first (D-Q2)
        items = (db.query(TreatmentItem)
                 .filter(TreatmentItem.extraction_id == extraction.id).all())
        for item in items:
            ont.validate_treatment(item.treatment_id)
            if item.tooth_id:
                ont.validate_tooth(item.tooth_id)
            subject = f"{item.tooth_id} " if item.tooth_id else ""
            item_prov = (db.query(ProvenanceRecord)
                         .filter(ProvenanceRecord.id == item.provenance_id).one_or_none())
            add_finding("TREATMENT_ITEM",
                        f"Document establishes {subject}"
                        f"{item.treatment_id} ({item.predicate.value})",
                        item.tooth_id, item.treatment_id, item.confidence,
                        page=item_prov.page if item_prov else None,
                        span=item_prov.source_span if item_prov else None,
                        model_run_id=item_prov.model_run_id if item_prov else None,
                        item=item, predicate=item.predicate)

        fields = (db.query(ExtractedField)
                  .filter(ExtractedField.extraction_id == extraction.id).all())
        for field in fields:
            field_prov = (db.query(ProvenanceRecord)
                          .filter(ProvenanceRecord.id == field.provenance_id)
                          .one_or_none())
            page = field_prov.page if field_prov else None
            span = field_prov.source_span if field_prov else None
            if field.field_name == "tooth_reference" and field.normalized_value:
                ont.validate_tooth(field.normalized_value)
                add_finding("TOOTH_REFERENCE",
                            f"Document references {field.normalized_value}",
                            field.normalized_value, None, field.confidence,
                            page=page, span=span,
                            model_run_id=field_prov.model_run_id if field_prov else None,
                            field=field)
            elif field.field_name in ("price", "total_price") and field.raw_value:
                add_finding("TREATMENT_QUOTED",
                            f"Document quotes price {field.raw_value}",
                            None, field.normalized_value, field.confidence,
                            page=page, span=span,
                            model_run_id=field_prov.model_run_id if field_prov else None,
                            field=field)

    if artifact.category == ArtifactCategory.FINANCIAL_DOCUMENT:
        prov = create_provenance(db, truth_type=TruthType.SYSTEM_DERIVED,
                                 artifact_id=artifact.id, confidence=0.9,
                                 description=f"classification of {artifact.public_id}")
        findings.append(Finding(
            public_id=public_id("FND"), case_id=artifact.case_id, artifact_id=artifact.id,
            finding_type="FINANCIAL_DOCUMENT_PRESENT",
            statement=f"A financial document ({artifact.subtype.value}) is present",
            predicate=Modality.MENTIONED.value, confidence=0.9,
            truth_type=TruthType.SYSTEM_DERIVED, provenance_id=prov.id,
            derivation_run_id=derivation_run_id,
            derivation_status=DerivationStatus.ACTIVE,
        ))
    db.add_all(findings)
    db.flush()
    return findings
