# Final audit readiness runbook — P2 #4

Checkpoint: `agent/sadeghi-next-phase` at
`53e3a8fed86c8d98ec9dc1b86d89fcf9dbf9d8c2` (2026-10-18 consolidation).
This is the technical resume entry point for the completed local audit sequence.
It consolidates evidence; it does not grant release, clinical, provider or deployment
approval. Existing detailed handoffs remain historical evidence and are not replaced
or rewritten. Approved product decisions remain authoritative over this summary.

**Outcome:** the authorized local audit sequence is complete. There is no evidenced
remaining local implementation gate that must be invented before stopping. Preserve
the frozen frontend and modular monolith. Resume implementation only for a concrete
new defect or a separately authorized gate with its prerequisites available.

## Evidence rules and source precedence

No application tests, browser checks, migrations, server launches, provider calls or
hosted checks were run in P2 #4. All runtime results below are **previously recorded**
at the named gate, not new verification of this HEAD. This gate checks repository
identity, commit contents, documentation links/whitespace and workspace preservation.

Classifications are scoped:

- **VERIFIED:** recorded successful execution in the stated environment and gate.
- **PARTIALLY VERIFIED:** a narrower layer/platform/scenario has evidence, while the
  broader claim remains unproven.
- **NOT VERIFIED:** no acceptance evidence for the stated scope; not a defect claim.
- **AMBIGUOUS / POLICY REQUIRED:** behavior/limits require an approved decision.
- **BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED:** execution needs postponed access,
  authorization, credentials, clinical/privacy review or infrastructure.
- **FROZEN / DO NOT REVISIT:** approved/completed work; reopen only with new evidence
  or explicit owner authorization, not because other work is blocked.

Primary sources (labels used in the matrices):

| Label | Source and use |
| --- | --- |
| G1 | [Gate 1](gate-1/README.md), [decisions](gate-1/DECISIONS.md), [architecture](gate-1/ARCHITECTURE.md): synthetic controlled MVP, preserve history/provenance, Python 3.11, PostgreSQL deployment target, modular monolith |
| NP | [Next-phase contract](../next-phase/CONTRACT.md), [acceptance](../next-phase/ACCEPTANCE.md): dossier, immutable shared report snapshot, offline/browser/PDF evidence; older limits may be superseded only by later explicit evidence |
| AUTH | [Auth foundation](../auth/gate-1/README.md), [ownership/Demo integration](../auth/gate-2/README.md): use Gate 2 for current ownership, not Gate 1's historical public-route limitation |
| P0 | `ea42a38`, `7e2855f`; [freshness tests](../../tests/regression_p0/test_assessment_freshness.py), [concurrent text tests](../../tests/regression_p0/test_case_text_concurrency.py); older [authority](p0-historical-current-isolation.md) and [report](p0-current-report-semantics.md) handoffs |
| P1a | [Intake parity](p1-intake-validation-parity.md) |
| P1b | [Processing/retry](p1-processing-retry.md) |
| P2a | [Upload resource boundaries](p2-upload-resource-boundaries.md) |
| P2b | [Filesystem/database consistency](p2-filesystem-db-consistency.md) |
| P2c | [Preservation regressions](p2-preservation-regressions.md): detailed invariant-to-test coverage map and exact test commands |
| PG | [Phase 7.2](../phase-7/gate-7.2/README.md): private PostgreSQL 16.15 runtime/migrations/concurrency; 50 focused and 711 broad passes historically |
| OPS | [Phase 7.3](../phase-7/gate-7.3/README.md), [7.4](../phase-7/gate-7.4/README.md): packaging, preflight, finite proxy trust, storage/restart/paired restoration contract |
| STAGE | [Phase 7.5B](../phase-7/gate-7.5B/README.md), [7.5E](../phase-7/gate-7.5E/README.md): local staging preparation and explicit Render staging TLS boundary, not hosted acceptance |

No dedicated handoff for the recent P0 #1 freshness or P0 #2 case-text concurrency
fix was found in repository documentation. Both commits contain code/tests only.
Their tests and diffs were inspected; later P1/P2 executions provide recorded
runtime evidence. Do not invent original standalone P0 pass counts.

