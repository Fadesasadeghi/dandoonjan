# Testing

`tests/`: unit (domain, ontology, state machine, knowledge pack), ingestion security,
pipeline integration, invariants (INV-01..08), adversarial (prompt injection,
hallucinated tooth, missing evidence, contradicting documents, overclaim, urgent),
audit hygiene, API integration, and the evaluation harness.

`evaluation/`: golden cases (`golden_cases/`), adversarial (`adversarial/`),
safety (`safety/`) as JSON specs executed by `tests/test_evaluation_harness.py`.
Mock provider keeps everything offline; prompt/provider changes are regression-
testable by rerunning the harness.

Run: `python -m pytest tests -q`

## P0 additions

- `tests/test_p0_claims_extraction.py`: P0-01-A/B/C, P0-02-A/B/C, P0-03-A/B/C,
  §14 predicate semantics, §15 no-circular-evidence.
- `tests/test_p0_orchestration.py`: P0-04-A/B/C/D/E, P0-05-A/B/C/D, P0-06-A/B/C/D,
  P0-07-A/B/C.
- `tests/test_p0_provenance.py`: P0-08-A/B/C, P0-09-A/B/C, P0-10-A/B/C,
  INV-04/05/06 strong variants.
- `tests/test_evaluation_harness.py`: every spec key is enforced; unknown keys
  rejected; adversarial specs (injection, TOOTH_900, contradictory documents) and
  safety specs (urgent, blocked) run through the same harness.
- `manual_verification_p0.py`: executable scenarios A-E from master doc §23.

- `tests/test_p01_reconciliation.py`: derivation isolation (no accumulation, no
  authority vacuum, snapshot scoping), retry safety (D1), NEEDS_MORE_EVIDENCE
  idempotency (D2), safety-before-early-exit (D3), immutability depth
  (UPDATE/DELETE/bulk ban, D-Q4), locator propagation (D5), scaling synonym patch
  (D6), reuse contract parity (D8).
- `tests/test_p0_claims_extraction.py` updated to P0.1 semantics: compositional
  claims, TreatmentItems, no cartesian, explicit-necessity routing, subject-safe
  evidence links.
- `manual_verification_p0.py`: scenarios A-H (incl. multi-tooth, revision
  isolation, safety ordering).
