"""Model Gateway. The only path from domain modules to an AI provider.

Production fails closed on missing provider configuration, provider failures, and
invalid responses. Development/test retain the existing recorded Mock fallback.
Fallback never applies to assessment, gaps, safety policy, or case state.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.providers import MockProvider, OpenRouterProvider, content_hash
from app.ai.prompts import Prompt, get_prompt, render_prompt
from app.ai.schemas import SCHEMA_VERSIONS
from app.config import get_settings
from app.domain.models import ModelRun
from app.errors import ExtractionValidationError, ModelProviderError, ProviderUnavailableError
from app.safe_logging import safe_error_code

T = TypeVar("T", bound=BaseModel)

REAL_PROVIDER_NAMES = {"openrouter"}


class ModelGateway:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.fallback = MockProvider()
        if settings.environment == "production" and settings.ai_provider not in REAL_PROVIDER_NAMES:
            raise ProviderUnavailableError("production requires a configured real provider")
        if settings.ai_provider == "openrouter":
            try:
                self.provider = OpenRouterProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.ai_model_name)
            except ProviderUnavailableError:
                if settings.environment == "production":
                    raise
                # no key configured -> run fully in mock (DEMO) mode
                self.provider = self.fallback
        else:
            self.provider = self.fallback

    @property
    def provider_mode(self) -> str:
        """Mode the configuration intends: AI when a real provider is active."""
        return "AI" if self.provider.name in REAL_PROVIDER_NAMES else "DEMO"

    def run(self, prompt_id: str, schema: type[T], content: str,
        temperature: float = 0.0) -> tuple[T, ModelRun]:
        prompt: Prompt = get_prompt(prompt_id)
        rendered = render_prompt(prompt, content=content)
        input_hash = content_hash(rendered)
        settings = get_settings()

        provider = self.provider
        run = ModelRun(
            provider=provider.name, model=settings.ai_model_name,
            prompt_id=prompt.prompt_id, prompt_version=prompt.version,
            schema_version=SCHEMA_VERSIONS[_schema_key(schema)],
            temperature=temperature, input_hash=input_hash, status="RUNNING",
        )
        self.db.add(run)
        self.db.flush()

        fallback_reason: str | None = None
        try:
            raw = self._call_raw(provider, prompt, rendered)
            validated = self._validate_schema(schema, raw)
        except (ProviderUnavailableError, ValidationError) as exc:
            if settings.environment == "production" or provider.name not in REAL_PROVIDER_NAMES:
                # Fail closed in production; preserve mock/test schema-firewall behavior.
                run.status = "FAILED"
                run.error = safe_error_code(exc)
                raise ExtractionValidationError("AI output validation failed") from None
            # VISIBLE fallback to the deterministic worker (AI worker boundary only)
            fallback_reason = safe_error_code(exc)
            raw = self._call_raw(self.fallback, prompt, rendered)
            validated = self._validate_schema(schema, raw)  # mock output must validate
            run.provider = self.fallback.name

        run.status = "SUCCEEDED"
        run.error = f"fallback: {fallback_reason}" if fallback_reason else None
        run.output_hash = hashlib.sha256(
            json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
        run.validated_output = json.loads(validated.model_dump_json())
        self.db.flush()
        return validated, run

    def _call_raw(self, provider, prompt: Prompt, rendered: str) -> dict[str, Any]:
        """Provider call + raw-shape guard; environment policy is enforced by run."""
        try:
            raw = provider.run(prompt, rendered, {})
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError("provider failure") from None
        if not isinstance(raw, dict):
            raise ProviderUnavailableError("provider returned non-object output")
        return raw

    def _validate_schema(self, schema: type[T], raw: dict[str, Any]) -> T:
        # Schema firewall: invalid output NEVER enters core state.
        return schema.model_validate(raw)


def _schema_key(schema: type[BaseModel]) -> str:
    name = schema.__name__.lower().replace("output", "")
    return name if name in SCHEMA_VERSIONS else "classification"
