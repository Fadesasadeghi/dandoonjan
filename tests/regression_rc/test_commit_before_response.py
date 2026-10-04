"""A successful create response must mean the transaction is committed."""
from fastapi.testclient import TestClient


def test_create_commits_before_success_headers(api_client, monkeypatch):
    authenticated, sessions, _ = api_client
    import app.main as main
    events = []
    original = sessions.class_.commit
    def commit(session):
        original(session)
        events.append("committed")
    monkeypatch.setattr(sessions.class_, "commit", commit)

    async def observed(scope, receive, send):
        async def checked_send(message):
            if message["type"] == "http.response.start" and message["status"] == 201:
                events.append("response")
            await send(message)
        await main.app(scope, receive, checked_send)

    with TestClient(observed) as client:
        client.cookies.update(authenticated.cookies)
        client.headers.update(authenticated.headers)
        assert client.post("/api/cases", data={"question": "Synthetic commit check"}).status_code == 201
    assert events == ["committed", "response"]
