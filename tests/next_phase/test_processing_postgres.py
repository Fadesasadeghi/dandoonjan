"""Opt-in private synthetic PostgreSQL admission. No provider network transport."""
import pytest

from verification.test_rc_postgres import pg_url, migrate
from tests.next_phase.test_processing_concurrency import (
    test_same_case_has_one_execution_and_reconciles as check_same_case,
    test_different_cases_overlap as check_different_cases,
    test_mutation_cannot_activate_obsolete_result as check_input_change,
)


@pytest.fixture()
def pg_api(pg_url, regression_settings, monkeypatch, request):
    migrate(pg_url)
    monkeypatch.setattr(regression_settings, 'database_url', pg_url)
    # Reuse the real ACCOUNT/CSRF fixture after choosing the private DB. The
    # existing pg_url fixture creates only a unique disposable synthetic database.
    return request.getfixturevalue('api_client')


@pytest.mark.parametrize('contention', ['simultaneous_claim', 'during_dispatch'])
def test_postgres_same_case(pg_api, monkeypatch, contention):
    check_same_case(pg_api, monkeypatch, contention)


def test_postgres_different_cases(pg_api, monkeypatch):
    check_different_cases(pg_api, monkeypatch)


def test_postgres_input_change(pg_api, monkeypatch):
    check_input_change(pg_api, monkeypatch, 'dossier')
