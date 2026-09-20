# P0_1_DECISIONS_LOCK

Canonical architecture decisions for P0.1. Locked 2026-09-06 after Phase 1 discovery
(see conversation report) and owner answers. Implementation must not deviate without
explicitly reopening a decision here.

Acceptance philosophy (binding):

- **A**: A relationship absent from extraction must never be invented downstream.
- **B**: A report belongs to one exact authoritative derivation, not to "whatever
  rows currently exist for this case".
- **C**: Recommendation is not necessity.
- **D**: Historical evidence is preserved, but historical derived state cannot
  contaminate current assessment.

---

## D-Q1 — Authoritative Case revision boundary

**Decision**: Hybrid revision-stamped + superseded live derivations (Option C), with
an explicit **Derivation Run** scope distinct from `case.version`.

- `case.version` = human-readable business/input revision (unchanged semantics).
- A **derivation** = one authoritative processing result produced from a specific
  case version + effective input. The existing pipeline-level `ProcessingRun`
  (module=`pipeline`) IS the derivation scope; no second workflow system.
- `Finding`, `Claim`, `EvidenceLink`, `EvidenceGap`, `Assessment` (and per-artifact
  `ArtifactClassification`, `ArtifactQualityAssessment`, `Extraction`) each carry
  `derivation_run_id` + a `derivation_status` of `ACTIVE` / `SUPERSEDED`.
- Current-state queries read only `derivation_status == ACTIVE`.
- Old sets become `SUPERSEDED`, never deleted.

**Authority switch rule (critical)**: do not supersede V1 until V2 has fully
produced its authoritative set. Concretely: the pipeline-level ProcessingRun is
created **after idempotency/reuse resolution and before actual processing stages
begin** (status RUNNING, non-authoritative); derived rows are stamped with its id
as they are created; on full success, ONE atomic commit marks V1's rows SUPERSEDED,
V2's rows ACTIVE, and the run SUCCEEDED + authoritative. If V2 fails, V1 remains
authoritative and V2's partial rows remain non-authoritative (and are not visible
to current-state queries). No authority vacuum is ever allowed.

**Reuse ordering (critical)**: the reuse check happens BEFORE any derivation run is
created. Canonical order:
1. compute `effective_input_hash`;
2. find a reusable **authoritative terminal** result (SUCCEEDED pipeline-level run
   for the same hash — including NEEDS_MORE_EVIDENCE outcomes per D2);
3. if found → return the reused result; NO new ProcessingRun is created;
4. only when no reusable result exists → create the new ProcessingRun
   (status RUNNING, attempt = max(previous attempts for the same case+input_hash)+1)
   and use its id as `derivation_run_id`.
FAILED runs are never reusable; a retry after FAILED reuses nothing and starts a new
RUNNING derivation with the next attempt number.

**Snapshots**: reference exactly one `derivation_run_id`; all snapshot payload
content is read from rows of that derivation, never from `all rows where
case_id = X`. A report means: "generated from derivation Y of case version X".

**Reason**: lineage preserved (better than pure supersede), no implicit
"latest-valid" inference (better than pure revision-stamp filtering), explicit
canonical identity, immutable old snapshots.

**Rejected alternatives**: pure Option A (loses lineage); pure Option B (every
reader infers currency; no explicit authority marker).

**Affected**: `app/domain/models.py` (new columns), `app/pipeline/orchestrator.py`
(run lifecycle + atomic switch), `claims.py`, `assessment.py`, `stages.py`,
`reporting.py`, all current-state queries.

**Migration impact**: add `derivation_run_id` (FK processing_runs.id, nullable for
legacy) + `derivation_status` to the 8 derived tables; add authority semantics to
processing_runs usage.

**Legacy backfill policy (Correction 1 — binding)**: pre-P0.1 derived rows are NOT
migrated as ACTIVE. The old implementation is known to have produced
revision-contaminated derivations, cartesian Tooth↔Treatment claims, and
cross-subject evidence links. All pre-P0.1 derived rows are preserved but marked
`NON_AUTHORITATIVE_LEGACY` (or equivalent non-authoritative state) and must never
participate in current assessment, evidence graph, snapshots, or reports. The first
successful P0.1 derivation for a Case becomes that Case's first authoritative P0.1
derivation. Legacy history is never deleted.

**Acceptance tests**:
1. Reprocessed case (changed input) → old claims/findings/gaps SUPERSEDED; exactly
   one ACTIVE set; counts do not grow across revisions (V1 repro inverted).
2. Failed V2 processing → V1 rows still ACTIVE; V2 rows non-authoritative; no
   partially-superseded state.
3. Snapshot payload contains only rows of its own derivation_run_id.
4. Assessment/gap/evidence engines see only ACTIVE rows.

---

