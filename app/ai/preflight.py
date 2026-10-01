"""Local-only acceptance configuration. Never discovers models or retrieves keys."""
import re
from app.errors import ProviderUnavailableError

CONTRACT_VERSION = 'real-provider-v3'
REVIEW_PROMPT_VERSION = 'review-instructions-v3'
LOCAL_SYNTHETIC_FREE_MODEL = 'qwen/qwen3.8-27b:free'


def failure(category):
    return ProviderUnavailableError(category=category)


def validate_configuration(model, api_key, live_enabled, offline=False, *,
                           environment=None, local_synthetic_acceptance_enabled=False):
    # The adapter owns the explicit offline handler path. A generic HTTP client
    # never authorizes it. Tests use only a synthetic dummy credential.
    if not offline and not live_enabled:
        raise failure('configuration')
    # Exact allowlist, never model discovery or a general free-model bypass.
    # Misusing this mode in production or with a paid model fails closed.
    if local_synthetic_acceptance_enabled and (
            local_synthetic_acceptance_enabled is not True or
            environment != 'local-synthetic' or model != LOCAL_SYNTHETIC_FREE_MODEL):
        raise failure('configuration')
    if (not isinstance(model, str) or len(model) > 128 or
            not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+', model) or
            'mock' in model.lower() or
            (':free' in model.lower() and not local_synthetic_acceptance_enabled) or
            model.lower() in ('openrouter/auto', 'openrouter/free') or
            model.lower().split('/')[1].split(':')[0] in ('auto', 'free', 'router', 'dynamic')):
        raise failure('configuration')
    if not isinstance(api_key, str) or not api_key.strip() or api_key != api_key.strip():
        raise failure('configuration')
    if any(ord(char) < 33 or ord(char) > 126 for char in api_key):
        raise failure('configuration')
