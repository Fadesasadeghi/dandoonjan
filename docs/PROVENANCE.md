# Provenance

Field-level provenance (`app/governance/record.py`, `ProvenanceRecord`): artifact
reference, page, source span (char range when available), model run, confidence,
truth type, description. Every Finding and ExtractedField links to a provenance row
(tested: INV-03). Answering "where did this fact come from?" requires no model rerun.
AuditEvent is separate and append-only; it never contains raw document content (tested).

## P0 snapshot provenance (P0-09)

Every AssessmentSnapshot freezes: case version, artifact ids + sha256, claim ids
(type/source/subject/predicate), finding ids (with predicate), evidence link ids
+ relationships, gap types, knowledge pack id + version + status, ontology,
assessment/safety/quality rules versions, provider/model, safety state and
reasons. Report -> Snapshot -> Assessment -> Claim -> Finding -> ExtractedField
-> Artifact is traceable without rerunning AI.

## P0.1 additions

- TreatmentItems and Findings inherit page/span (and bounding_box when available)
  from their source provenance — locators are never hardcoded.
- AssessmentSnapshot freezes `run_provenance`: derivation run id + attempt, stage
  ProcessingRun ids, ModelRun ids with provider/model/prompt id + version/schema
  version, Extraction ids, ExtractedField ids, TreatmentItem ids, ProvenanceRecord
  ids, plus artifact ids + sha256 and all claim/finding/link/gap/assessment ids of
  the derivation. The chain Report -> Snapshot -> Assessment -> Claim -> Finding ->
  ExtractedField/TreatmentItem -> Artifact -> ModelRun is reconstructable without
  invoking AI.
