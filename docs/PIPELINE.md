# Pipeline

`app/pipeline/orchestrator.py` runs: text extraction -> classification ->
quality gate -> extraction -> findings -> claims -> evidence graph -> gap
analysis -> assessment -> safety gate -> snapshot -> report.

- **Canonical data flow (P0-02)**: Artifact -> Extraction -> ExtractedField ->
  Normalization -> Finding. Findings are built only from validated normalized
  extraction outputs; raw artifact text is never re-read downstream.
- **Quality Gate actually gates (P0-07)**: per-artifact decision
  CONTINUE / CONTINUE_WITH_LIMITATIONS / NEEDS_MORE_EVIDENCE / REJECT_ARTIFACT.
  All-rejected/all-insufficient input sends the Case to NEEDS_MORE_EVIDENCE;
  rejected artifacts skip extraction; limitations stay visible in quality rows.
- **Idempotency (P0-04)**: a pipeline-level run records the effective-input hash
  (case texts, artifact ids/hashes/texts, module versions). Identical input
  reuses the prior successful result; changed input produces a new run identity.
  Stage runs increment attempts; identical identity never raises IntegrityError.
- **Case versioning (P0-04)**: bumps on artifact add and case text edits.
- **Transaction safety (§17)**: stage-level commits keep completed stages
  auditable; a failed stage rolls back its partial state, records a FAILED
  ProcessingRun + audit event, moves the Case to FAILED (retryable), and never
  commits invalid output.
- Every AI call goes through the ModelGateway; outputs pass strict schema +
  ontology + semantic validation before persistence (P0-03).

## P0.1 derivation lifecycle

Canonical order per processing request:
1. materialize artifact text; compute `effective_input_hash`;
2. reuse check FIRST: an authoritative terminal result (SUCCEEDED + ACTIVE
   pipeline-level run, same hash) is returned without creating any run (D8: same
   public contract, incl. `report_kind`);
3. only otherwise: create the derivation ProcessingRun (RUNNING,
   attempt = max(prev)+1; FAILED runs are never reusable) — its id is the
   `derivation_run_id` stamped on every derived row;
4. stages run with per-stage commits (auditable);
5. on full success: ONE atomic commit — prior ACTIVE rows -> SUPERSEDED, this
   derivation's rows stay ACTIVE, run -> SUCCEEDED + ACTIVE (no authority vacuum);
6. on failure: partial state rolled back, committed rows -> NON_AUTHORITATIVE,
   run -> FAILED, previous derivation remains ACTIVE.
NEEDS_MORE_EVIDENCE and BLOCKED outcomes are recorded as authoritative terminal
results and are reusable. Intake safety screening (text-only) runs before any
document-dependent early exit; safety and evidence sufficiency are orthogonal
(D3): a case may be NEEDS_MORE_EVIDENCE and URGENT_EVALUATION simultaneously.
