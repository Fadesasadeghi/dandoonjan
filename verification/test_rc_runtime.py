"""Real local HTTP, five concurrent cases, restart persistence and log canaries."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import httpx
import pytest

from verification.test_rc_postgres import pg_url, migrate

ROOT = Path(__file__).resolve().parents[1]
CANARY = "SYNTHETIC_CASE_CONTENT_CANARY"
HEADER_CANARY = "SYNTHETIC_NOT_A_REAL_TOKEN_CANARY"


@contextmanager
def running_server(folder, database_url, environment="development"):
    folder.mkdir(exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "DJ_DATABASE_URL": database_url,
        "DJ_ARTIFACT_STORAGE_DIR": str(folder / "store"), "DJ_AI_PROVIDER": "mock",
        "DJ_ENVIRONMENT": environment, "DJ_OPENROUTER_API_KEY": "", "DJ_OPENAI_API_KEY": "",
        "DJ_CORS_ORIGINS": "[]", "DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK": "false"}
    with (folder / "server.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-config", "app/logging.json"],
            cwd=ROOT, env=env, stdout=log, stderr=log)
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as client:
            try:
                for _ in range(150):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.1)
                else:
                    pytest.fail("local server did not become healthy")
                yield client
            finally:
                process.terminate()
                process.wait(timeout=15)


def file_hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.rglob("*") if p.is_file()}


def exercise(folder, url):
    cases = []
    with running_server(folder, url) as client:
        for tooth in (41, 42, 43, 44, 45):
            created = client.post("/api/cases", data={"question": f"{CANARY}_{tooth}"})
            assert created.status_code == 201
            case_id = created.json()["case_id"]
            cases.append((case_id, tooth))
            rejected = client.post(f"/api/cases/{case_id}/artifacts", files={
                "file": ("synthetic.exe", b"MZ", "application/octet-stream")})
            assert rejected.status_code == 422
            accepted = client.post(f"/api/cases/{case_id}/artifacts", files={
                "file": (f"synthetic-{tooth}.txt", f"Treatment Plan\nTooth {tooth}: RCT recommended\n{CANARY}_{tooth}".encode(), "text/plain")})
            assert accepted.status_code == 201
        barrier = threading.Barrier(5)
        def process(item):
            barrier.wait(timeout=10)
            start = time.monotonic()
            result = client.post(f"/api/cases/{item[0]}/process")
            return start, time.monotonic(), result
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(process, cases))
        assert max(r[0] for r in results) < min(r[1] for r in results), "requests did not overlap"
        assert all(r[2].status_code == 200 for r in results), [(r[2].status_code, r[2].text) for r in results]
        assert all(r[2].json().get("status") != "FAILED" for r in results), [r[2].json() for r in results]
        reports = {}
        for case_id, tooth in cases:
            report = client.get(f"/api/cases/{case_id}/report")
            assert report.status_code == 200, report.text
            reports[case_id] = report.json()
            assessments = client.get(f"/api/cases/{case_id}/assessment").json()["assessments"]
            assert assessments and {a["subject"] for a in assessments} == {f"TOOTH_{tooth}"}
            assert all(a["modality"] == "RECOMMENDED" for a in assessments)
        client.get("/health?synthetic=" + HEADER_CANARY, headers={"Authorization": HEADER_CANARY})
    hashes = file_hashes(folder / "store")
    assert len(hashes) == 5
    with running_server(folder, url) as client:
        for case_id, tooth in cases:
            assert client.get(f"/api/cases/{case_id}").json()["question"] == f"{CANARY}_{tooth}"
            assert client.get(f"/api/cases/{case_id}/report").json() == reports[case_id]
            assert client.post(f"/api/cases/{case_id}/process").status_code == 200
            assert client.get(f"/api/cases/{case_id}/report").json() == reports[case_id]
    assert file_hashes(folder / "store") == hashes
    # Real production misconfiguration must fail closed, not run the demo worker.
    with running_server(folder, url, environment="production") as client:
        new = client.post("/api/cases", data={"question": CANARY}).json()["case_id"]
        client.post(f"/api/cases/{new}/artifacts", files={
            "file": ("synthetic.txt", b"Treatment Plan\nTooth 46: RCT", "text/plain")})
        client.post(f"/api/cases/{new}/process")
        assert client.get(f"/api/cases/{new}/report").status_code == 404
    log = (folder / "server.log").read_text(encoding="utf-8")
    assert CANARY not in log and HEADER_CANARY not in log
    assert "Treatment Plan" not in log and "Tooth " not in log
    assert url not in log and "Traceback" not in log
    events = [json.loads(line) for line in log.splitlines() if line.strip()]
    assert any(e["event"] == "http_response" for e in events)
    assert all(set(e) <= {"level", "event", "status"} for e in events)
    if os.environ.get("RC_EVIDENCE_DIR"):
        evidence = Path(os.environ["RC_EVIDENCE_DIR"])
        evidence.mkdir(parents=True, exist_ok=True)
        backend = "postgresql" if url.startswith("postgresql") else "sqlite"
        (evidence / f"{backend}-server.log").write_text(log, encoding="utf-8")
        (evidence / f"{backend}-runtime.json").write_text(json.dumps({
            "backend": backend, "data": "synthetic only", "simultaneous_cases": 5,
            "request_start_spread_seconds": round(max(r[0] for r in results) - min(r[0] for r in results), 4),
            "all_five_request_intervals_overlap": True,
            "isolated_assessments_and_reports": True, "persisted_files": len(hashes),
            "restart_report_and_file_equality": True, "reuse_after_restart": True,
            "production_mock_configuration_refused": True,
            "private_content_or_token_canaries_in_logs": False,
            "log_records_inspected": len(events)}, indent=2) + "\n", encoding="utf-8")


def test_sqlite_concurrent_cases_restart_and_logs(tmp_path):
    exercise(tmp_path, f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}")


def test_postgres_concurrent_cases_restart_and_logs(tmp_path, pg_url):
    migrate(pg_url)
    exercise(tmp_path, pg_url)
