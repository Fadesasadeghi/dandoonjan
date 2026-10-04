"""Gate 1: isolated synthetic storage; no provider or developer DB access."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('auth_api_fixtures', Path(__file__).parents[1] / 'regression_p0/conftest.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
regression_settings = fixtures.regression_settings
api_client = fixtures.raw_api_client

@pytest.fixture(autouse=True)
def auth_settings(regression_settings, monkeypatch):
    monkeypatch.setitem(regression_settings.__dict__, 'auth_foundation_enabled', True)
    monkeypatch.setitem(regression_settings.__dict__, 'auth_allowed_origins', ['http://testserver'])
