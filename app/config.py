"""Environment-based configuration. No secrets in code."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DANDOONJAN_EVIDENCE_CORE_V0"
    database_url: str = "sqlite:///./dandoonjan_dev.db"
    artifact_storage_dir: str = "./artifact_store"
    # AI provider: explicit "mock" (offline) or "openrouter" (fail closed).
    ai_provider: str = "mock"
    ai_model_name: str = "mock-evidence-v1"
    # Deliberate authorization gate. Offline tests inject a transport instead.
    live_provider_enabled: bool = False
    # Backend-only; requires environment=local-synthetic and the exact approved model.
    local_synthetic_acceptance_enabled: bool = False
    openai_api_key: str = ""  # never hardcoded; read from env
    openrouter_api_key: str = ""  # never hardcoded; read from env
    max_upload_bytes: int = 25 * 1024 * 1024
    # Production deployments must set this to True to reject non-clinician-reviewed packs
    require_clinician_reviewed_knowledge_pack: bool = False
    environment: str = "development"
    # Same-origin frontend needs no CORS grant. Explicit JSON array in DJ_CORS_ORIGINS.
    cors_origins: list[str] = []
    # Backend verification only until Gate 2 protects every normal case route.
    auth_foundation_enabled: bool = False
    auth_allowed_origins: list[str] = []

    @field_validator("cors_origins", "auth_allowed_origins")
    @classmethod
    def exact_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
                    parsed.username or parsed.password or parsed.path or
                    parsed.query or parsed.fragment or "*" in origin):
                raise ValueError("CORS requires exact HTTP(S) origins without paths or credentials")
        return origins

    model_config = {"env_file": ".env", "env_prefix": "DJ_", "extra": "ignore",
                    "hide_input_in_errors": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()
