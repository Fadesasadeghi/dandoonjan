"""D/I: current report selection and durable rejected-upload audit events."""
from copy import deepcopy

from app.domain.models import Artifact, AssessmentSnapshot, AuditEvent, Case, Report


def test_blocked_revision_never_returns_historical_report_as_current(api_client, pdf_bytes):
    client, sessions, _ = api_client
    response = client.post("/api/cases", data={"question": "Explain tooth 46"})
    assert response.status_code == 201
    case_id = response.json()["case_id"]
    url = f"/api/cases/{case_id}"
    assert client.post(f"{url}/artifacts", files={
        "file": ("plan.pdf", pdf_bytes, "application/pdf")}).status_code == 201
    first = client.post(f"{url}/process")
    assert first.status_code == 200 and first.json()["report"]
    old_report = client.get(f"{url}/report")
    assert old_report.status_code == 200
    old_id = old_report.json()["report_id"]
    with sessions() as db:
        stored = db.query(Report).filter(Report.public_id == old_id).one()
        frozen = deepcopy(stored.content)
        snapshot_id = stored.snapshot_id
        frozen_snapshot = deepcopy(db.get(AssessmentSnapshot, snapshot_id).payload)
    revision = client.patch(url, data={"question": "بدون نسخه چه دارویی بخرم؟"})
    assert revision.status_code == 200 and revision.json()["changed"] is True
    blocked = client.post(f"{url}/process")
    assert blocked.status_code == 200
    assert blocked.json()["safety_state"] == "BLOCKED" and blocked.json()["report"] is None
    with sessions() as db:
        assert db.query(Report).filter(Report.public_id == old_id).one().content == frozen
        assert db.get(AssessmentSnapshot, snapshot_id).payload == frozen_snapshot
    current = client.get(f"{url}/report")
    # No new historical-report API or particular error code is prescribed here.
    assert not (current.is_success and current.json().get("report_id") == old_id), \
        "current-report endpoint returned the preserved historical report after BLOCKED"


def test_rejected_upload_persists_audit_without_partial_ingestion(api_client):
    client, sessions, storage = api_client
    created = client.post("/api/cases", data={"question": "Synthetic upload test"})
    assert created.status_code == 201
    case_id = created.json()["case_id"]
    with sessions() as db:
        case = db.query(Case).filter(Case.public_id == case_id).one()
        internal_id, version = case.id, case.version
        old_audit_ids = {e.id for e in db.query(AuditEvent).filter(AuditEvent.case_id == case.id)}
    response = client.post(f"/api/cases/{case_id}/artifacts", files={
        "file": ("unsupported.exe", b"MZ-synthetic", "application/x-msdownload")})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_ARTIFACT"
    # A new session proves durability after the request's rollback/close boundary.
    with sessions() as db:
        assert db.query(Artifact).filter(Artifact.case_id == internal_id).count() == 0
        assert db.get(Case, internal_id).version == version
        assert not any(p.is_file() for p in storage.rglob("*"))
        events = db.query(AuditEvent).filter(AuditEvent.case_id == internal_id).all()
        assert old_audit_ids <= {e.id for e in events}
        rejected = [e for e in events if e.event_type == "artifact_rejected"]
        assert len(rejected) == 1, "intended artifact_rejected event was rolled back"
        assert rejected[0].detail["reason"] == "UNSUPPORTED_ARTIFACT"