The root README's “unauthenticated RC” wording and old handoffs' outstanding failure
lists describe earlier checkpoints. AUTH Gate 2, PG, and the P0/P1/P2 sequence
supersede those specific limitations. Conversely, later SQLite passes do not renew
older PostgreSQL acceptance. Old PR states, platform prices/limits, URLs, IPs and
account entitlements are historical observations, not current operational facts.
Do not query external services merely to refresh them during this postponed gate.

## Readiness matrix

“Now” means action authorized/needed in this consolidation, not eventual release
work. All runtime evidence is historical to this documentation gate. A VERIFIED
row never means hosted, live-provider or clinical acceptance unless explicitly said.

| Area | Classification | Concrete evidence / verified scope | Remaining limitation | Action now |
| --- | --- | --- | --- | --- |
| A. Frontend visuals | FROZEN / DO NOT REVISIT | Owner-approved checkpoint `5c3a9e5`; commit changes only landing CSS; NP has older browser evidence | No new visual certification or exact-checkpoint browser result claimed | None; preserve visuals and dirty screenshots |
| B. Authentication | VERIFIED | AUTH account/password/login foundation; P2c reran auth access/boundary selection within 220 passes | No email verification/recovery or public rollout approval | None |
| C. Sessions | VERIFIED | AUTH hashed bearer tokens, expiry/idle/revocation; P2c denial/boundary regressions; PG historical session tests | Hosted cookie/proxy behavior unverified; admitted work may finish after logout | None |
| D. CSRF | VERIFIED | AUTH exact Origin/Referer + synchronizer token; P2a and P2c pre-body mutation checks in ACCOUNT/Demo | Hosted proxy forwarding not established | None |
| E. Ownership/isolation | VERIFIED | AUTH direct owner-scoped queries, uniform foreign-case denial, no child work; P2c rerun | Not proof of every dual-owner history combination or constant-time DB execution | None |
| F. Demo isolation | VERIFIED | Visitor-scoped namespace, separate cookies, Mock-only restrictions; P2c ACCOUNT/Demo tests | Local Demo does not authorize hosted staging processing | None |
| G. Case creation/update | VERIFIED | P0/P1a version/no-op/clear assertions; P2c regression evidence | No broader new product validation contract | None |
| H. Intake validation | VERIFIED | P1a: explicit empty recommendation/context persisted; URL-encoded/multipart, 47 focused cases in 82-pass selection | Empty question is rejected on creation but no-op on PATCH; new limits/normalization need policy | None |
| I. Dossier revisioning | VERIFIED | P2c six new ACCOUNT/Demo rollback, full-row preservation and ORM update/delete guard cases; PG earlier concurrent revisions | Latest P2 evidence is SQLite, not a new PG run | None |
| J. Concurrent case-text updates | VERIFIED | `7e2855f` locks and refreshes before comparison; P1a 82-pass and P2a 211-pass selections include P0 concurrency | Controlled SQLite overlap; not newly rerun in P2c/P2d or independently accepted on PG after this fix | None |
| K. Artifact ingestion | VERIFIED | P2a/P2b additive IDs/bytes, same-case hash dedup, validation and exclusive creation; P2c rerun | Duplicate audit may append; missing-file dedup is not repair; exhaustive decoder attacks not tested | None |
| L. Upload resource boundaries | PARTIALLY VERIFIED | P2a 54 cases; P2c rerun: each part retains at most configured limit+1; all spools close | Total traffic/time/concurrency/header budgets not bounded by this fix; Windows long-path acceptance remains partial | None; do not widen the fix |
| M. Filesystem/DB consistency | PARTIALLY VERIFIED | P2b 23 cases within 173 passes; P2c rerun: prior bytes/rows survive injected DB/storage failures and retries | Files precede commit; complete/partial orphans allowed; no fsync/cross-store transaction/power-loss proof | None |
| N. Processing lifecycle | VERIFIED | P1b and P2c RUNNING reconciliation, terminal results, current authority; existing interrupted-run characterization | Abandoned RUNNING can block indefinitely; no kill/recovery acceptance | None |
| O. Retry behavior | VERIFIED | P1b distinct failed attempts, successful retry, unchanged success reuse without new history; P2c rerun | No automatic replay/force-rerun promise; browser reload during durable failure/running only partially verified | None |
| P. Assessment freshness | VERIFIED | `ea42a38`: latest successful ACTIVE matching effective input hash; P2c freshness suite included in 220 passes | Already-open idle tabs are not continuously synchronized | None |
| Q. Report freshness/current authority | VERIFIED | P0 shared filters plus case/snapshot version checks; P1b/P2c stale result unavailable and later success current | No newly promised public historical-report endpoint; print/browser coverage from earlier gates | None |
| R. Historical snapshots/reports | VERIFIED | P1b full-column before/after failure/retry comparisons; P2b upload rollback; P2c dossier failure/edit preservation | DB retention is distinct from current authority and backup restoration | None |
| S. Immutable provenance/history | VERIFIED | P2c reruns P0 source-distinct provenance and ORM guards; adds dossier guards | ORM enforcement can be bypassed by privileged SQL; run authority and artifact derived metadata legitimately mutate | None |
| T. PDF/report behavior | PARTIALLY VERIFIED | NP synthetic three-page PDF/API snapshot identity and page bounds; P1b six history/print freshness browser checks | No current cross-browser/layout rerun, hosted print acceptance or clinical correctness; server PDFs are not durable stored artifacts | None; visuals frozen |
| U. Offline Mock pipeline | VERIFIED | P1b/P2a/P2b/P2c synthetic deterministic pipeline and retry/history executions | Mock output establishes software behavior only, never medical accuracy | None |
| V. Live OpenRouter/provider acceptance | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | OPS explicitly carries real-provider gate as deferred/blocked; offline adapter/fail-closed tests exist | Successful live acceptance NOT VERIFIED; credentials/model/budget/transmission approval required | None; no calls or credential work |
| W. Knowledge pack | PARTIALLY VERIFIED | G1/NP versioned pack, deterministic restrictions; P0 freshness and STAGE reviewed-pack refusal | Seeded DEVELOPMENT pack NOT_CLINICALLY_VALIDATED; no reviewed clinical pack established | None; retain fail-closed behavior |
| X. PostgreSQL behavior | PARTIALLY VERIFIED | PG private 16.15 runtime: auth, migrations, dossier concurrency, processing/restart/history; 50 focused/711 broad passes; 7.3 later PG-enabled evidence | Historical acceptance predates recent audit fixes; P2 gates use SQLite; arbitrary migration histories and populated authoritative snapshots across predecessor upgrades remain unverified | None; revalidate only in authorized PG gate |
| Y. Hosted PostgreSQL | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | STAGE specifies dedicated synthetic PG16 and separate migration/preflight | Hosted schema, connectivity, account access and actual deployed state NOT VERIFIED | None |
| Z. Hosted durable file storage | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | OPS paired identity contract; STAGE explicitly permits only ephemeral infrastructure rehearsal | Durable mount/redeploy preservation NOT VERIFIED; provider/cost/access approval needed | None |
| AA. Deployment | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | OPS/STAGE local packaging/preflight/routing evidence; 7.5E local 309-pass selection and 835-pass broad run | Hosted integration, clean image lifecycle and access protection not acceptance-proven | None; do not deploy |
| AB. DNS/TLS | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | OPS finite peers; 7.5E explicit staging-only boundary tested locally | Actual origin, certificates, ingress trust and Netlify/Render cookie forwarding NOT VERIFIED | None |
| AC. Backup/recovery | NOT VERIFIED | OPS defines paired DB/artifact restoration acceptance; explicitly not executed | No paired restore, retention/encryption/RPO/RTO or disaster-recovery acceptance | None; blocked on policy and target |
| AD. Real-patient/privacy readiness | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | G1/NP synthetic-only scope; minimization/redaction tests are technical evidence | No real-data permission, transmission/retention/legal/privacy approval | None; synthetic only |
| AE. Clinical approval | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | G1 explicitly not clinical-ready; NP hypotheses are qualitative, not diagnosis | Clinician review/validated pack and real acceptance unavailable | None |
| AF. Abandoned RUNNING recovery | AMBIGUOUS / POLICY REQUIRED | P1b and OPS preserve unresolved attempts and block replay | Lease/cancel/timeout/reconciliation semantics not approved | None; do not reset rows |
| AG. Orphan repair/retention | AMBIGUOUS / POLICY REQUIRED | P2b characterizes complete/partial orphans and missing-file duplicate reuse | No safe automatic removal/repair/retention contract | None; never silently delete evidence |
| AH. Aggregate upload/request limits | AMBIGUOUS / POLICY REQUIRED | P2a only per-file retained spool bound; OPS delegates ingress budgets | Request bytes/time/headers/quotas/concurrent resource limits not numerically approved | None; no arbitrary thresholds |
| AI. Email/account recovery | BLOCKED / OWNER OR INFRASTRUCTURE REQUIRED | AUTH records email_verified state but no verification-delivery/recovery flow | Delivery access, identity/security policy and product authorization needed | None; do not add reset flows |
| AJ. Safety/provenance architecture | FROZEN / DO NOT REVISIT | G1 modular monolith; NP deterministic restrictions, independent sources, shared immutable snapshot | Safety behavior tests are not clinical validation | None; no rewrite |
| AK. Packaging/liveness | PARTIALLY VERIFIED | OPS launcher/preflight/read-only checks and local process rehearsal | Health is liveness, not dependency readiness or proof of storage identity; no clean image/host acceptance | None |

