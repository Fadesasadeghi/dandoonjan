# DANDOONJAN_CURRENT_STATE_LOCK

Current continuation: [approved Gate 1 handoff](docs/handoff/gate-1/README.md)
(recorded 2026-09-22). Its audit, roadmap, and Product Owner decisions supersede
conflicting completion/readiness claims below. The earlier record is preserved as
historical context; it is not evidence that Gate 1 defects are fixed.

Current implementation: [P0 historical/current isolation gate](docs/handoff/p0-historical-current-isolation.md)
(2026-09-22). Both historical/current regressions pass; 16 other P0 failures remain.
Historical rows are preserved; stale-current-report semantics remain unresolved.

Prior implementation: [P0 case isolation gate](docs/handoff/p0-case-isolation.md)
(2026-09-22). Preserved without changes; both case-isolation regressions still pass.

Prior implementation: [P0 storage containment gate](docs/handoff/p0-storage-containment.md)
(2026-09-22). Preserved without changes; executable storage regressions still pass.

Prior tests-only gate: [P0 regression-test gate](docs/handoff/p0-regression-tests.md)
(2026-09-22). Records the regression baseline before the storage fix.

- **Implementation date**: 2026-09-06
- **P0 Architecture Reconciliation completed**: 2026-09-06 (all 12 issues fixed;
  see `docs/P0_ARCHITECTURE_RECONCILIATION.md`)
- **P0.1 Decisions Lock + build completed**: 2026-09-06
  (see `docs/P0_1_DECISIONS_LOCK.md` — D-Q1..D-Q4, D1..D8 all implemented)
- **Architecture version**: DANDOONJAN_EVIDENCE_CORE_V0 — ARCHITECTURE LOCKED 10/10

## Schema migration version
- `13cb12f30f53` — initial domain schema
- `d632177845ea` — P0: knowledge-pack (id, version) uniqueness, Finding.predicate +
  extracted_field_id link
- `a5716dc9a797` — P0: Claim.confidence
- `3b805a8b02ae` — **P0.1**: `treatment_items` table; derivation columns
  (`derivation_run_id` + `derivation_status`) on all derived tables;
  ProcessingRun.`authority` + self-referencing `derivation_run_id`;
  Claim.`treatment_id` + Claim.`modality`; ProvenanceRecord.`bounding_box`.
  Data policy: ALL pre-P0.1 derived rows are `NON_AUTHORITATIVE_LEGACY`
  (preserved, never authoritative, never deleted) per Correction 1.
- `alembic/env.py` resolves DJ_DATABASE_URL through app config (P0-10).

## P0.1 decisions implemented (all FIXED/LOCKED)
- **D-Q1** derivation isolation: pipeline-level ProcessingRun = derivation scope;
  reuse resolution BEFORE run creation; atomic authority switch on success
  (old ACTIVE → SUPERSEDED); failures keep the prior derivation authoritative
  (no vacuum); legacy rows NON_AUTHORITATIVE_LEGACY.
- **D-Q2** `TreatmentItem`: atomic tooth-treatment relationship extracted at
  extraction time (line-level association); persisted relationally; ZERO cartesian
  reconstruction downstream; independent tooth references preserved.
- **D-Q3** compositional claims: TREATMENT + `treatment_id` + `modality`
  (PLANNED/RECOMMENDED/REQUIRED routed by explicit language only; a plan listing
  never yields REQUIRED); Knowledge Pack keys are `TREATMENT|MODALITY`
  (`kp-dev-v1.2.0-modality`, still NOT CLINICALLY VALIDATED).
- **D-Q4** immutability: UPDATE + DELETE ORM guards on AssessmentSnapshot/
  AuditEvent/Artifact; bulk-op ban enforced by static test
  (`test_dq4_bulk_ops_on_protected_entities_banned_in_app_code`); integrity hash
  verified before every report composition. Raw-SQL bypass by a privileged DB
  operator remains a documented V0 limitation (triggers reserved for production).
- **D1** attempts = max(prev)+1 everywhere; failed+successful runs coexist; no
  IntegrityError on any retry path. **D2** NEEDS_MORE_EVIDENCE is a reusable
  terminal result. **D3** intake safety screening before document-dependent early
  exit; safety ⊥ evidence-sufficiency (urgent report may exist while case is
  NEEDS_MORE_EVIDENCE). **D4** snapshot freezes full run provenance (derivation/
  stage/model runs, extractions, fields, items, provenance ids, artifact hashes).
  **D5** locators propagate (never hardcoded page). **D6** جرم گیری →
  TREATMENT_SCALING (+ ZWNJ variant). **D7** dead assertions removed.
  **D8** reuse results expose the same public contract incl. `report_kind`.

## Test status
- `python -m pytest tests -q` → **106 passed**.
- `manual_verification_p0.py` scenarios A–H: **ALL PASS** (A claim semantics,
  B idempotent reuse, C TOOTH_900 + C2 retry, D manual review, E tampering,
  F multi-tooth no cartesian, G revision isolation, H safety-before-exit).
- Alembic chain verified from empty DB to `3b805a8b02ae (head)`.

## Known limitations (explicit, not hidden TODOs)
1. `OpenAIProvider` remains a stub; MockProvider is the canonical provider.
2. Single dev user; no authentication.
3. Synchronous processing (no queue); derivations are idempotency-ready for one.
4. No image analysis (policy DISABLED); ImageAnalysisProvider boundary reserved.
5. Report composer is deterministic/template-based (deliberate).
6. MockProvider line-level tooth↔treatment association: treatments and teeth on
   DIFFERENT lines are extracted as unassociated items (tooth=None) — correct per
   "never reconstruct downstream"; a real provider would resolve context.
7. Knowledge Pack RECOMMENDED entries currently share requirement shapes with
   REQUIRED — splitting them is clinical work (out of scope, NOT VALIDATED).
8. Raw-SQL bypass of immutability remains possible for privileged operators
   (integrity hash detects; triggers reserved).
9. Automated CONTRADICTED assessments still need contradicting-link heuristics.

## Active risks
- Dev knowledge pack must never be presented as clinical guidance; production must
  set DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK=true and PostgreSQL DATABASE_URL.
- Migrated databases: every legacy Case needs one reprocess to become
  P0.1-authoritative (by design).

## Knowledge pack status
`dandoonjan_dev_pack` v`kp-dev-v1.2.0-modality`, DEVELOPMENT,
review_status NOT_CLINICALLY_VALIDATED. Composite treatment|modality keys.

## AI provider status
MockProvider (deterministic, offline) only; test-only deterministic providers
(InvalidToothProvider, EmptyExtractionProvider, LowConfidenceProvider, malicious
variants) live in tests/verification scripts.

## Next allowed implementation phase
P0.1 release conditions are met. Candidate next steps (product priority): a real
clinician-reviewed Knowledge Pack workflow (REVIEW_REQUIRED → CLINICIAN_REVIEWED),
authentication, or the background worker — in that architectural order.
