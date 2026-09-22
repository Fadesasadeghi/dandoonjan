# P0 Rejected-Upload Audit Durability

- Starting commit: `5773b04079ec7ec02e949c460430c6895c38ef05`
- Root cause: the rejection audit row was added to the request session, then the error response caused `get_db()` to roll back that transaction.
- Fix: rejection auditing now uses the current application `SessionLocal` in a narrow independent transaction, commits the `artifact_rejected` event, closes that session, and then returns the unchanged 422 error. No artifact or invalid domain row is persisted.

## Verification

- Focused regression: **1 passed**.
- Relevant API/ingestion tests: **11 passed**.
- Existing suite excluding regression tests: **109 passed**.
- Combined suite: **135 passed, 1 expected failure, 2 skipped**.
- Remaining expected failure: Docker/frontend packaging.
- `git diff --check`: passed.

No migrations, dependencies, validation rules, or public error semantics changed.
