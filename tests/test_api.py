"""API integration tests via FastAPI TestClient (offline)."""
import os

os.environ.setdefault("DJ_DATABASE_URL", "sqlite://")
os.environ.setdefault("DJ_ARTIFACT_STORAGE_DIR", "./test_api_store")

import pytest
from tests.regression_p0.conftest import regression_settings, raw_api_client, api_client


@pytest.fixture()
def client(api_client):
    yield api_client[0]


def _pdf(text="Treatment Plan\nTooth 46: RCT"):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/health").json() == {"status": "ok"}


def test_presentation_home_and_demo_sample(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "قبل از درمان" in home.text
    sample = client.get("/api/demo/sample")
    assert sample.status_code == 200
    assert "Treatment Plan" in sample.text


def test_case_lifecycle(client):
    r = client.post("/api/cases", data={
        "question": "آیا دندان 46 باید عصب‌کشی شود؟",
        "dentist_recommendation": "عصب کشی لازم است"})
    assert r.status_code == 201
    case_id = r.json()["case_id"]

    r = client.post(f"/api/cases/{case_id}/artifacts",
                    files={"file": ("plan.pdf", _pdf(), "application/pdf")})
    assert r.status_code == 201

    r = client.post(f"/api/cases/{case_id}/process")
    assert r.status_code == 200
    assert r.json()["report"] is not None

    status = client.get(f"/api/cases/{case_id}/status").json()
    assert status["status"] == "REPORT_READY"

    report = client.get(f"/api/cases/{case_id}/report").json()
    sections = {s["section"] for s in report["sections"]}
    assert {"your_question", "dentist_recommendation", "found_in_documents",
            "evidence_status", "still_unclear", "missing_evidence", "questions_to_ask",
            "confidence", "safety_note"} <= sections


def test_unsupported_upload_rejected_with_safe_message(client):
    r = client.post("/api/cases", data={"question": "q"})
    case_id = r.json()["case_id"]
    r = client.post(f"/api/cases/{case_id}/artifacts",
                    files={"file": ("virus.exe", b"MZ\x90\x00", "application/x-msdownload")})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "UNSUPPORTED_ARTIFACT"
    assert "message_fa" in r.json()["detail"]


def test_report_404_before_processing(client):
    r = client.post("/api/cases", data={"question": "q"})
    case_id = r.json()["case_id"]
    assert client.get(f"/api/cases/{case_id}/report").status_code == 404