## D-Q2 — Tooth ↔ Treatment association: composite `TreatmentItem`

**Decision**: the tooth↔treatment relationship is established during extraction as
one atomic typed unit, persisted explicitly (not reconstructed, not opaque JSON).

- AI boundary: typed Pydantic sub-schema `TreatmentItemOutput`:
  `{tooth: "TOOTH_46"|null, treatment: "TREATMENT_ROOT_CANAL", predicate:
  PLANNED|RECOMMENDED|PERFORMED|QUOTED, confidence, page, span}`.
- Core persistence: dedicated `treatment_items` table (extraction_id FK, tooth_id,
  treatment_id, predicate, confidence, provenance_id, page, source_span) — explicit
  relational model so downstream modules never parse JSON.
- `TreatmentItem` is the source for a `TREATMENT_ITEM` Finding
  (subject=tooth, object=treatment, predicate) — one finding per atomic
  relationship, provenance inherited.
- Independent tooth-only references remain supported: "دندان 46 حساس است" →
  `TOOTH_REFERENCE` finding without treatment. Standalone tooth references are
  NEVER used to rebuild treatment associations.
- FORBIDDEN: cartesian reconstruction, nearest-neighbor, line-distance guessing —
  in claim building, findings, or evidence linking.

**Reason**: association is made where the text is understood; downstream stays
declarative; the same unit later covers QUOTED/PERFORMED without implying necessity.

**Rejected alternatives**: group_id/span-overlap linkage of independent fields
(heuristics moved downstream); proximity association at finding construction
(positional guessing).

**Affected**: `app/ai/schemas.py` (extraction schema v2), `app/ai/providers.py`
(mock extractor emits TreatmentItems), `app/pipeline/stages.py` (findings from
items), `app/pipeline/claims.py` (no cartesian), `app/domain/models.py`.

**Migration impact**: new `treatment_items` table; extraction schema version bump
(`ext-schema-v2`); no data backfill needed (dev data re-derivable).

**Acceptance tests**:
1. "Treatment Plan / Tooth 46: RCT / Tooth 36: Filling" → exactly 2 TreatmentItems
   → exactly 2 document claims with correct (tooth, treatment) pairs; no
   FILLING_REQUIRED/TOOTH_46, no ROOT_CANAL_REQUIRED/TOOTH_36 (V2 repro inverted).
2. Tooth-only text → TOOTH_REFERENCE finding, no treatment claim invented.
3. Every TREATMENT_ITEM finding traceable to a treatment_items row + provenance.

---

## D-Q3 — Claim modality: compositional Treatment + Modality (not enum explosion)

**Decision**: split modality compositionally. A treatment proposition claim is:

```text
claim_type  = TREATMENT            (coarse category; also TREATMENT_QUOTED, OTHER)
subject     = TOOTH_46
treatment   = TREATMENT_ROOT_CANAL (ontology-validated column)
modality    = PLANNED | RECOMMENDED | REQUIRED   (new enum column)
```

- Modalities in use now: `PLANNED` (plan lists treatment), `RECOMMENDED` (explicit
  recommendation language), `REQUIRED` (explicit necessity language:
  "حتماً باید عصب‌کشی شود"), `QUOTED` (financial, via TREATMENT_QUOTED claims).
  `MENTIONED` and `PERFORMED` reserved in the enum, unused in V0.1 routing.
- A treatment plan listing RCT produces modality PLANNED or RECOMMENDED — never
  REQUIRED automatically.
- `Finding.predicate` and `Claim.modality` use the same vocabulary; normalization
  never upgrades modality (PLANNED → REQUIRED forbidden).
- ClaimType enum collapses to `TREATMENT`, `TREATMENT_QUOTED`, `OTHER`.
  `normalize_treatment_from_claim_type` is retired; evidence matching uses
  `claim.treatment`.
- Knowledge Pack keys become composite: `"<TREATMENT_ID>|<MODALITY>"` (e.g.
  `TREATMENT_ROOT_CANAL|REQUIRED`, `TREATMENT_ROOT_CANAL|RECOMMENDED`). P0.1 ships
  the smallest DEVELOPMENT entries needed to prove routing/assessment (existing
  requirement sets mapped to the new keys; RECOMMENDED initially shares the same
  requirements, explicitly NOT CLINICALLY VALIDATED). Clinical expansion remains
  out of scope.
