"""Standalone deployment checks. No dotenv, provider construction or migrations.

Success proves these bounded checks only, not provider availability, clinical
readiness, HTTPS/proxy operation, durable mounts or recoverability.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import get_origin

from pydantic import BaseModel, ConfigDict, create_model
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ASSETS = (
    'index.html', 'styles.css', 'landing.css', 'report-print.css', 'account.css',
    'account.js', 'app.js', 'landing.js', 'report-export.js',
    'hero-tooth-aqua.png', 'tooth.svg',
)


def load_configuration() -> BaseModel:
    # Use the existing field definitions/defaults, but a plain BaseModel: even
    # overriding a BaseSettings secret field would still scan the full environment.
    # No Settings constructor, dotenv/file sources, or provider key values here.
    fields = {name: field for name, field in Settings.model_fields.items()
              if name not in {'openrouter_api_key', 'openai_api_key'}}
    configuration_type = create_model('DeploymentConfiguration',
        __config__=ConfigDict(hide_input_in_errors=True),
        **{name: (field.annotation, field.default) for name, field in fields.items()})
    values = {}
    for name, field in fields.items():
        value = os.environ.get('DJ_' + name.upper())
        if value is not None:
            values[name] = json.loads(value) if get_origin(field.annotation) is list else value
    settings = configuration_type(**values)
    # Reuse the app's origin syntax validation without loading its settings.
    Settings.exact_origins(settings.auth_allowed_origins)
    Settings.exact_origins(settings.cors_origins)
    return settings


def check_configuration(settings: Settings | BaseModel, *, key_present: bool,
                        other_provider_key_present: bool = False) -> str:
    if settings.environment not in {'production', 'staging'}:
        return 'PRODUCTION_REQUIRED'
    try:
        url = make_url(settings.database_url)
        if url.drivername != 'postgresql+psycopg' or not url.database:
            return 'POSTGRES_CONFIGURATION_INVALID'
    except Exception:
        return 'POSTGRES_CONFIGURATION_INVALID'
    if (not settings.auth_foundation_enabled or not settings.auth_allowed_origins or
            any(not origin.startswith('https://') for origin in settings.auth_allowed_origins) or
            not set(settings.cors_origins).issubset(settings.auth_allowed_origins)):
        return 'AUTH_CONFIGURATION_INVALID'
    if settings.environment == 'staging':
        if key_present or other_provider_key_present:
            return 'STAGING_PROVIDER_CREDENTIALS_FORBIDDEN'
        if (settings.ai_provider != 'mock' or settings.ai_model_name != 'mock-evidence-v1'
                or settings.live_provider_enabled or settings.local_synthetic_acceptance_enabled):
            return 'PROVIDER_CONFIGURATION_INVALID'
        if settings.cors_origins:
            return 'AUTH_CONFIGURATION_INVALID'
    else:
        # Mirror existing model routing restrictions without constructing an adapter,
        # reading its key value, or changing the provider's own validation/behavior.
        model = settings.ai_model_name
        if (settings.ai_provider != 'openrouter' or not settings.live_provider_enabled or
                settings.local_synthetic_acceptance_enabled or not key_present or
                len(model) > 128 or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+', model) or
                'mock' in model.lower() or ':free' in model.lower() or
                model.lower().split('/')[1].split(':')[0] in {'auto', 'free', 'router', 'dynamic'}):
            return 'PROVIDER_CONFIGURATION_INVALID'
    if not settings.require_clinician_reviewed_knowledge_pack:
        return 'REVIEWED_PACK_ENFORCEMENT_REQUIRED'
    if not Path(settings.artifact_storage_dir).is_absolute():
        return 'ABSOLUTE_ARTIFACT_DIRECTORY_REQUIRED'
    if settings.max_upload_bytes <= 0:
        return 'UPLOAD_LIMIT_INVALID'
    return 'OK'


def postgres_version_supported(version_num: int) -> bool:
    return 160000 <= version_num < 170000


def check_database(settings: Settings | BaseModel, root: Path = ROOT) -> str:
    # ScriptDirectory reads revision files only. Never load alembic/env.py,
    # adoption code, application DB globals, domain models or the HTTP app.
    try:
        config = Config()
        config.set_main_option('script_location', str(root / 'alembic'))
        expected = ScriptDirectory.from_config(config).get_heads()
        if len(expected) != 1:
            return 'PACKAGED_MIGRATIONS_INVALID'
    except Exception:
        return 'PACKAGED_MIGRATIONS_INVALID'
    engine = None
    try:
        engine = create_engine(settings.database_url, hide_parameters=True,
                               connect_args={'connect_timeout': 10})
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                connection.execute(text("SET LOCAL statement_timeout = '10000'"))
                version = int(connection.execute(text('SHOW server_version_num')).scalar_one())
                if not postgres_version_supported(version):
                    return 'POSTGRES_VERSION_INVALID'
                heads = MigrationContext.configure(connection).get_current_heads()
                if set(heads) != set(expected):
                    return 'SCHEMA_REVISION_INVALID'
        return 'OK'
    except Exception:
        # Exceptions can contain URLs, credentials or SQL. Emit fixed codes only.
        return 'DATABASE_UNAVAILABLE'
    finally:
        if engine is not None:
            engine.dispose()


def check_storage(path: Path) -> str:
    try:
        if not path.is_dir():
            return 'ARTIFACT_DIRECTORY_MISSING'
        # TemporaryFile owns only its own probe; never create the configured root
        # or modify/remove any evidence. This does not prove persistent mounting.
        with tempfile.TemporaryFile(dir=path, prefix='.dj-preflight-') as probe:
            probe.write(b'dandoonjan-storage-probe')
            probe.flush()
            probe.seek(0)
            if probe.read() != b'dandoonjan-storage-probe':
                return 'ARTIFACT_DIRECTORY_UNWRITABLE'
        return 'OK'
    except Exception:
        return 'ARTIFACT_DIRECTORY_UNWRITABLE'


def check_frontend(root: Path = ROOT) -> str:
    try:
        for asset in REQUIRED_ASSETS:
            path = root / 'frontend' / asset
            if not path.is_file() or path.stat().st_size == 0:
                return 'FRONTEND_ASSETS_MISSING'
            with path.open('rb') as source:
                source.read(1)
        return 'OK'
    except Exception:
        return 'FRONTEND_ASSETS_MISSING'


def main() -> int:
    try:
        # Inspect provider key presence only, separately from configuration.
        key_present = bool(os.environ.get('DJ_OPENROUTER_API_KEY'))
        settings = load_configuration()
        configuration = check_configuration(settings, key_present=key_present,
            other_provider_key_present=bool(os.environ.get('DJ_OPENAI_API_KEY')))
        checks = {'configuration': configuration}
        if configuration == 'OK':
            checks.update(database=check_database(settings),
                          artifacts=check_storage(Path(settings.artifact_storage_dir)),
                          frontend=check_frontend())
    except Exception:
        checks = {'configuration': 'CONFIGURATION_INVALID'}
    passed = all(result == 'OK' for result in checks.values())
    print(json.dumps({'status': 'PASS' if passed else 'FAIL', 'checks': checks}, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
