import json
import logging
import sys
import subprocess
import os

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest

from app.db import make_engine
from app.pipeline.runs import processing_run
from app.domain.models import ProcessingRun
from app.safe_logging import SafeFormatter

MARKER = "SYNTHETIC_PRIVATE_LOG_CANARY"


@pytest.mark.parametrize("name", ["uvicorn.error", "httpx", "sqlalchemy.engine", "application"])
def test_formatter_omits_messages_arguments_and_tracebacks(name):
    try:
        raise ValueError(MARKER)
    except ValueError:
        record = logging.LogRecord(name, logging.ERROR, __file__, 1,
            "payload %s", (MARKER,), sys.exc_info())
    result = SafeFormatter().format(record)
    assert MARKER not in result and "payload" not in result
    assert json.loads(result) == {"level": "ERROR", "event": "runtime_failure"}


def test_access_log_keeps_status_without_url_or_client():
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', (MARKER, "GET", "/?token=" + MARKER, "1.1", 422), None)
    assert json.loads(SafeFormatter().format(record)) == {
        "level": "INFO", "event": "http_response", "status": 422}


def test_processing_failure_diagnostic_excludes_content(db, case):
    with pytest.raises(RuntimeError):
        with processing_run(db, case, "synthetic", {}):
            raise RuntimeError(MARKER)
    assert db.query(ProcessingRun).one().error == "INTERNAL_ERROR"


def test_sql_parameters_hidden_in_engine_exceptions():
    engine = make_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE demo (value TEXT UNIQUE)"))
            conn.execute(text("INSERT INTO demo VALUES (:value)"), {"value": MARKER})
            with pytest.raises(IntegrityError) as caught:
                conn.execute(text("INSERT INTO demo VALUES (:value)"), {"value": MARKER})
            assert MARKER not in str(caught.value)
    finally:
        engine.dispose()


def test_invalid_environment_does_not_echo_input_in_startup_errors():
    env = {**os.environ, "DJ_CORS_ORIGINS": json.dumps([MARKER]),
        "DJ_OPENROUTER_API_KEY": "", "DJ_OPENAI_API_KEY": ""}
    result = subprocess.run([sys.executable, "-c", "from app.config import Settings; Settings()"],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert MARKER not in result.stdout + result.stderr
