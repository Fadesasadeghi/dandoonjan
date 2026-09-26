"""Presentation may not strengthen claims, merge sources, or expose stale reports."""
import json
import pytest


def create(client, question="آیا پیشنهاد عصب کشی دندان 46 پشتیبانی دارد؟"):
    return client.post("/api/cases", data={"question": question,
        "dentist_recommendation": "RCT recommended for tooth 46"}).json()["case_id"]


def upload(client, case_id, name="plan.txt", text="Treatment Plan\nTooth 46: RCT recommended"):
    return client.post(f"/api/cases/{case_id}/artifacts",
        files={"file": (name, text.encode(), "text/plain")})


def test_sources_and_relevant_is_not_support(api_client):
    client, sessions, _ = api_client
    case_id = create(client)
    upload(client, case_id)
    client.post(f"/api/cases/{case_id}/process")
    report = client.get(f"/api/cases/{case_id}/report").json()
    p = report["presentation"]
    assert p["materials"][0]["filename"] == "plan.txt"
    assert len(p["claims"]) >= 2
    assert {c["source"] for c in p["claims"]} >= {
        "گفتهٔ دندان‌پزشک به روایت شما", "استخراج‌شده از سند"}
    assert all("عصب‌کشی" in c["label"] for c in p["claims"])
    assert all("پیشنهاد شده" in c["label"] for c in p["claims"])
    evidence = [e for c in p["claims"] for e in c["evidence"]]
    assert evidence and any(e["relationship"] == "مرتبط با ادعا؛ اثبات ضرورت درمان نیست" for e in evidence)
    assert all(e["filename"] == "plan.txt" for e in evidence)
    encoded = json.dumps(p, ensure_ascii=False)
    for internal in ("RUN-", "CLM-", "FND-", "ART-", "ROOT_CANAL", "TOOTH_", "derivation_run"):
        assert internal not in encoded
    from app.domain.models import AssessmentSnapshot, Report
    with sessions() as db:
        stored = db.query(Report).filter(Report.public_id == report["report_id"]).one()
        snapshot = db.get(AssessmentSnapshot, stored.snapshot_id)
        before = (json.dumps(stored.content, sort_keys=True), snapshot.content_hash,
                  json.dumps(snapshot.payload, sort_keys=True))
    client.get(f"/api/cases/{case_id}/report")
    with sessions() as db:
        stored = db.query(Report).filter(Report.public_id == report["report_id"]).one()
        snapshot = db.get(AssessmentSnapshot, stored.snapshot_id)
        assert before == (json.dumps(stored.content, sort_keys=True), snapshot.content_hash,
                          json.dumps(snapshot.payload, sort_keys=True))


def test_same_case_more_evidence_and_rejection(api_client):
    client, _, _ = api_client
    case_id = create(client)
    assert client.post(f"/api/cases/{case_id}/process").json()["status"] == "NEEDS_MORE_EVIDENCE"
    rejected = client.post(f"/api/cases/{case_id}/artifacts", files={"file": ("bad.exe", b"MZ", "application/octet-stream")})
    assert rejected.status_code == 422 and rejected.json()["detail"]["message_fa"]
    assert upload(client, case_id).status_code == 201
    assert upload(client, case_id).json()["duplicate_of"]
    assert len(client.get(f"/api/cases/{case_id}").json()["artifacts"]) == 1
    client.post(f"/api/cases/{case_id}/process")
    old = client.get(f"/api/cases/{case_id}/report").json()
    assert old["presentation"]["claims"]
    upload(client, case_id, "extra.txt", "Treatment Plan\nTooth 36: crown recommended")
    assert client.get(f"/api/cases/{case_id}/report").status_code == 404
    client.post(f"/api/cases/{case_id}/process")
    new = client.get(f"/api/cases/{case_id}/report").json()
    assert new["report_id"] != old["report_id"]
    assert len(new["presentation"]["materials"]) == 2
    client.patch(f"/api/cases/{case_id}", data={"question": "prescribe me"})
    client.post(f"/api/cases/{case_id}/process")
    assert client.get(f"/api/cases/{case_id}/report").status_code == 404


@pytest.mark.parametrize("question,kind", [("facial swelling", "URGENT"), ("prescribe me", None)])
def test_safety_reports_do_not_gain_claims(api_client, question, kind):
    client, _, _ = api_client
    case_id = create(client, question)
    upload(client, case_id)
    client.post(f"/api/cases/{case_id}/process")
    response = client.get(f"/api/cases/{case_id}/report")
    if kind is None:
        assert response.status_code == 404
    else:
        assert response.json()["report_kind"] == kind
        assert response.json()["presentation"] == {}
        assert [s["section"] for s in response.json()["sections"]] == ["safety_note"]


def test_review_pending_has_no_claims(api_client, monkeypatch):
    from app.ai.providers import MockProvider
    original = MockProvider.run
    def low_confidence(self, prompt, content, params):
        out = original(self, prompt, content, params)
        if prompt.prompt_id in ("treatment_plan_extractor", "invoice_extractor"):
            out["fields"] = [{**f, "confidence": 0.3} for f in out["fields"]]
            out["treatment_items"] = [{**i, "confidence": 0.3} for i in out.get("treatment_items", [])]
        return out
    monkeypatch.setattr(MockProvider, "run", low_confidence)
    client, _, _ = api_client
    case_id = create(client)
    upload(client, case_id)
    client.post(f"/api/cases/{case_id}/process")
    report = client.get(f"/api/cases/{case_id}/report").json()
    assert report["report_kind"] == "REVIEW_PENDING"
    assert report["presentation"] == {}


def test_presentation_is_case_scoped(api_client):
    client, _, _ = api_client
    first = create(client)
    upload(client, first, "first.txt")
    client.post(f"/api/cases/{first}/process")
    before = client.get(f"/api/cases/{first}/report").json()
    second = create(client)
    upload(client, second, "second.txt", "Treatment Plan\nTooth 36: Crown")
    client.post(f"/api/cases/{second}/process")
    after = client.get(f"/api/cases/{first}/report").json()
    assert after == before
    assert "second.txt" not in json.dumps(after["presentation"])


@pytest.mark.parametrize("word,expected", [("planned", "در طرح درمان ثبت شده"),
    ("recommended", "پیشنهاد شده"), ("required", "لازم اعلام شده")])
def test_presentation_never_upgrades_modality(api_client, word, expected):
    client, _, _ = api_client
    case_id = client.post("/api/cases", data={"question": "q"}).json()["case_id"]
    upload(client, case_id, text=f"Treatment Plan\nTooth 46: RCT {word}")
    client.post(f"/api/cases/{case_id}/process")
    report = client.get(f"/api/cases/{case_id}/report").json()
    assert report["presentation"]["claims"]
    assert all(expected in c["label"] for c in report["presentation"]["claims"])


def test_tampered_snapshot_cannot_be_presented(api_client):
    from sqlalchemy import text
    client, sessions, _ = api_client
    case_id = create(client)
    upload(client, case_id)
    client.post(f"/api/cases/{case_id}/process")
    with sessions() as db:
        # Simulate the documented privileged raw-SQL bypass in synthetic data.
        db.execute(text("UPDATE assessment_snapshots SET content_hash = 'tampered'"))
        db.commit()
    response = client.get(f"/api/cases/{case_id}/report")
    assert response.status_code == 422
    assert response.json()["code"] == "SAFETY_BLOCKED"