## Compact audit timeline

Counts below belong to their source handoffs. Overlapping selections must not be
summed into a unique-test total. P2c's 9 + 220 are two recorded selections, not a
new run performed here.

| Commit | Problem/gate and change | Change type | Recorded verification | Caveat |
| --- | --- | --- | --- | --- |
| `5c3a9e5` | Final workspace visual polish; landing CSS only | Frontend production | Owner-approved/frozen checkpoint; NP holds earlier browser/PDF evidence | No test result attached to this exact commit inferred |
| `ea42a38` | Assessments could outlive current inputs/attempt; share latest-success/ACTIVE/hash filters with report reads | Production + tests | P0 freshness tests; later P2c 220-pass selection includes them | No dedicated P0 handoff/original count found; SQLite evidence |
| `7e2855f` | Stale pre-lock case object could lose concurrent text/version state; lock and refresh before mutation | Production + tests | P0 controlled-overlap/rollback tests; P1a 82-pass and P2a 211-pass selections include them | No dedicated P0 handoff; no new PG acceptance of this fix |
| `c557222` | FastAPI empty-form defaults swallowed explicit clears; preserve empty recommendation/ACCOUNT context | Production + tests/docs | P1a expanded pre-fix 8 failed/40 passed; final 82 passed plus 7 auth PATCH passes | Empty-question policy unchanged; Demo context remains server-owned |
| `c194f40` | Verify processing/failure/retry/reuse and browser handling; no demonstrated production defect | Tests/docs only | P1b four new API cases passed; initial 68 passes/7 fixture errors, isolated-cache follow-up 36 passes; six new browser cases passed | Initial fixture errors were not a clean run; durable RUNNING/FAILED reload and recovery limited |
| `d7dfc8e` | Multipart spooled arbitrary rejected bytes; unfinished spool not deterministically closed; bound each part to limit+1 and close all | Production + tests/docs | P2a Linux pre-fix 6 failed/42 passed; post-fix 48 passed; final focused 54; broader 211 | Not aggregate request protection; Windows long-path uncertainty retained |
| `5d02f92` | Characterize storage/DB ordering and protect prior bytes/history across failures/retry | Tests/docs only | P2b final 173 passed including 23 new consistency cases | Allowed orphans and absent automatic repair are not newly fixed defects |
| `53e3a8f` | Fill dossier full-history/commit-failure and direct update/delete guard gaps; avoid duplicate fixture stacks | Tests/docs only | P2c 9 focused passes (six new), 220 relevant passes; three existing warnings per command | SQLite/Mock; P0 concurrency inspected but not rerun at P2c |

