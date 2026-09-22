# ROADMAP

Approved future implementation order:

1. Regression tests for reproduced defects.
2. Storage containment.
3. Case-scoped derivation authority/isolation.
4. Historical/current assessment and safety isolation.
5. Current-report semantics.
6. Source-distinct claim provenance.
7. Processing identity.
8. Fresh/reused terminal outcome parity.
9. Migrations/schema integrity.
10. Rejected-upload audit durability.
11. Docker/deployment.
12. Remaining release verification.

Preserve the current modular-monolith architecture unless a Stop Condition
requires reconsideration. Use the root [engineering workflow](../../../AGENTS.md)
and the [approved decisions](DECISIONS.md).

Implementation and subsequent gates follow:

IMPLEMENT → RETEST → DOCUMENT → RELEASE CANDIDATE.

Remaining release verification must address the [audit's verification limits](AUDIT.md),
including PostgreSQL deployment, provider failure behavior, deployment execution,
and at least five simultaneous processing requests with correct isolation. MVP
acceptance includes case editing/versioning and adding evidence to an existing case.
Deep Links and the clinician-review workflow are deferred.

This file records the approved order, not completed fixes. Do not begin P0/P1/P2
implementation as part of the documentation lock. Stop after committing, pushing,
and reporting this gate; wait for the next instruction.
