from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.exc import IntegrityError
import pytest

from app.domain.models import User, Case, public_id
from .helpers import PASSWORD, register, csrf


def test_registration_preserves_legacy_and_never_returns_credentials(api_client):
    client, sessions, _ = api_client
    with sessions() as db:
        legacy = User(public_id=public_id('USR'), display_name='Synthetic legacy')
        db.add(legacy); db.flush()
        case = Case(public_id=public_id('CASE'), user_id=legacy.id, version=7)
        db.add(case); db.commit()
        db.refresh(legacy)  # Compare persisted SQLite timestamps, not pre-flush tz representation.
        original = (legacy.id, legacy.public_id, legacy.display_name, legacy.created_at, case.id, case.user_id, case.version)
    response = register(client, ' Synthetic@EXAMPLE.com ')
    assert response.status_code == 201
    assert set(response.json()) == {'public_id', 'email', 'email_verified'}
    assert PASSWORD not in response.text
    with sessions() as db:
        legacy = db.get(User, original[0]); case = db.get(Case, original[4])
        assert (legacy.id, legacy.public_id, legacy.display_name, legacy.created_at, case.id, case.user_id, case.version) == original
        assert legacy.kind == 'LEGACY' and legacy.password_hash is None
        account = db.query(User).filter_by(kind='ACCOUNT').one()
        assert account.normalized_email == 'synthetic@example.com'
        assert account.password_hash.startswith('$argon2id$')
        assert PASSWORD not in account.password_hash
        assert len(account.public_id.split('-')[1]) >= 32


def test_case_insensitive_duplicate_is_transactionally_rejected(api_client):
    client, sessions, _ = api_client
    assert register(client).status_code == 201
    assert register(client, ' SYNTHETIC@EXAMPLE.COM ').status_code == 400
    with sessions() as db:
        assert db.query(User).filter_by(kind='ACCOUNT').count() == 1
        original = db.query(User).filter_by(kind='ACCOUNT').one()
        db.add(User(public_id='USR-' + 'a'*32, kind='ACCOUNT', status='ACTIVE', email=original.email,
                    normalized_email=original.normalized_email, password_hash=original.password_hash))
        with pytest.raises(IntegrityError):
            db.flush()


def test_concurrent_duplicate_registration(api_client):
    from fastapi.testclient import TestClient
    from app.main import app
    _, sessions, _ = api_client
    def attempt(_):
        with TestClient(app) as client:
            return register(client, 'race@example.com').status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [201, 400]
    with sessions() as db:
        assert db.query(User).filter_by(normalized_email='race@example.com').count() == 1


def test_legacy_credentials_forbidden_by_database(api_client):
    _, sessions, _ = api_client
    with sessions() as db:
        db.add(User(public_id='USR-legacy-invalid', password_hash='forbidden'))
        with pytest.raises(IntegrityError):
            db.flush()


@pytest.mark.parametrize('body', [
    {'email':'invalid', 'password': PASSWORD},
    {'email':'valid@example.com', 'password': 'short'},
    {'email':'valid@example.com', 'password': {'secret': PASSWORD}},
    {'email':'valid@example.com', 'password': PASSWORD, 'user_id': 1},
])
def test_validation_never_echoes_password(api_client, body):
    client, _, _ = api_client
    response = client.post('/api/auth/register', json=body, headers=csrf(client))
    assert response.status_code == 422
    assert PASSWORD not in response.text and 'short' not in response.text


def test_registration_commit_failure_rolls_back_account_and_context(api_client, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.domain.models import PreAuthContext
    client, sessions, _ = api_client
    headers = csrf(client)
    original = sessions.class_.commit
    calls = []
    def fail_final_commit(db):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('SYNTHETIC_COMMIT_FAILURE')
        return original(db)
    monkeypatch.setattr(sessions.class_, 'commit', fail_final_commit)
    with TestClient(app, raise_server_exceptions=False) as failed:
        failed.cookies.update(client.cookies)
        response = failed.post('/api/auth/register', json={'email':'Synthetic@example.com','password':PASSWORD}, headers=headers)
    assert response.status_code == 500 and 'Set-Cookie' not in response.headers
    with sessions() as db:
        assert db.query(User).count() == 0
        assert db.query(PreAuthContext).one().consumed_at is None


def test_account_case_delete_is_restricted(api_client):
    client, sessions, _ = api_client
    register(client)
    with sessions() as db:
        account = db.query(User).filter_by(kind='ACCOUNT').one()
        db.add(Case(public_id='CASE-delete-synthetic', user_id=account.id))
        db.commit()
        db.delete(account)
        with pytest.raises(IntegrityError): db.flush()


def test_malformed_json_response_and_logs_never_echo_credentials(api_client, caplog):
    client, _, _ = api_client
    headers = {**csrf(client), 'Content-Type':'application/json'}
    response = client.post('/api/auth/register', headers=headers, content='{"password":"SYNTHETIC_SECRET_SENTINEL"')
    assert response.status_code == 422
    assert 'SYNTHETIC_SECRET_SENTINEL' not in response.text + caplog.text
