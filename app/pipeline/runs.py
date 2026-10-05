"""ProcessingRun helper: pipeline operation state, separate from Case state.

Run identity = (case, module, input_hash including module_version, attempt).
Pipeline attempt allocation uses max(previous attempts) + 1 only while holding
the Case admission lock. Module allocation belongs to the single admitted
pipeline. Failed and successful runs may coexist; unresolved runs block admission.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.domain.enums import DerivationStatus, ProcessingRunStatus, RunAuthority
from app.domain.models import Case, ModelRun, ProcessingRun, public_id, utcnow
from app.safe_logging import safe_error_code


def lock_case(db: Session, case_id: int):
    """Short DB coordination transaction; caller commits before any provider I/O.

    SQLite reserves the writer without relying on ignored FOR UPDATE. PostgreSQL
    locks only this Case. This also works inside an existing write transaction.
    Never change input/version/timestamps to acquire the lock.
    """
    if db.get_bind().dialect.name == 'sqlite':
        db.execute(text('UPDATE cases SET id=id WHERE id=:case_id'), {'case_id': case_id})
    else:
        db.query(Case.id).filter(Case.id == case_id).with_for_update(of=Case).one()


def next_attempt(db: Session, case_id: int, module: str, input_hash: str) -> int:
    # Pipeline allocation happens under lock_case; module allocation is owned by
    # that single durable RUNNING pipeline claim, never competing requests.
    max_attempt = (db.query(func.max(ProcessingRun.attempt))
                   .filter(ProcessingRun.case_id == case_id,
                           ProcessingRun.module == module,
                           ProcessingRun.input_hash == input_hash)
                   .scalar())
    return (max_attempt or 0) + 1


@contextmanager
def processing_run(db: Session, case, module: str, input_obj,
                   module_version: str = "", derivation_run_id: int | None = None):
    prior_model_ids = set(db.info.get('model_run_ids', ()))
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
    db.commit()  # No SQLite write reservation spans provider execution.
    try:
        yield run
        run.status = ProcessingRunStatus.SUCCEEDED
    except Exception as exc:
        db.rollback()  # Discard this stage's unfinished candidates.
        owned_ids = set(db.info.get('model_run_ids', ())) - prior_model_ids
        if owned_ids:
            for model in db.query(ModelRun).filter(ModelRun.id.in_(owned_ids),
                                                   ModelRun.status == 'RUNNING').all():
                model.status = 'FAILED'
                model.error = safe_error_code(exc)
        run.status = ProcessingRunStatus.FAILED
        run.error = safe_error_code(exc)
        run.finished_at = utcnow()
        db.commit()  # Durable failure, never leave a caught failure RUNNING.
        raise
    finally:
        run.finished_at = utcnow()
        db.flush()
