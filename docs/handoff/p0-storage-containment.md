# P0 storage containment gate

Recorded: 2026-09-22. Scope: artifact storage containment only.
Starting commit: `e7574ef2d9af892ec984d9259c0bf652602ccec2` on `agent/sadeghi`.
Before editing, HEAD, the local tracking ref, and the remote branch matched that
commit, and the working tree was clean.

Authority: [AGENTS.md](../../AGENTS.md), the approved [Gate 1 roadmap](gate-1/ROADMAP.md),
and the [P0 regression-test gate](p0-regression-tests.md).

## Root cause and implementation

Both `store_bytes` and `read_bytes` checked containment with
`os.path.abspath(candidate).startswith(root)`. This compared text prefixes instead
of path ancestry: `store-neighbor` passed as a child of `store`. `abspath` also
did not resolve filesystem symlinks.

The storage module now resolves the configured root and uses a shared
`_contained_path` helper to resolve each candidate and check `Path.is_relative_to`
against that root. The helper returns the resolved target, and both reads and
writes use that returned path for I/O. Absolute paths outside the root and parent
escapes therefore follow the same rejection rule as sibling-prefix escapes.

For writes, resolution includes existing parent symlinks even if the final UUID
directory/file does not exist. Validation precedes directory creation; the
resolved target is checked again after parents are created. The final open uses
the resolved target rather than reopening the original key through a symlink
alias. Exclusive binary creation (`xb`) enforces the existing no-overwrite intent
and refuses a file/symlink that already occupies the new opaque filename.
Resolution/I/O errors, including symlink-loop errors, become `StorageError`.

Public signatures, filename sanitization, UUID-based relative storage-key format,
and successful artifact read/write behavior are preserved. Inspected callers are
`app/core/artifacts/ingestion.py` (write) and `app/pipeline/orchestrator.py` (read);
neither required changes. No regression test was modified or marked `xfail`.

## Exact files changed

- `app/security/ingestion.py`: shared resolved containment check and bounded I/O changes.
- `docs/handoff/p0-storage-containment.md`: this gate record.
- `DANDOONJAN_CURRENT_STATE_LOCK.md`: current gate pointer and prior-gate labeling.

No other source, tests, migrations, dependency declarations, Docker/deployment
files, or approved product/API contracts changed. No secrets, databases, logs,
temporary files, or generated artifacts are included in the commit.

## Verification

Executed with the same temporary Windows CPython 3.11 environment as the
regression-test gate, using synthetic data and deterministic/mock AI only.
No environment dependency changes were needed for this gate.

| Command (`python` from that environment) | Total | Passed | Failed | Errors | Skipped | Warnings |
| --- | --- | --- | --- | --- | --- | --- |
| `python -m pytest tests/regression_p0/test_storage.py -q --tb=short -rfs` | 9 | 7 | 0 | 0 | 2 | 0 |
| `python -m pytest tests/test_ingestion.py tests/test_api.py tests/test_pipeline.py -q --tb=short` | 18 | 18 | 0 | 0 | 0 | 4 |
| `python -m pytest tests --ignore=tests/regression_p0 -q --tb=short` | 109 | 109 | 0 | 0 | 0 | 4 |
| `python -m pytest tests -q --tb=short -rfs` | 138 | 116 | 20 expected | 0 | 2 | 4 |

Compared the combined failure node IDs with the prior gate: exactly these three
failures disappeared, with no unexpected passes or new failures:

- `test_storage_read_rejects_escape[sibling-prefix]`
- `test_storage_read_rejects_escape[absolute-sibling-prefix]`
- `test_storage_write_rejects_parent_escape[store-neighbor]`

The four existing storage controls continue to pass. The full existing suite
remains at 109 passed. The four broader-suite deprecation warnings are unchanged.
Complete diff review, `git diff --check`, syntax checks, and documentation-link
checks passed.

## Remaining expected P0 failures

All 20 non-storage failure node IDs match the previous gate:

- Cross-case authority/evidence reuse: 2.
- Historical/current safety and assessment isolation: 2.
- Source-distinct claim provenance: 1.
- Processing identity (model/provider/pack version/pack identity): 4.
- Reportless terminal reuse safety parity: 3.
- Stale current report after BLOCKED processing: 1.
- Rejected-upload audit durability: 1.
- Populated migration paths, startup-schema adoption, schema FK drift, and SQLite FK enforcement: 5.
- Docker frontend packaging: 1.

These remain visible ordinary failures and are not fixed by this gate. Exact test
names and the established evidence remain in the [regression gate record](p0-regression-tests.md).

## Risks and verification limits

- **VERIFIED WORKING:** executable storage regressions, including sibling-prefix
  reads/writes, ordinary parent traversal rejection, outside absolute-path
  rejection, and valid descendant round trips; existing ingestion/API/pipeline
  behavior in the tested scope.
- **NOT VERIFIED:** symlink read/write regressions on a capable runtime. Both
  encoded cases skipped because Windows returned `WinError 1314` while creating
  the directory symlink; no enforcement result is inferred from those skips.
- Filesystem ownership remains relevant: resolved-path checks and exclusive file
  creation are not an atomic defense against a local actor concurrently replacing
  parent directories between validation and opening. The storage tree must remain
  application-controlled. No adversarial filesystem race test was performed.
- Broader Gate 1 limits remain: real PostgreSQL/provider/hosted/browser behavior,
  Docker build/run, HEIC, concurrency/load, backup/restore, and clinical readiness.

This gate ends with one `fix: enforce artifact storage containment` commit, push
to `origin agent/sadeghi`, and publication verification. Do not begin the next
P0 implementation gate until instructed.
