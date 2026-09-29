"""Canonical domain model. Core relationships are explicit columns, never a JSON blob.

Versioning: every versioned artifact of reasoning (prompt/schema/ontology/pack)
is stamped on the rows that depend on it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Enum as SAEnum, Float, ForeignKey,
                        Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.enums import (AssessmentStatus, ArtifactCategory, ArtifactSubtype,
                              CaseStatus, ClaimType, ConfidenceLevel, DerivationStatus,
                              EvidenceRelationship, GapImportance, GapStatus,
                              KnowledgePackStatus, Modality, ProcessingRunStatus,
                              RunAuthority, SafetyState, TruthType, UsabilityState)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def public_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(255), default="patient")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[CaseStatus] = mapped_column(SAEnum(CaseStatus), default=CaseStatus.CREATED)
    version: Mapped[int] = mapped_column(Integer, default=1)
    question_text: Mapped[str] = mapped_column(Text, default="")
    context_text: Mapped[str] = mapped_column(Text, default="")
    dentist_recommendation_text: Mapped[str] = mapped_column(Text, default="")
    ontology_version: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                onupdate=utcnow)

    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="case")
    claims: Mapped[list["Claim"]] = relationship(back_populates="case")


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    document_role: Mapped[str] = mapped_column(String(32), default='unspecified')
    safe_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(255), default="")
    detected_mime_type: Mapped[str] = mapped_column(String(255), default="")
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    category: Mapped[ArtifactCategory] = mapped_column(SAEnum(ArtifactCategory),
                                                       default=ArtifactCategory.UNKNOWN)
    subtype: Mapped[ArtifactSubtype] = mapped_column(SAEnum(ArtifactSubtype),
                                                     default=ArtifactSubtype.UNKNOWN)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="artifacts")
    classifications: Mapped[list["ArtifactClassification"]] = relationship(back_populates="artifact")
    quality_assessments: Mapped[list["ArtifactQualityAssessment"]] = relationship(
        back_populates="artifact")
    findings: Mapped[list["Finding"]] = relationship(back_populates="artifact")


class ArtifactClassification(Base):
    __tablename__ = "artifact_classifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"), index=True)
    category: Mapped[ArtifactCategory] = mapped_column(SAEnum(ArtifactCategory))
    subtype: Mapped[ArtifactSubtype] = mapped_column(SAEnum(ArtifactSubtype))
    confidence: Mapped[float] = mapped_column(Float)
    truth_type: Mapped[TruthType] = mapped_column(SAEnum(TruthType))
    model_run_id: Mapped[int | None] = mapped_column(ForeignKey("model_runs.id"), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), default="")
    schema_version: Mapped[str] = mapped_column(String(64), default="")
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artifact: Mapped[Artifact] = relationship(back_populates="classifications")


class ArtifactQualityAssessment(Base):
    __tablename__ = "artifact_quality_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"), index=True)
    dimension: Mapped[str] = mapped_column(String(64))
    state: Mapped[UsabilityState] = mapped_column(SAEnum(UsabilityState))
    reason: Mapped[str] = mapped_column(Text, default="")
    rules_version: Mapped[str] = mapped_column(String(64), default="")
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artifact: Mapped[Artifact] = relationship(back_populates="quality_assessments")


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt_id: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(64))
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="SUCCEEDED")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    bounding_box: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_id: Mapped[int | None] = mapped_column(ForeignKey("extractions.id"), nullable=True)
    model_run_id: Mapped[int | None] = mapped_column(ForeignKey("model_runs.id"), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    truth_type: Mapped[TruthType] = mapped_column(SAEnum(TruthType))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Extraction(Base):
    __tablename__ = "extractions"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"), index=True)
    schema_name: Mapped[str] = mapped_column(String(128))
    schema_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    model_run_id: Mapped[int | None] = mapped_column(ForeignKey("model_runs.id"), nullable=True)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    fields: Mapped[list["ExtractedField"]] = relationship(back_populates="extraction")
    treatment_items: Mapped[list["TreatmentItem"]] = relationship(
        back_populates="extraction")


class TreatmentItem(Base):
    # Atomic extracted tooth-treatment relationship (D-Q2): established during
    # extraction while source context is available; never reconstructed downstream.
    __tablename__ = "treatment_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    extraction_id: Mapped[int] = mapped_column(ForeignKey("extractions.id"), index=True)
    tooth_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    treatment_id: Mapped[str] = mapped_column(String(64))
    predicate: Mapped[Modality] = mapped_column(SAEnum(Modality))
    confidence: Mapped[float] = mapped_column(Float)
    provenance_id: Mapped[int | None] = mapped_column(ForeignKey("provenance_records.id"),
                                                      nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    bounding_box: Mapped[str | None] = mapped_column(Text, nullable=True)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    extraction: Mapped[Extraction] = relationship(back_populates="treatment_items")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    extraction_id: Mapped[int] = mapped_column(ForeignKey("extractions.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    raw_value: Mapped[str] = mapped_column(Text, default="")
    normalized_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    provenance_id: Mapped[int | None] = mapped_column(ForeignKey("provenance_records.id"),
                                                      nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    extraction: Mapped[Extraction] = relationship(back_populates="fields")


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    finding_type: Mapped[str] = mapped_column(String(128))
    statement: Mapped[str] = mapped_column(Text)
    normalized_subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_object: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Semantic predicate: MENTIONED / PLANNED / RECOMMENDED / PERFORMED / REQUIRED.
    # Never upgraded during normalization (no MENTIONED -> REQUIRED invention).
    predicate: Mapped[str] = mapped_column(String(32), default="MENTIONED")
    extracted_field_id: Mapped[int | None] = mapped_column(
        ForeignKey("extracted_fields.id"), nullable=True)
    treatment_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment_items.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    truth_type: Mapped[TruthType] = mapped_column(SAEnum(TruthType))
    provenance_id: Mapped[int | None] = mapped_column(ForeignKey("provenance_records.id"),
                                                      nullable=True)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artifact: Mapped[Artifact | None] = relationship(back_populates="findings")


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    claim_type: Mapped[ClaimType] = mapped_column(SAEnum(ClaimType))
    subject: Mapped[str] = mapped_column(String(64), default="")
    predicate: Mapped[str] = mapped_column(String(128), default="")
    object_value: Mapped[str] = mapped_column(String(255), default="")
    treatment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    modality: Mapped[Modality | None] = mapped_column(SAEnum(Modality), nullable=True)
    source_type: Mapped[TruthType] = mapped_column(SAEnum(TruthType))
    source_reference: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    provenance_id: Mapped[int | None] = mapped_column(ForeignKey("provenance_records.id"),
                                                      nullable=True)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="claims")
    evidence_links: Mapped[list["EvidenceLink"]] = relationship(back_populates="claim")
    gaps: Mapped[list["EvidenceGap"]] = relationship(back_populates="claim")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="claim")


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id"), nullable=True)
    evidence_reference: Mapped[str] = mapped_column(String(255))
    # DB column keeps the canonical name "relationship"; attr avoids shadowing
    # sqlalchemy.orm.relationship.
    relationship_type: Mapped[EvidenceRelationship] = mapped_column(
        "relationship", SAEnum(EvidenceRelationship))
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    source_type: Mapped[TruthType] = mapped_column(SAEnum(TruthType))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    provenance_id: Mapped[int | None] = mapped_column(ForeignKey("provenance_records.id"),
                                                      nullable=True)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    claim: Mapped[Claim] = relationship(back_populates="evidence_links")


class EvidenceGap(Base):
    __tablename__ = "evidence_gaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    gap_type: Mapped[str] = mapped_column(String(128))
    importance: Mapped[GapImportance] = mapped_column(SAEnum(GapImportance))
    status: Mapped[GapStatus] = mapped_column(SAEnum(GapStatus), default=GapStatus.MISSING)
    reason: Mapped[str] = mapped_column(Text, default="")
    knowledge_pack_version: Mapped[str] = mapped_column(String(64), default="")
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    claim: Mapped[Claim] = relationship(back_populates="gaps")


class KnowledgePack(Base):
    __tablename__ = "knowledge_packs"
    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_pack_id: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(64))
    status: Mapped[KnowledgePackStatus] = mapped_column(SAEnum(KnowledgePackStatus))
    review_status: Mapped[str] = mapped_column(String(64), default="NOT_CLINICALLY_VALIDATED")
    content: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("knowledge_pack_id", "version",
                                       name="uq_knowledge_pack_logical_version"),)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    status: Mapped[AssessmentStatus] = mapped_column(SAEnum(AssessmentStatus))
    supporting_evidence: Mapped[list] = mapped_column(JSON, default=list)
    contradicting_evidence: Mapped[list] = mapped_column(JSON, default=list)
    missing_evidence: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[ConfidenceLevel] = mapped_column(SAEnum(ConfidenceLevel))
    knowledge_pack_version: Mapped[str] = mapped_column(String(64))
    assessment_rules_version: Mapped[str] = mapped_column(String(64), default="")
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    claim: Mapped[Claim] = relationship(back_populates="assessments")


class SafetyResult(Base):
    __tablename__ = "safety_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    state: Mapped[SafetyState] = mapped_column(SAEnum(SafetyState))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    rules_version: Mapped[str] = mapped_column(String(64), default="")
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    derivation_status: Mapped[DerivationStatus] = mapped_column(
        SAEnum(DerivationStatus), default=DerivationStatus.NON_AUTHORITATIVE_LEGACY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssessmentSnapshot(Base):
    __tablename__ = "assessment_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    case_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON))
    safety_state: Mapped[SafetyState] = mapped_column(SAEnum(SafetyState))
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    immutable: Mapped[bool] = mapped_column(Boolean, default=True)
    versions: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON),
                                           default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("assessment_snapshots.id"), index=True)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    module: Mapped[str] = mapped_column(String(128))
    status: Mapped[ProcessingRunStatus] = mapped_column(SAEnum(ProcessingRunStatus))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    input_version: Mapped[str] = mapped_column(String(128), default="")
    input_hash: Mapped[str] = mapped_column(String(64), default="")
    output_version: Mapped[str] = mapped_column(String(128), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority: Mapped[RunAuthority] = mapped_column(SAEnum(RunAuthority),
                                                     default=RunAuthority.NON_AUTHORITATIVE)
    derivation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id"), nullable=True, index=True)
    model_run_id: Mapped[int | None] = mapped_column(ForeignKey("model_runs.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("case_id", "module", "input_hash", "attempt",
                                       name="uq_processing_run_identity"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    case_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(128), default="system")
    detail: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON),
                                         default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewRun(Base):
    __tablename__ = 'review_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('cases.id'), index=True)
    derivation_run_id: Mapped[int] = mapped_column(ForeignKey('processing_runs.id'), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    schema_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_index: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiagnosticHypothesis(Base):
    __tablename__ = 'diagnostic_hypotheses'
    id: Mapped[int] = mapped_column(primary_key=True)
    review_run_id: Mapped[int] = mapped_column(ForeignKey('review_runs.id'), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(Text)
    confidence_label: Mapped[str] = mapped_column(String(8))
    insufficient_support: Mapped[bool] = mapped_column(Boolean)


class HypothesisEvidence(Base):
    __tablename__ = 'hypothesis_evidence'
    id: Mapped[int] = mapped_column(primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey('diagnostic_hypotheses.id'), index=True)
    source_ref: Mapped[str] = mapped_column(String(255))
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey('artifacts.id'), nullable=True)
    dossier_revision_id: Mapped[int | None] = mapped_column(ForeignKey('dossier_revisions.id'), nullable=True)
    relationship_type: Mapped[str] = mapped_column(String(16))


class DossierRevision(Base):
    """Append-only intake history; empty fields mean not supplied, never 'none'."""
    __tablename__ = "dossier_revisions"
    __table_args__ = (UniqueConstraint("case_id", "case_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    case_version: Mapped[int] = mapped_column(Integer)
    symptoms: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[str] = mapped_column(Text, default="")
    medical_history: Mapped[str] = mapped_column(Text, default="")
    medications: Mapped[str] = mapped_column(Text, default="")
    allergies: Mapped[str] = mapped_column(Text, default="")
    treatment_plan: Mapped[str] = mapped_column(Text, default="")
    previous_reports: Mapped[str] = mapped_column(Text, default="")
    previous_treatments: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Register real-immutability event guards (P0-05) once all mapped classes exist.
from app.governance.immutability import register_immutability_guards  # noqa: E402
register_immutability_guards()
