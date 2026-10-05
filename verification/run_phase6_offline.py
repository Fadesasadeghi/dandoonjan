"""Disposable offline pytest launcher. Never load the workspace .env or database."""
import os
from pathlib import Path
import sys
import tempfile
import shutil


def main():
    repo = Path(__file__).resolve().parents[1]
    args = [str(repo / arg) if (repo / arg).exists() else arg for arg in sys.argv[1:]]
    sys.path.insert(0, str(repo))
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='dj-phase6-') as folder:
        os.chdir(folder)
        # Subprocess migration/browser helpers sometimes choose cwd=repo. Disable
        # dotenv at interpreter startup there too; never open provider secrets.
        Path('sitecustomize.py').write_text(
            "from app.config import Settings\nSettings.model_config['env_file'] = None\n",
            encoding='utf-8')
        config = (repo / 'alembic.ini').read_text(encoding='utf-8')
        Path('alembic.ini').write_text(config.replace('script_location = alembic',
            'script_location = ' + (repo / 'alembic').as_posix()), encoding='utf-8')
        # Some integrity tests load the historical manifests relative to cwd.
        shutil.copytree(repo / 'alembic', Path('alembic'), ignore=shutil.ignore_patterns('__pycache__'))
        os.environ.update({
            'DJ_DATABASE_URL': 'sqlite:///global.db',
            'DJ_ARTIFACT_STORAGE_DIR': str(Path(folder) / 'storage'),
            'DJ_AI_PROVIDER': 'mock', 'DJ_AI_MODEL_NAME': 'mock-evidence-v1',
            'DJ_LIVE_PROVIDER_ENABLED': 'false', 'DJ_OPENAI_API_KEY': '',
            'DJ_OPENROUTER_API_KEY': '', 'DJ_ENVIRONMENT': 'test',
            'DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED': 'false',
            'DJ_AUTH_FOUNDATION_ENABLED': 'false', 'DJ_AUTH_ALLOWED_ORIGINS': '[]',
            'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONPATH': str(Path(folder)) + os.pathsep + str(repo),
            'GIT_DIR': str(repo / '.git'), 'GIT_WORK_TREE': str(repo),
        })
        sys.dont_write_bytecode = True
        import httpx
        network_attempts = []
        original_transport = httpx.HTTPTransport.handle_request
        def forbidden_network(self, request):
            network_attempts.append(True)
            raise AssertionError('OFFLINE_GATE_NETWORK_DISPATCH_FORBIDDEN')
        httpx.HTTPTransport.handle_request = forbidden_network
        import pytest
        try:
            result = pytest.main([*args, '-p', 'no:cacheprovider'])
            if network_attempts:
                print('OFFLINE_GATE_NETWORK_TRIPWIRE_FAILED')
                return 1
            return result
        finally:
            httpx.HTTPTransport.handle_request = original_transport
            os.chdir(previous)


if __name__ == '__main__':
    raise SystemExit(main())
