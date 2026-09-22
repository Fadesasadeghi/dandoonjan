# RISKS

These risks remain open after the documentation lock. The approved Controlled
MVP / Demo scope excludes real patient data and clinical readiness.

| Risk | Implication for future work |
| --- | --- |
| Cross-case data isolation | Derivation authority must remain scoped to the correct case. |
| Historical/current-state safety contamination | Historical assessments and safety state must not contaminate current processing. |
| Stale current-report semantics | Preserved historical reports must never be returned as current after newer blocked processing. |
| Populated migration/data integrity | Repair migration paths, ORM/schema drift, and startup-created database lifecycle entry; verify populated synthetic databases. |
| Existing derived data | Code fixes may not automatically repair already-derived data; assess repair/reprocessing while preserving history and provenance. |
| Storage containment/security boundary | Sibling-prefix/path-boundary behavior can escape intended containment. |
| SQLite foreign-key integrity | Disabled FK enforcement permits integrity failures in local development/testing. |
| Cache/reuse invalidation | Corrected processing identity may invalidate prior reusable results; verify the transition. |
| API/client compatibility | Correcting current-report semantics may affect clients; preserve approved contracts or invoke the relevant Stop Condition. |
| Deployment reproducibility | Packaging omission and unverified Docker/hosted/PostgreSQL behavior prevent a verified deployment claim. |
| Clinical scope | Clinical correctness/readiness is unverified; decision-support demo output must not be represented as autonomous diagnosis or clinical-ready. |

No production legacy database currently requires migration. This does not waive
safe populated-synthetic-database migration discipline. See [AUDIT](AUDIT.md) for
verification limits and [DECISIONS](DECISIONS.md) for approved constraints.
