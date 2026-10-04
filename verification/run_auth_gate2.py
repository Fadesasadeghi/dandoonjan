"""Run pytest with Windows-process-local offline settings and disposable defaults.

WSL shell environment assignments do not reliably reach Windows Python. Set the
environment before pytest imports the application or reads .env. Test fixtures
continue to own their individual databases and storage.
"""
import os
from pathlib import Path
import sys
import tempfile


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    with tempfile.TemporaryDirectory(prefix='dj-auth-gate2-') as folder:
        root = Path(folder)
        os.environ.update({
            'DJ_DATABASE_URL': f"sqlite:///{(root/'global.db').as_posix()}",
            'DJ_ARTIFACT_STORAGE_DIR': str(root/'storage'),
            'DJ_AI_PROVIDER': 'mock', 'DJ_AI_MODEL_NAME': 'mock-evidence-v1',
            'DJ_LIVE_PROVIDER_ENABLED': 'false', 'DJ_OPENAI_API_KEY': '',
            'DJ_OPENROUTER_API_KEY': '', 'DJ_ENVIRONMENT': 'test',
            'DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED': 'false',
            'DJ_AUTH_FOUNDATION_ENABLED': 'false', 'DJ_AUTH_ALLOWED_ORIGINS': '[]',
        })
        import pytest
        return pytest.main(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
