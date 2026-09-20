"""ProcessingRun helper: pipeline operation state, separate from Case state.

Run identity = (case, module, input_hash including module_version, attempt).
attempt = max(previous attempts for the same identity) + 1 — retries are safe and
never raise IntegrityError (D1). Failed and successful runs may coexist.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.enums import DerivationStatus, ProcessingRunStatus, RunAuthority
from app.domain.models import ProcessingRun, public_id, utcnow


def next_attempt(db: Session, case_id: int, module: str, input_hash: str) -> int:
    max_attempt = (db.query(func.max(ProcessingRun.attempt))
                   .filter(ProcessingRun.case_id == case_id,
                           ProcessingRun.module == module,
                           ProcessingRun.input_hash == input_hash)
                   .scalar())
    return (max_attempt or 0) + 1


@contextmanager
def processing_run(db: Session, case, module: str, input_obj,
                   module_version: str = "", derivation_run_id: int | None = None):
    input_hash = hashlib.sha256(
        json.dumps({"module": module, "module_version": module_version,
                    "input": input_obj},
                   sort_keys=True, default=str).encode()).hexdigest()[:64]
    run = ProcessingRun(
        public_id=public_id("RUN"), case_id=case.id, module=module,
        status=ProcessingRunStatus.RUNNING, attempt=next_attempt(db, case.id, module,
                                                                 input_hash),
        input_hash=input_hash,
        input_version=f"case-v{case.version}/{module_version}",
        authority=RunAuthority.NON_AUTHORITATIVE,
        started_at=utcnow(),
    )
    if derivation_run_id is not None:
        run.derivation_run_id = derivation_run_id
    db.add(run)
    db.flush()
    try:
        yield run
        run.status = ProcessingRunStatus.SUCCEEDED
    except Exception as exc:
        run.status = ProcessingRunStatus.FAILED
        run.error = str(exc)[:2000]
        raise
    finally:
        run.finished_at = utcnow()
        db.flush()
