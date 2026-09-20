"""Model Gateway. The only path from domain modules to an AI provider.

Responsibilities: provider selection, prompt version, schema validation, model-run
recording, error mapping, VISIBLE provider fallback (V0.2 Q5):
- If the real provider (openrouter) is unavailable OR returns schema-invalid output,
  the gateway falls back to MockProvider for that call, records the fallback reason
  in ModelRun metadata, and marks the model run provider as "mock" — the UI badge
  and snapshot therefore show DEMO mode. Never silently.
- Fallback applies ONLY at the AI worker boundary (classification/extraction/
  claim candidates). Assessment, gaps, safety, and case state never get "mocked".
- Fallback does NOT apply when the active provider is already mock or a
  test-injected provider: their failures propagate (schema firewall semantics).
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

T = TypeVar("T", bound=BaseModel)

REAL_PROVIDER_NAMES = {"openrouter"}


class ModelGateway:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.fallback = MockProvider()
        if settings.ai_provider == "openrouter":
            try:
                self.provider = OpenRouterProvider(
                    api_key=settings.openrouter_api_key,
                    model=settings.ai_model_name)
            except ProviderUnavailableError:
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
            if provider.name not in REAL_PROVIDER_NAMES:
                # mock/test provider failed: propagate (schema firewall semantics)
                run.status = "FAILED"
                run.error = f"{type(exc).__name__}: {str(exc)[:500]}"
                raise ExtractionValidationError(
                    f"AI output failed for {prompt_id}: {exc}") from exc
            # VISIBLE fallback to the deterministic worker (AI worker boundary only)
            fallback_reason = f"{type(exc).__name__}: {str(exc)[:300]}"
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
        """Provider call + raw-shape guard. ProviderUnavailableError => fallback."""
        try:
            raw = provider.run(prompt, rendered, {})
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(f"provider failure: {exc}") from exc
        if not isinstance(raw, dict):
            raise ProviderUnavailableError("provider returned non-object output")
        return raw

    def _validate_schema(self, schema: type[T], raw: dict[str, Any]) -> T:
        # Schema firewall: invalid output NEVER enters core state.
        return schema.model_validate(raw)


def _schema_key(schema: type[BaseModel]) -> str:
    name = schema.__name__.lower().replace("output", "")
    return name if name in SCHEMA_VERSIONS else "classification"
