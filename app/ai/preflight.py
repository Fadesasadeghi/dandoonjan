"""Local-only acceptance configuration. Never discovers models or retrieves keys."""
import re
from app.errors import ProviderUnavailableError

CONTRACT_VERSION = 'real-provider-v3'
REVIEW_PROMPT_VERSION = 'review-instructions-v2'


def failure(category):
    return ProviderUnavailableError(category=category)


def validate_configuration(model, api_key, live_enabled, offline=False):
    # The adapter owns the explicit offline handler path. A generic HTTP client
    # never authorizes it. Tests use only a synthetic dummy credential.
    if not offline and not live_enabled:
        raise failure('configuration')
    if (not isinstance(model, str) or len(model) > 128 or
            not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+', model) or
            any(token in model.lower() for token in ('mock', ':free')) or
            model.lower() in ('openrouter/auto', 'openrouter/free') or
            model.lower().endswith(('/auto', '/free'))):
        raise failure('configuration')
    if not isinstance(api_key, str) or not api_key.strip() or api_key != api_key.strip():
        raise failure('configuration')
    if any(ord(char) < 33 or ord(char) > 126 for char in api_key):
        raise failure('configuration')