No new production defect was found in P2b/P2c, and no bug hunt was conducted here.
Recent production fixes are freshness, concurrent text updates, explicit empty
intake handling and bounded multipart cleanup. Test-only gates must not be described
as production remediations.

## Safe resume runbook

Start with read-only identity/status checks. The expected checkpoint for this
handoff is `53e3a8f`; a future legitimate commit may advance it. Investigate a mismatch
rather than checking out/resetting over an existing workspace.

```bash
cd /mnt/c/Users/Admin/Desktop/dandoonjan
conda activate dandoonjan-wsl
git branch --show-current
git rev-parse --short HEAD
git status --short
git status --short -uall
git diff --name-only
git diff --cached --name-only
```

Read this runbook, AGENTS.md and the relevant gate handoff before changes. Record
and hash the current dirty/untracked baseline again: the old `/tmp` manifest is
session evidence, not a permanent backup. Preserve unknown files byte-for-byte.
The known workspace has three modified landing PNGs plus many untracked temporary
PDF/browser/UI artifacts, an archive, frontend-demo, tools and verification scripts.
Untracked does not mean disposable. Do not casually use `git add .`, `git clean`,
`git reset --hard`, broad deletion, or staging that captures unrelated evidence.
This gate authorizes no staging/commit/push; any later authorized commit must select
explicit task paths only after review.

