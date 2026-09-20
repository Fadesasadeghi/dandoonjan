# Domain Model

Entities (`app/domain/models.py`): User, Case, Artifact, ArtifactClassification,
ArtifactQualityAssessment, ModelRun, ProvenanceRecord, Extraction, ExtractedField,
TreatmentItem, Finding, Claim, EvidenceLink, EvidenceGap, KnowledgePack, Assessment,
SafetyResult, AssessmentSnapshot, Report, ProcessingRun, AuditEvent.

## P0.1 semantics (docs/P0_1_DECISIONS_LOCK.md)

- **TreatmentItem**: the atomic extracted tooth-treatment relationship
  (tooth, treatment, predicate/confidence, locator). Established during extraction;
  never reconstructed downstream (no cartesian products).
- **Compositional claims**: claim_type in {TREATMENT, TREATMENT_QUOTED, OTHER};
  treatment propositions carry `treatment_id` + `modality`
  (PLANNED/RECOMMENDED/REQUIRED; MENTIONED/PERFORMED reserved). Recommendation is
  not necessity; normalization never upgrades modality.
- **Derivations**: derived tables (classifications, quality rows, extractions,
  treatment items, findings, claims, links, gaps, assessments, safety results)
  carry `derivation_run_id` + `derivation_status`
  (ACTIVE / SUPERSEDED / NON_AUTHORITATIVE / NON_AUTHORITATIVE_LEGACY). Exactly one
  authoritative derivation per Case is ACTIVE; superseded/legacy rows are preserved
  and excluded from all current-state queries. Pre-P0.1 rows are
  NON_AUTHORITATIVE_LEGACY.

Key distinctions:
- **Claim** (proposition to assess: subject/predicate/object + source_type) vs
  **Finding** (directly observed/extracted fact) — separate tables, never merged.
- **ProvenanceRecord** ("where did this fact come from") vs **AuditEvent**
  ("what did the system do") — separate, audit is append-only.
- Truth types (PATIENT_REPORTED, CLINICIAN_REPORTED, DOCUMENT_EXTRACTED,
  MODEL_INFERRED, CLINICAL_KNOWLEDGE, SYSTEM_DERIVED) are stored on rows that
  carry facts and never silently merged.

Source of truth: versioned Structured Case + Evidence Graph + Knowledge Pack +
Immutable Assessment Snapshot. Reports/LLM output/frontend state are not sources.

## Claim/Finding semantics (P0-01, §14-15)

- Clinician-reported and patient-reported claims ARE assessable: document findings
  link to them in the evidence graph. MODEL_INFERRED duplicates of an existing
  reported claim (same type + subject) are never created.
- `Finding.predicate` captures source semantics: MENTIONED / PLANNED /
  RECOMMENDED / REQUIRED. Normalization never upgrades semantics (a mention is
  never turned into a requirement).
- Evidence links from document findings that merely mention a treatment use
  RELEVANT_TO, never SUPPORTS — a treatment plan mentioning RCT supports the
  existence of a recommendation, not medical necessity (no circular evidence).
- All canonical claim values pass `validate_claim_semantics` (tooth ids, treatment
  ids, claim types) before persistence; invalid candidates are rejected.
