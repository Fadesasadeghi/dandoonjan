"""Offline SQLite regression for the shared PostgreSQL lifecycle harness.

This exercises real authentication and the injected transport; it is not
PostgreSQL runtime evidence.
"""
from verification.test_rc_postgres import (
    test_postgres_injected_openrouter_dossier_lifecycle as check_lifecycle,
)


def test_current_contract_lifecycle_harness(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'synthetic.db').as_posix()}"
    check_lifecycle(url, tmp_path, monkeypatch)
