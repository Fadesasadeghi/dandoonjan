"""Offline provider scope and diagnostic privacy; all markers are synthetic."""
import json
import traceback

import pytest

from app.ai.gateway import ModelGateway
from app.ai.providers import OpenRouterProvider
from app.ai.schemas import ClaimsOutput
from app.config import get_settings
from app.domain.models import ModelRun
from app.errors import ExtractionValidationError

MARKER = "SYNTHETIC_PRIVATE_CASE_AND_TOKEN_CANARY"
VALID = {"claims": [{"claim_type": "TREATMENT", "subject": "TOOTH_46",
    "predicate": "PROPOSES_TREATMENT", "object_value": "TREATMENT_ROOT_CANAL",
    "treatment": "TREATMENT_ROOT_CANAL", "modality": "RECOMMENDED", "confidence": 0.8}]}


def offline_gateway(db, monkeypatch, payload):
    # Bypass credential initialization and replace the HTTP boundary completely.
    provider = object.__new__(OpenRouterProvider)
    provider.model = "vendor/fixed-model"
    monkeypatch.setattr(provider, "_post", lambda *args: {
        "model": "vendor/fixed-model", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}]})
    monkeypatch.setattr("app.ai.gateway.OpenRouterProvider", lambda **kwargs: provider)
    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "ai_provider", "openrouter")
    return ModelGateway(db)


def test_openrouter_claim_builder_is_supported_without_mock(db, monkeypatch):
    gateway = offline_gateway(db, monkeypatch, VALID)
    monkeypatch.setattr(gateway.fallback, "run", lambda *args: pytest.fail("Mock used"))
    output, run = gateway.run("claim_builder", ClaimsOutput, '{"treatment_items":[]}')
    assert output.claims[0].modality == "RECOMMENDED"
    assert run.provider == "openrouter" and run.status == "SUCCEEDED"


@pytest.mark.parametrize("payload", [{"claims": MARKER}, {"claims": [], "extra": MARKER}])
def test_claim_schema_firewall_rejects_without_retaining_private_input(db, monkeypatch, payload):
    gateway = offline_gateway(db, monkeypatch, payload)
    with pytest.raises(ExtractionValidationError) as caught:
        gateway.run("claim_builder", ClaimsOutput, MARKER)
    run = db.query(ModelRun).one()
    assert run.status == "FAILED" and run.validated_output is None
    assert run.error == "SCHEMA_VALIDATION_FAILED"
    assert MARKER not in (run.error or "")
    assert MARKER not in "".join(traceback.format_exception(caught.value))


def test_unexpected_provider_error_does_not_retain_sensitive_details(db, monkeypatch):
    gateway = offline_gateway(db, monkeypatch, VALID)
    def fail(*args):
        raise RuntimeError(MARKER)
    monkeypatch.setattr(gateway.provider, "run", fail)
    with pytest.raises(ExtractionValidationError) as caught:
        gateway.run("claim_builder", ClaimsOutput, MARKER)
    assert MARKER not in db.query(ModelRun).one().error
    assert MARKER not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("invalid", [None, "schema", "ontology"])
def test_production_pipeline_uses_claim_builder_firewalls(api_client, monkeypatch, invalid):
    client, sessions, _ = api_client
    from app.security.sessions import cookie_name
    raw = client.cookies.get(cookie_name())
    monkeypatch.setattr(get_settings(), "environment", "production")
    client.cookies.set(cookie_name(), raw, domain='testserver.local', path='/')
    monkeypatch.setattr(get_settings(), "ai_provider", "openrouter")
    provider = object.__new__(OpenRouterProvider)
    provider.model = "vendor/fixed-model"
    seen = []
    def post(prompt, content):
        seen.append(prompt.prompt_id)
        payloads = {
            "artifact_classifier": {"category": "CLINICAL_DOCUMENT", "subtype": "TREATMENT_PLAN", "confidence": 0.9},
            "treatment_plan_extractor": {"fields": [], "treatment_items": [{
                "tooth": "TOOTH_46", "treatment": "TREATMENT_ROOT_CANAL",
                "predicate": "RECOMMENDED", "confidence": 0.8,
                "source_locator": {"page": 1, "span": "line:1", "bounding_box": None}}]},
            "claim_builder": VALID,
        }
        payload = json.loads(json.dumps(payloads[prompt.prompt_id]))
        if prompt.prompt_id == "claim_builder" and invalid == "schema":
            payload["extra"] = MARKER
        if prompt.prompt_id == "claim_builder" and invalid == "ontology":
            payload["claims"][0]["subject"] = "INVALID_TOOTH"
        return {"model": "vendor/fixed-model", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}]}
    monkeypatch.setattr(provider, "_post", post)
    monkeypatch.setattr("app.ai.gateway.OpenRouterProvider", lambda **kwargs: provider)
    monkeypatch.setattr("app.ai.providers.MockProvider.run", lambda *args: pytest.fail("Mock used"))
    case_id = client.post("/api/cases", data={"question": "Synthetic pipeline check"}).json()["case_id"]
    assert client.post(f"/api/cases/{case_id}/artifacts", files={
        "file": ("synthetic.txt", b"Treatment Plan\nTooth 46: RCT recommended", "text/plain")}).status_code == 201
    result = client.post(f"/api/cases/{case_id}/process")
    assert "claim_builder" in seen
    report = client.get(f"/api/cases/{case_id}/report")
    if invalid:
        assert result.json()["status"] == "FAILED"
        assert report.status_code == 404
    else:
        assert report.status_code == 200
        assert client.get(f"/api/cases/{case_id}/assessment").json()["assessments"][0]["modality"] == "RECOMMENDED"
        with sessions() as db:
            assert {run.provider for run in db.query(ModelRun)} == {"openrouter"}
