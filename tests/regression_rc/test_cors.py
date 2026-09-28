from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
import pytest
from app.config import Settings


def test_default_cors_denies_untrusted_origin(api_client):
    client, _, _ = api_client
    response = client.options("/api/cases", headers={
        "Origin": "https://untrusted.invalid",
        "Access-Control-Request-Method": "POST"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", ["*", "https://*.invalid", "null", "https://demo.invalid/", "https://demo.invalid/path", "https://name@demo.invalid"])
def test_cors_rejects_non_origin_configuration(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin])


def test_cors_environment_exact_allowlist(monkeypatch):
    monkeypatch.setenv("DJ_CORS_ORIGINS", '["https://pilot.invalid"]')
    settings = Settings(_env_file=None)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])
    with TestClient(app) as client:
        for origin, status in [("https://pilot.invalid", 200), ("https://other.invalid", 400)]:
            response = client.options("/api/cases", headers={"Origin": origin,
                "Access-Control-Request-Method": "POST"})
            assert response.status_code == status
            assert response.headers.get("access-control-allow-origin") == (origin if status == 200 else None)
