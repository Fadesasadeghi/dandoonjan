# Engineering workflow

READ → VERIFY → TEST → PLAN → IMPLEMENT → RETEST → DOCUMENT

Read the [approved Gate 1 handoff](docs/handoff/gate-1/README.md) before continuing.
Its audit and Product Owner decisions are the current handoff; preserve useful
older documentation as history. The Gate 1 documentation lock is documentation
and Git only: commit, push, report, then stop until the next instruction.

## Principles

- Evidence before assumptions. Distinguish VERIFIED WORKING, VERIFIED BROKEN,
  PARTIALLY VERIFIED, and NOT VERIFIED; always state the tested scope.
- Make the smallest coherent change within the approved scope.
- Add regression tests for reproduced defects before fixing them.
- Preserve the modular-monolith architecture unless change is strongly justified
  and the architecture Stop Condition is resolved.
- Preserve data, history, and independent source provenance.
- Use safe populated-database migration discipline: inspect schema and lifecycle
  assumptions, verify populated synthetic data, and preserve integrity and history.
- Do not use real credentials or paid services without approval.
- Perform targeted retesting plus broader regression testing appropriate to the change.
  For documentation-only gates, use lightweight documentation/repository checks;
  do not run implementation tests merely to create a documentation commit.
- Document verified implementation, test results, limitations, and remaining risks.
  Keep approved intent distinct from evidence of implementation.
- Make meaningful Git commits at engineering gates.

## Stop Conditions

Stop and request owner approval only when:

1. Product behavior is genuinely ambiguous.
2. A change may delete, corrupt, or irreversibly transform data.
3. Real credentials, payments, paid services, legal/privacy decisions, or sensitive
   production access are required.
4. A fundamental architecture change is necessary.
5. Repository behavior materially contradicts the approved product definition or
   safety requirements.
6. A material approved API/data contract would need to change.
7. Safe migration design requires unknown real deployed database state.

Ordinary reversible engineering decisions within the approved roadmap do not
require owner approval. The reproduced Gate 1 defects are already acknowledged
remediation scope; do not repeatedly seek approval for their ordinary reversible
fixes. Apply Stop Conditions to unresolved decisions or actions requiring them.

## Engineering Gate report

Report only useful handoff evidence:

- Changes/evidence.
- Tests and results, distinguishing prior results from checks run at this gate.
- Remaining relevant risks or NOT VERIFIED items.
- Commit SHA.
- Working-tree status.
