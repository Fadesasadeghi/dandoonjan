from concurrent.futures import ThreadPoolExecutor
from .helpers import register, login


def test_persistent_normalized_limit_and_no_permanent_lockout(api_client):
    from app.domain.models import AuthRateLimit, utcnow
    from datetime import timedelta
    client, sessions, _ = api_client
    register(client)
    responses = [login(client, email='SYNTHETIC@example.com', password='wrong synthetic password') for _ in range(6)]
    assert [r.status_code for r in responses] == [401]*5+[429]
    assert 'Retry-After' in responses[-1].headers
    assert login(client).status_code == 429
    with sessions() as db:
        for row in db.query(AuthRateLimit).all(): row.window_started_at = utcnow()-timedelta(minutes=16)
        db.commit()
    assert login(client).status_code == 200


def test_concurrent_limit_is_atomic(api_client):
    from fastapi.testclient import TestClient
    from app.main import app
    _, _, _ = api_client
    def attempt(_):
        with TestClient(app) as client:
            return login(client, email='rate@example.com').status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(attempt, range(6)))
    assert sorted(codes) == [401]*5+[429]
