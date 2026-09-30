"""Content-free operational diagnostics; no exception text or log arguments."""
import json
import logging
import logging.config
from pathlib import Path


def safe_error_code(exc: Exception) -> str:
    from app import errors
    if isinstance(exc, errors.ProviderUnavailableError):
        return "REAL_PROVIDER_" + exc.category.upper()
    for cls in vars(errors).values():
        if isinstance(cls, type) and issubclass(cls, errors.DandoonjanError):
            if type(exc) is cls:
                return cls.code
    from pydantic import ValidationError
    if isinstance(exc, ValidationError):
        return "SCHEMA_VALIDATION_FAILED"
    return "INTERNAL_ERROR"


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Libraries may log URLs, bodies, SQL parameters and exception chains.
        # Allowlist output fields instead of trying to redact arbitrary content.
        event = "runtime_event"
        fields = {}
        if record.name == "uvicorn.access":
            event = "http_response"
            if isinstance(record.args, tuple) and len(record.args) == 5:
                status = record.args[4]
                if type(status) is int and 100 <= status <= 599:
                    fields["status"] = status
        elif record.exc_info:
            event = "runtime_failure"
        level = record.levelname if record.levelname in {
            "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "UNKNOWN"
        return json.dumps({"level": level, "event": event, **fields})


def configure_logging() -> None:
    config = Path(__file__).with_name("logging.json")
    logging.config.dictConfig(json.loads(config.read_text(encoding="utf-8")))
