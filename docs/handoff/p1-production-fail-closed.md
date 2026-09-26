# Approved production fail-closed prerequisite

Date: 2026-09-26. Branch: `agent/sadeghi-p1-core`.
Base: `b36036962a14397ebca0c6f1b7c23001409c93b3`.
The Product Owner explicitly approved resolving the PO-06 contradiction before P1.

## Change and evidence

The gateway now raises the existing controlled provider error when production
selects Mock/an unsupported provider or OpenRouter lacks a key. Production provider
exceptions, non-object responses and schema-invalid responses enter the existing
failed-run/schema-firewall error path without invoking Mock. Valid provider output
is unchanged. Development/test fallback remains unchanged. No credentials, live
services, architecture, schema, pipeline, safety policy, or P0 tests changed.

## Executed checks

Python: existing Windows CPython 3.11.3 at
`/mnt/c/Users/Admin/AppData/Local/Temp/dandoonjan-p0-regression-venv/Scripts/python.exe`.
All provider substitutes are offline synthetic classes.

- Prior baseline: `python -m pytest tests -q --tb=short -rfs`:
  136 passed, 2 skipped, 4 warnings in 25.80s.
- Before correction: `python -m pytest tests/regression_p1/test_production_provider.py -q --tb=short`:
  5 failed, 10 passed in 0.71s. All five production defects reproduced;
  development/test controls passed.
- After correction, same focused command (with four additional controls):
  **19 passed in 0.46s**.
- Full: `python -m pytest tests -q --tb=short -rfs`:
  **155 passed, 2 skipped, 4 warnings in 24.85s**.
- `git diff --check`: passed.

VERIFIED WORKING: bounded offline gateway behavior above and all executable P0
regressions. The two unchanged Windows directory-symlink tests skip with WinError
1314. Warnings remain Starlette/httpx, AnyIO and FastAPI startup deprecations.

NOT VERIFIED: live provider, hosted production, PostgreSQL, Docker and browser/UI.
The checked-in Render template still selects production plus Mock; processing now
intentionally fails closed with that configuration. Deployment configuration is
not changed here. A local controlled demo must explicitly use development/test
with Mock; this is not production/clinical readiness. Existing protected P0
semantics and deterministic tests remain intact within tested scope.

Next: continue the authorized Issue #1 P1 checkpoint after this separate commit.