When a local application is actually needed, use the existing Python 3.11 environment
and an approved **synthetic local** configuration/database/storage. Confirm local
Mock/no-live operation and applicable exact local auth origin without exposing or
copying credentials. Do not let an inherited live-provider setting authorize calls.
Do not create/migrate a normal database, enable the Render TLS boundary on local HTTP,
or overwrite a workspace .env merely to get the server running.

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-config app/logging.json
```

This requested bind listens on available interfaces; it is a local development
command, not deployment approval. If Windows requires the WSL address, obtain it
again with `hostname -I` in WSL and select the current reachable interface address.
An old screenshot/terminal WSL IP is not authoritative. Use the actual browser origin
in the approved local auth-origin configuration; do not broaden CORS/CSRF to mask
an origin mismatch. No server or IP lookup was needed in this documentation gate.

### Focused testing, only when the next change warrants it

Use separate bytecode caches across WSL/Windows. Select the smallest relevant
suite first; broaden for changed dependencies or observed failures, not automatically.
P2c's exact commands and environment caveat are in its handoff. Example focused
preservation invocation using the established disposable fixtures:

```bash
PYTHONPYCACHEPREFIX=/tmp/dandoonjan-resume-pycache python -m pytest tests/regression_p2/test_preservation_invariants.py tests/next_phase/test_dossier.py -q --tb=short
```

If workspace dotenv/inherited provider settings are unsuitable, the existing offline
launcher disables dotenv, sets disposable SQLite/storage and Mock/no-key defaults,
and installs an HTTP transport tripwire. Use file/directory arguments as below:

```bash
PYTHONPYCACHEPREFIX=/tmp/dandoonjan-resume-pycache python verification/run_phase6_offline.py tests/regression_p2/test_preservation_invariants.py -q --tb=short
```

That launcher command is an inspected existing mechanism, **not newly executed or
certified in this gate**. Do not treat it as a live-provider acceptance tool.
If Linux TestClient stalls in the sandbox, interrupt/bound the attempt, record that
it produced no result, and request permission before focused offline execution
outside the sandbox. Prior approval is not an invitation to run unrelated work.

| Change area | Start with existing evidence/tests |
| --- | --- |
| Freshness/current report | `tests/regression_p0/test_assessment_freshness.py`, relevant `test_api_state.py` |
| Text concurrency | `tests/regression_p0/test_case_text_concurrency.py` |
| Intake | `tests/regression_p1/test_intake_validation.py` |
| Processing/retry | `tests/regression_p1/test_processing_retry.py`; relevant next-phase concurrency tests |
| Upload parser/limits | `tests/regression_p2/test_upload_resource_boundaries.py`; relevant upload-management tests |
| Storage/DB | `tests/regression_p2/test_filesystem_db_consistency.py` |
| Dossier/history | `tests/regression_p2/test_preservation_invariants.py`, `tests/next_phase/test_dossier.py` |
| Ownership/CSRF/Demo | Relevant cases in `tests/auth_gate2/test_access.py`, `test_boundary.py` |

For documentation-only changes, repository/link/whitespace checks suffice. Do not
run hundreds of tests to reconfirm old counts. Never remove regression assertions
or loosen application safeguards to make an environment mismatch pass. PostgreSQL
requires a separately approved disposable target and its own runtime evidence;
never reuse the historical temporary socket path from PG as if it still exists.
No blanket migration or full-suite command is part of routine resume.

## Do not reopen completed work without new evidence

Approved frontend visuals, auth foundation, ownership/CSRF/Demo boundaries,
dossier versioning, additive evidence management, deterministic offline Mock,
report/snapshot freshness, preservation regressions, and the P2 upload fix are
complete within their documented scopes. Keep their tests and useful history.

This is not a claim that bugs cannot exist. A reproducible defect, changed dependency,
new supported environment or explicitly approved requirement can justify a scoped
new gate. Without that trigger, do not repeat the broad audit, create redundant
fixtures for coverage percentages, redesign the frontend, replace the architecture,
reset historical runs, delete orphans or rerun successful live requests. Do not
reopen settled Gate 1 decisions or turn missing deployment access into local busywork.

## Blocked work and decision register

All items below are **postponed now**. Roles identify required decisions/access,
not a request to contact anyone. Work requiring Mehdi remains deferred. No email,
provider, hosting or account action is authorized by this runbook.

| Item | Why blocked or ambiguous | Needed from owner/operator | Engineering gate only afterward |
| --- | --- | --- | --- |
| Render/Netlify integration | Local templates/source checks do not verify real routing, cold starts, cookies or protection of both origins | Mehdi/account administrator and owner authorization, actual origins/entitlements, exposure plan | Inspect actual configuration, validate platform constraints, then separately authorize synthetic hosted acceptance |
| DNS/TLS/ingress | No verified actual trust boundary/certificates/forwarding | Domain/platform operator, approved exact origins and ingress boundary | Verify TLS, trusted proxy behavior, secure cookie/Origin handling; use 7.5E only for its explicit staging contract |
| Hosted PostgreSQL | No approved target/access/state established by local evidence | Infrastructure owner, dedicated synthetic PG16 access and migration authorization | Inspect schema/history, rehearse populated migration, separate migration/preflight, then hosted runtime checks; unknown deployed state is a Stop Condition |
| Durable artifact storage | Ephemeral staging is explicitly not preservation acceptance | Owner cost/storage choice and operator mount/access/capacity contract | Verify identity/permissions, prior bytes across restart/redeploy, DB/file consistency; never hide lost files by deleting rows |
| Backups/disaster recovery | Paired restore unexecuted; retention/encryption/recovery objectives undecided | Owner privacy/retention/RPO/RTO and infrastructure backup access | Quiescent paired DB/artifact backup; restore to disposable target; verify hashes, provenance, history/current authority and unresolved runs |
| Live provider | Real-provider gate deferred; offline adapter behavior does not prove live model behavior | Explicit owner authorization, approved model/version, budget/transmission terms, owner-provisioned credential | Bounded synthetic acceptance with sanitized evidence and no implicit retries/fallback; no secret discovery |
| Clinical pack/acceptance | Seeded pack is not clinically validated | Authorized clinical reviewer and approved versioned pack | Validate pack provenance/version, enforce reviewed gate, perform separately approved clinical acceptance |
| Real-patient/privacy | Synthetic-only approved scope | Owner and appropriate privacy/legal/clinical decision makers; permitted data and handling/retention terms | Review minimization, access, logging, transmission and deletion/retention implementation before any real data |
| Email/recovery | No verified delivery or recovery/verification flow | Owner product/security policy and approved email infrastructure | Implement scoped verification/recovery with session invalidation and abuse protections; test synthetic delivery first |
| Abandoned RUNNING | No approved lease/timeout/cancel/reconcile semantics; ambiguous external work may have executed | Owner-approved recovery semantics | Preserve attempt audit/history; design bounded concurrency/recovery and failure tests before production edits |
| Orphan/missing-file repair | DB-only dedup does not restore missing bytes; deletion could destroy evidence | Owner retention/repair policy and actual storage inventory/access | Read-only inventory first; design provenance-preserving reconciliation and dry-run review before mutations |
| Aggregate request/upload limits | No approved total bytes/time/header/concurrency/quotas | Owner/operator capacity and UX constraints | Implement/retest chosen ingress/application limits without weakening per-file spool guarantees |
| Product-scope additions | Empty-question clearing, automatic polling/retry, force-rerun and other additions not settled by existing contracts | Product Owner decision and explicit scope | Separate behavior/API contract gate, regression-first; no speculative expansion |

STAGE's initial ephemeral infrastructure rehearsal intentionally excludes durable
uploads, restart evidence preservation, reviewed clinical processing and real data.
It cannot be relabeled production readiness. The unreviewed-pack refusal remains
expected, including when a staging health/auth probe succeeds. Do not copy old
platform commercial limits without verifying them in the later authorized planning
gate. No current external availability, price or account status is asserted here.

## Next legitimate gates

### NOW, WITHOUT MEHDI / HOSTED ACCESS

No meaningful remaining local implementation gate is evidenced by this completed
audit. Read/review this handoff and stop. A future concrete regression can open a
small reproduction-first fix gate; it is not authorization for another broad bug
hunt. No production refactor, frontend redesign, redundant test suite or full-suite
rerun is necessary merely because deployment is blocked.

### LATER, AFTER OWNER/INFRASTRUCTURE ACCESS

1. Authorized infrastructure/access and policy planning: resolve actual origins,
   environment protection, database/storage identity, budgets and acceptance scope.
2. Refresh PostgreSQL acceptance on the intended disposable environment for the
   current revision, including recent audit fixes, before any hosted schema action.
3. Separate synthetic infrastructure deployment gate: inspect target state, migrate
   only with approval, preflight, verify TLS/routing/auth/session/CSRF/isolation and
   expected processing refusal. This does not require or grant clinical acceptance.
4. Durable storage and paired backup/restore acceptance before any durability claim.
   Recovery-policy implementation is a separate gate after decisions, not a silent
   addition to hosting work.
5. Independently authorized live-provider acceptance and clinical pack approval;
   real-patient/privacy acceptance is another explicit prerequisite for real data.
6. Email/recovery or other product additions only if selected and authorized by the
   owner; they are not automatic requirements of this documentation gate.

These are conditional gates, not scheduled work or evidence they have passed.

## This gate's repository evidence and validation

Read the source index above, targeted phase-7/auth/runtime sections, root README,
regression P0/P1/P2 test definitions and relevant fixture/assertion sections.
Inspected `git log` and `git show` for all eight timeline commits, including the
production diffs for both recent P0 fixes. No unrelated giant tree was audited.

Before editing, branch and full HEAD matched the requested checkpoint. Complete
baseline status and SHA-256 hashes for 988 pre-existing modified/untracked files
were saved to `/tmp/dandoonjan-p2-final-runbook-baseline/status.txt` and
`hashes.json`. These are temporary local evidence, not committed artifacts.

Only task file: `docs/handoff/final-audit-readiness-runbook.md` (new).
Production/frontend/test/fixture changes: **NONE**. No runtime tests were necessary
for this consolidation; prior results were not rerun. No staging, commit, push,
deployment, migration, credentials, live/paid provider or external account work.

Final validation: branch and full HEAD unchanged; **988/988 baseline file hashes
match**, every original status entry remains, and only this runbook is newly
untracked. Staged diff is empty. `git diff --check` passed; an explicit trailing
whitespace check for this untracked Markdown file passed. All 21 relative source
links resolve; readiness rows A–AK and paired code fences were checked. All prior
dirty/untracked files were preserved. Nothing was staged, committed, pushed or
deployed. Stop at this documentation checkpoint.
