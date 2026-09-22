# P0 Docker / Deployment Packaging

- Starting commit: `894b1447bb469e79564a12885b31503d6d9e93c6`
- Root cause: the Dockerfile copied application and migration files but omitted the repository `frontend/` directory, while `app.main` serves runtime assets from `/app/frontend`.
- Fix: added `COPY frontend ./frontend` to the single-stage Python 3.11 image.

## Verification

- Focused packaging regression: **1 passed**.
- Relevant API/static tests: **12 passed**.
- Existing suite excluding regression tests: **109 passed**.
- Full combined suite: **136 passed, 2 skipped, 0 failed**.
- Known skips are Windows symlink privilege skips.
- Docker CLI is unavailable in this environment, so an actual image build and runtime smoke check remain NOT VERIFIED.

All currently locked P0 regression failures are resolved by the combined suite.
