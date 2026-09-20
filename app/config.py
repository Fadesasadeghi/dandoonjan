"""Environment-based configuration. No secrets in code."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DANDOONJAN_EVIDENCE_CORE_V0"
    database_url: str = "sqlite:///./dandoonjan_dev.db"
    artifact_storage_dir: str = "./artifact_store"
    # AI provider: "mock" (default, offline, deterministic) or "openai" (adapter stub)
    ai_provider: str = "mock"
    ai_model_name: str = "mock-evidence-v1"
    openai_api_key: str = ""  # never hardcoded; read from env
    openrouter_api_key: str = ""  # never hardcoded; read from env
    max_upload_bytes: int = 25 * 1024 * 1024
    # Production deployments must set this to True to reject non-clinician-reviewed packs
    require_clinician_reviewed_knowledge_pack: bool = False
    environment: str = "development"

    model_config = {"env_file": ".env", "env_prefix": "DJ_", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