- A REQUIRED claim is assessed against evidence/policy ("do evidence and policy
  support necessity?"); a RECOMMENDED claim is assessed as
  "did clinician/document recommend this?" — different propositions, different
  report wording.

**Reason**: eliminates the contradictory `ROOT_CANAL_REQUIRED + predicate=RECOMMENDS`
row; enables the pack to demand stronger evidence for necessity later without
schema churn; no enum-space explosion.

**Rejected alternatives**: per-treatment necessity/recommended enum pairs
(ROOT_CANAL_RECOMMENDED, …) — combinatorial; status quo shape (type-level lie).

**Affected**: `domain/enums.py` (Modality, ClaimType), `ontology.py` (validate
treatment ids; retire claim-type→treatment map), `pipeline/claims.py`
(patterns route to treatment+modality), `knowledge/pack.py` (composite keys, pack
version bump), `pipeline/assessment.py` + `reporting.py` (label maps, wording),
`pipeline/stages.py` (predicate values).

**Migration impact**: claims table: add `treatment_id` (nullable string) +
`modality` (nullable enum); data migration maps legacy claim_type values
(ROOT_CANAL_REQUIRED → TREATMENT / TREATMENT_ROOT_CANAL / REQUIRED etc.);
knowledge pack content version bump.

**Acceptance tests**:
1. "دکتر گفت عصب کشی لازم است" → claim(TREATMENT, ROOT_CANAL, REQUIRED,
   CLINICIAN_REPORTED). "دکتر گفت عصب کشی خوبه" / plan listing → RECOMMENDED /
   PLANNED.
2. No claim exists with modality REQUIRED unless source text has explicit
   necessity language.
3. Gap engine produces requirements for `TREATMENT_ROOT_CANAL|REQUIRED` claims;
   RECOMMENDED claims get their own pack entry.
4. Report wording distinguishes recommendation-existence from necessity.

---

## D-Q4 — Immutability enforcement depth

**Decision**: strong application/ORM enforcement + integrity verification now; DB
triggers reserved as a documented production-hardening path.

- `before_update` + `before_delete` ORM guards on `AssessmentSnapshot` and
  `AuditEvent` (currently only before_update).
- Artifact: identity fields (storage_key, sha256, file_size, filenames, detected
  MIME) keep update guards; artifact DELETE guarded explicitly (not by FK accident).
- Snapshot payload stays canonicalized JSON with deterministic content hash;
  write-once row; `verify_snapshot_integrity` checked before every report use.
- Application code must not use ORM bulk update/delete against protected entities;
  add a static/architectural regression test (AST or grep-based) forbidding
  `query.update()` / `query.delete()` / `session.execute(update(...))` targeting
  protected models in app code.
- **Documented limitation**: a privileged DB operator can bypass application
  architecture with raw SQL; acceptable for V0, integrity hash detects it.
  No SQLite/PostgreSQL trigger implementations in P0.1.
- Snapshot payload is NOT flattened into child tables (rejected as unnecessary
  complexity for P0.1).

**Rejected alternatives**: DB triggers now (dialect divergence, migration
complexity); payload flattening (over-engineering for V0.1).

**Affected**: `app/governance/immutability.py`, `app/domain/models.py` (guard
registration), tests, `manual_verification_p0.py` Scenario E.

**Migration impact**: none.

**Acceptance tests**:
1. UPDATE snapshot → raise; DELETE snapshot → raise; DELETE audit event → raise.
2. Bulk/Core-level update on protected tables: forbidden by static test; if somehow
   executed, `verify_snapshot_integrity` returns False and composer refuses.
3. Artifact DELETE → explicit guard raise (not FK accident).

---

## D1 — ProcessingRun attempt correctness (failed retry)

**Decision**: for identical (case, module, input_hash), attempt =
max(previous_attempt) + 1 for every real retry — including the pipeline-level run
and the failure handler. A FAILED run and a later SUCCEEDED run for the same input
may coexist. No retry may raise IntegrityError / PendingRollbackError.

**Affected**: `app/pipeline/runs.py`, `app/pipeline/orchestrator.py`.
**Migration**: none.
**Acceptance tests**: fail→retry same input succeeds (V4 repro inverted); two
consecutive failures handled; stage attempts monotonic per input hash.

## D2 — NEEDS_MORE_EVIDENCE idempotency

**Decision**: a NEEDS_MORE_EVIDENCE outcome is a meaningful terminal result for an
effective input; record a pipeline-level derivation result for it. Identical rerun
reuses it (no duplicate classification/quality rows) unless input changed.

**Affected**: `app/pipeline/orchestrator.py`.
**Migration**: none. **Acceptance tests**: blank-doc case run twice → second run
`reused=True`, classification/quality row counts stable.

## D3 — Safety ordering: intake safety screening before document-dependent exit

**Decision**: patient-provided text safety screening runs at intake of processing —
before any artifact-sufficiency early exit — and its result is carried through.
Safety and evidence sufficiency are orthogonal and BOTH are preserved: a case may be
simultaneously `NEEDS_MORE_EVIDENCE` (evidence dimension → case.status) and
`URGENT_EVALUATION` (safety dimension → SafetyResult + snapshot/report). In that
combined state an urgent-safe report is produced immediately (urgent content does
not require documents); the case status is NOT forced to REPORT_READY. One engine,
two call points (intake screening + post-assessment screening); the stricter state
wins; the composer can never downgrade it.

**Affected**: `app/pipeline/orchestrator.py`, `app/pipeline/assessment.py` (split
text-scan helper), `reporting.py` (urgent-report path independent of assessments).
**Migration**: none.
**Acceptance tests**: blocked/urgent question with NO artifacts → safety_state
recorded, urgent-safe/blocked report behavior, case status reflects evidence
dimension; V8 repro inverted.

## D4 — Snapshot provenance completeness

**Decision**: snapshot freezes actual run provenance, at minimum: derivation
(pipeline) run id, relevant stage ProcessingRun ids, ModelRun ids, Extraction ids,
ExtractedField ids, ProvenanceRecord ids, Artifact ids + sha256, Claim ids,
Finding ids, EvidenceLink ids, EvidenceGap ids, Assessment ids, Knowledge Pack
id+version+status, ontology version, prompt id/version and schema version per
relevant ModelRun, safety result. A test must reconstruct the full
Report→ModelRun chain without invoking AI.

**Affected**: `app/pipeline/reporting.py`. **Migration**: none (payload JSON).
**Acceptance tests**: chain walk test from snapshot payload alone; V7 repro inverted.

## D5 — Source-locator propagation

**Decision**: never hardcode page 1. Finding provenance inherits the best locator
(page, span, bounding_box when available) from the ExtractedField/ProvenanceRecord
that generated it; TreatmentItems carry their own locator end-to-end.

**Affected**: `app/pipeline/stages.py`, `app/domain/models.py` (provenance bounding
box field if practical). **Migration**: minor (optional column).
**Acceptance tests**: finding.provenance.page/span == source field's locator.

## D6 — Ontology bug: جرم گیری

**Decision**: remove `جرم گیری` from the TREATMENT_EXTRACTION synonym list (it
currently shadows TREATMENT_SCALING due to iteration order). Regression coverage:
`normalize_treatment("جرم گیری") == "TREATMENT_SCALING"`.

**Affected**: `app/core/ontology/ontology.py`. **Migration**: none.
**Acceptance test**: as above; existing extraction tests updated.

## D7 — Dead/fake tests

**Decision**: remove all assertions of the form `assert X or True` and equivalent
non-falsifiable checks. Verified instances: `tests/test_p0_provenance.py:247`
and `:265`. Replace with real assertions or delete. Test count is not a goal.

## D8 — Reuse API contract

**Decision**: reused pipeline results expose the same public contract as fresh
results (`report_kind`, `status`, `snapshot`, `report`, `safety_state`, …), sourced
from the reused derivation's snapshot/report.

**Affected**: `app/pipeline/orchestrator.py` reuse path.
**Acceptance test**: fresh vs reused result key sets equal; report_kind present.

---

## Contradictions found between decisions and current repository

1. **Pipeline-run creation timing (D-Q1)**: the pipeline-level ProcessingRun is
   currently created only at the END (after snapshot/report). Derivation stamping
   requires it to exist before processing stages begin — but **after**
   idempotency/reuse resolution, per Correction 2. Resolution: reuse check first;
   then create the run (RUNNING, correct attempt); flip to SUCCEEDED+authoritative
   in the single atomic authority-switch commit. Design consequence, not a conflict.
2. **Pack vocabulary (D-Q3)**: `knowledge/pack.py` keys and
   `normalize_treatment_from_claim_type` are keyed on necessity-typed claim types.
   Both are replaced by composite keys / `claim.treatment`. Pack version bumps.
3. **Evidence-link matching (Step 3)**: current TREATMENT_MENTION matching is
   tooth-agnostic; replaced by (treatment AND subject-compatibility) matching
   against `claim.treatment`/`claim.subject`.
4. **Report/case-status interaction (D3)**: current code only produces reports on
   the post-assessment path. New rule: urgent-safe reports may exist while
   case.status is NEEDS_MORE_EVIDENCE (orthogonal dimensions). The existing
   invariant "MANUAL_REVIEW never yields a normal report; BLOCKED never yields a
   report" is unchanged.
5. **Legacy derived state (Correction 1)**: the current schema has no derivation
   status at all, and existing dev data was produced by the contaminated pipeline.
   Resolution: `derivation_status` gains a `NON_AUTHORITATIVE_LEGACY` value; the
   data migration marks all pre-P0.1 rows with it instead of ACTIVE. This also
   means the first run of a migrated system must reprocess every case (no legacy
   row can satisfy reuse), which is the intended behavior.

No other genuine contradictions were found.

READY TO IMPLEMENT P0.1
