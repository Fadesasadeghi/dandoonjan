"""Reuse isolated P0 API fixtures for RC regressions."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "p0_rc_fixtures", Path(__file__).parents[1] / "regression_p0" / "conftest.py")
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)
regression_settings = _fixtures.regression_settings
api_client = _fixtures.api_client
