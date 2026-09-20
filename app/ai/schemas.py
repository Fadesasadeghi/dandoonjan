"""Strict output schemas (the schema firewall). AI output that fails these never enters core state.

Extraction schema v2 (D-Q2): treatment relationships are emitted as atomic
TreatmentItems — tooth/treatment association is established at extraction time and
never reconstructed downstream.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.ontology import ontology as ont

SCHEMA_VERSIONS = {
    "classification": "cls-schema-v1",
    "extraction": "ext-schema-v2",
    "claims": "claims-schema-v2",
    "report": "report-schema-v1",
}

MODALITIES = {"MENTIONED", "PLANNED", "RECOMMENDED", "REQUIRED", "PERFORMED", "QUOTED"}


class ClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    subtype: str
    confidence: float = Field(ge=0.0, le=1.0)


class SourceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int | None = None
    span: str | None = None
    bounding_box: str | None = None


class TreatmentItemOutput(BaseModel):
    """Atomic tooth-treatment relationship. tooth may be None when the source
    mentions a treatment without a tooth reference."""
    model_config = ConfigDict(extra="forbid")
    tooth: str | None = None
    treatment: str
    predicate: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_locator: SourceLocator | None = None

    @field_validator("treatment")
    @classmethod
    def _valid_treatment(cls, v: str) -> str:
        ont.validate_treatment(v)
        return v

    @field_validator("tooth")
    @classmethod
    def _valid_tooth(cls, v: str | None) -> str | None:
        if v is not None:
            ont.validate_tooth(v)
        return v

    @field_validator("predicate")
    @classmethod
    def _valid_modality(cls, v: str) -> str:
        if v not in MODALITIES:
            raise ValueError(f"unknown modality: {v}")
        return v


class ExtractionFieldOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_name: str
    raw_value: str
    normalized_value: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    page: int | None = None
    source_span: str | None = None


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[ExtractionFieldOutput] = []
    treatment_items: list[TreatmentItemOutput] = []


class ClaimCandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_type: str
    subject: str = ""
    predicate: str = ""
    object_value: str = ""
    treatment: str | None = None
    modality: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ClaimsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[ClaimCandidateOutput]


class ReportSectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    text: str


class ReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[ReportSectionOutput]
