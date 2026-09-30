"""Offline production fail-closed checks; no real credentials or provider calls."""
import pytest

from app.ai.gateway import ModelGateway
from app.ai.providers import MockProvider
from app.ai.schemas import ClassificationOutput
from app.config import get_settings
from app.domain.models import ModelRun
from app.errors import DandoonjanError, ProviderUnavailableError

CONTENT = '{"mime":"text/plain","filename":"plan.txt"}\nTreatment Plan\nTooth 46: RCT'


@pytest.mark.parametrize("environment", ["production", "development", "test"])
def test_missing_key(db, monkeypatch, environment):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(ProviderUnavailableError):
        ModelGateway(db)


@pytest.mark.parametrize("environment", ["production", "development", "test"])
@pytest.mark.parametrize("failure", ["unavailable", "exception", "non_object", "invalid_schema"])
def test_provider_failure_policy(db, monkeypatch, environment, failure):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "ai_provider", "openrouter")

    class OfflineProvider:
        name = "openrouter"

        def __init__(self, **kwargs):
            pass

        def run(self, *args):
            if failure == "unavailable":
                raise ProviderUnavailableError("synthetic outage")
            if failure == "exception":
                raise RuntimeError("synthetic unexpected failure")
            return [] if failure == "non_object" else {"category": "NOT_A_CATEGORY"}

    monkeypatch.setattr("app.ai.gateway.OpenRouterProvider", OfflineProvider)
    gateway = ModelGateway(db)
    monkeypatch.setattr(gateway.fallback, "run", lambda *args: pytest.fail("Mock fallback"))
    with pytest.raises(DandoonjanError):
        gateway.run("artifact_classifier", ClassificationOutput, CONTENT)
    run = db.query(ModelRun).one()
    assert run.status == "FAILED"
    assert run.provider == "openrouter"
    assert run.validated_output is None


@pytest.mark.parametrize("provider", ["mock", "openai", "unknown"])
def test_production_never_implicitly_selects_mock(db, monkeypatch, provider):
    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "ai_provider", provider)
    with pytest.raises(ProviderUnavailableError):
        ModelGateway(db)


def test_valid_production_response_is_preserved(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "ai_provider", "openrouter")

    class OfflineProvider:
        name = "openrouter"
        def __init__(self, **kwargs):
            pass
        def run(self, *args):
            return {"category": "CLINICAL_DOCUMENT", "subtype": "TREATMENT_PLAN",
                    "confidence": 0.9}

    monkeypatch.setattr("app.ai.gateway.OpenRouterProvider", OfflineProvider)
    output, run = ModelGateway(db).run("artifact_classifier", ClassificationOutput, CONTENT)
    assert output.category == "CLINICAL_DOCUMENT"
    assert run.status == "SUCCEEDED" and run.provider == "openrouter"
    assert run.error is None
