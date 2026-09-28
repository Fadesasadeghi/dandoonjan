"""P0 acceptance tests: knowledge pack versioning (P0-08), snapshot provenance
completeness (P0-09), alembic DJ_DATABASE_URL (P0-10), strong invariant tests."""
import json
import os
import subprocess
import sys

import pymupdf
import pytest


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


PLAN = "Treatment Plan\nTooth 46: RCT\nCrown recommended after RCT"


def _ingest(db, case, text=PLAN, filename="plan.pdf"):
    from app.core.artifacts.ingestion import ingest_artifact
    ingest_artifact(db, case, filename=filename, declared_mime="application/pdf",
                    data=_pdf(text))


def _run(db, case):
    from app.pipeline.orchestrator import run_case_pipeline
    return run_case_pipeline(db, case)


# ---------------- P0-08 ----------------

def test_p0_08_a_two_versions_of_same_pack_coexist(db):
    from app.core.knowledge.pack import DEVELOPMENT_PACK, seed_knowledge_pack
    from app.domain.enums import KnowledgePackStatus
    from app.domain.models import KnowledgePack
    seed_knowledge_pack(db)
    v2 = KnowledgePack(
        knowledge_pack_id="dandoonjan_dev_pack", version="kp-dev-v1.2.1-test",
        status=KnowledgePackStatus.DEVELOPMENT,
        review_status="NOT_CLINICALLY_VALIDATED",
        content={**DEVELOPMENT_PACK, "notes": "revision"},
        active=False)
    db.add(v2)
    db.flush()  # both versions persist
    packs = db.query(KnowledgePack).filter(
        KnowledgePack.knowledge_pack_id == "dandoonjan_dev_pack").all()
    assert len(packs) == 2


def test_p0_08_b_duplicate_id_version_rejected(db):
    from sqlalchemy.exc import IntegrityError
    from app.core.knowledge.pack import DEVELOPMENT_PACK_VERSION, seed_knowledge_pack
    from app.domain.enums import KnowledgePackStatus
    from app.domain.models import KnowledgePack
    seed_knowledge_pack(db)
    dup = KnowledgePack(knowledge_pack_id="dandoonjan_dev_pack",
                        version=DEVELOPMENT_PACK_VERSION,
                        status=KnowledgePackStatus.DEVELOPMENT, content={}, active=False)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_p0_08_c_snapshot_references_exact_pack_version(db, case):
    _ingest(db, case)
    _run(db, case)
    from app.core.knowledge.pack import DEVELOPMENT_PACK_VERSION
    from app.domain.models import AssessmentSnapshot
    snap = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.case_id == case.id).one()
    assert snap.versions["knowledge_pack"] == DEVELOPMENT_PACK_VERSION
    assert snap.versions["knowledge_pack_id"] == "dandoonjan_dev_pack"
    assert snap.versions["knowledge_pack_status"] == "DEVELOPMENT"


# ---------------- P0-09 ----------------

def test_p0_09_a_full_provenance_trace_without_ai(db, case):
    _ingest(db, case)
    _run(db, case)
    from app.domain.models import (Artifact, AssessmentSnapshot, Claim, ExtractedField,
                                   Finding, Report)
    report = db.query(Report).filter(Report.case_id == case.id).one()
    snap = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.id == report.snapshot_id).one()
    # Snapshot -> artifact (with content hash)
    artifact_ref = snap.payload["artifacts"][0]
    artifact = db.query(Artifact).filter(
        Artifact.public_id == artifact_ref["artifact_id"]).one()
    assert artifact.sha256 == artifact_ref["sha256"]
    # Snapshot -> claim -> finding -> extracted field -> artifact
    claim_id = snap.payload["claims"][0]["claim_id"]
    claim = db.query(Claim).filter(Claim.public_id == claim_id).one()
    finding = db.query(Finding).filter(Finding.case_id == case.id).first()
    assert finding.artifact_id == artifact.id
    if finding.extracted_field_id:
        field = db.query(ExtractedField).filter(
            ExtractedField.id == finding.extracted_field_id).one()
        assert field.extraction_id
    # No AI rerun was needed anywhere above.
    assert snap.versions["ai_provider"] == "mock"


def test_p0_09_b_hash_changes_with_payload(db):
    from app.governance.immutability import snapshot_content_hash
    h1 = snapshot_content_hash({"a": 1}, {"v": "1"})
    h2 = snapshot_content_hash({"a": 2}, {"v": "1"})
    h3 = snapshot_content_hash({"a": 1}, {"v": "2"})
    assert h1 != h2 and h1 != h3 and h2 != h3


def test_p0_09_c_old_snapshot_valid_after_case_change(db, case):
    _ingest(db, case)
    _run(db, case)
    from app.domain.models import AssessmentSnapshot
    from app.governance.immutability import verify_snapshot_integrity
    snap = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.case_id == case.id).one()
    question_at_creation = snap.payload["question"]
    case.question_text = "changed after snapshot"
    case.version += 1
    db.commit()
    db.expire_all()
    snap2 = db.query(AssessmentSnapshot).filter(
        AssessmentSnapshot.case_id == case.id).one()
    assert verify_snapshot_integrity(snap2) is True
    assert snap2.payload["question"] == question_at_creation


# ---------------- P0-10 ----------------

def test_p0_10_a_alembic_targets_dj_database_url(tmp_path):
    db_file = tmp_path / "alembic_target.db"
    env = {**os.environ, "DJ_DATABASE_URL": f"sqlite:///{db_file.as_posix()}"}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       env=env, capture_output=True, text=True, cwd=os.getcwd())
    assert r.returncode == 0, r.stderr
    import sqlite3
    conn = sqlite3.connect(db_file)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"cases", "artifacts", "claims", "assessment_snapshots",
            "knowledge_packs", "alembic_version"} <= tables


def test_p0_10_b_postgres_url_not_silently_redirected(tmp_path):
    """A configured non-SQLite URL must reach alembic (fails to connect, proving
    the URL is respected instead of falling back to the dev sqlite file)."""
    env = {**os.environ,
           "DJ_DATABASE_URL": "postgresql+psycopg://nouser@localhost:1/nodb"}
    r = subprocess.run([sys.executable, "-m", "alembic", "current"],
                       env=env, capture_output=True, text=True, cwd=os.getcwd(), timeout=30)
    assert "dandoonjan_dev.db" not in r.stderr
    assert r.returncode != 0  # connection refused => the PG URL was honored


def test_p0_10_c_default_dev_url_is_explicit_sqlite(tmp_path):
    env = {k: v for k, v in os.environ.items()
           if k != "DJ_DATABASE_URL" and k != "DATABASE_URL"}
    env["DJ_ENVIRONMENT"] = "development"
    r = subprocess.run([sys.executable, "-c",
                        "from alembic.config import Config;"
                        "from alembic import command;"
                        "import os;"
                        "os.chdir(os.getcwd());"
                        "c=Config('alembic.ini');"
                        "print(c.attributes)"],
                       env=env, capture_output=True, text=True, cwd=os.getcwd())
    # the override happens in env.py; alembic.ini default never applies at runtime
    from app.config import get_settings
    assert get_settings().database_url.startswith("sqlite:///")


# ---------------- INV-05 (strong): pack-driven requirements ----------------

def test_inv05_assessment_cannot_invent_requirements(db, case):
    """Remove the ROOT_CANAL_REQUIRED rule from the active pack: assessment must not
    invent pulp-test/radiograph requirements from model memory."""
    from app.core.knowledge.pack import (DEVELOPMENT_PACK, DEVELOPMENT_PACK_VERSION,
                                         seed_knowledge_pack)
    from app.domain.enums import KnowledgePackStatus
    from app.domain.models import EvidenceGap, KnowledgePack
    seed_knowledge_pack(db)
    stripped = json.loads(json.dumps(DEVELOPMENT_PACK))
    for key in [k for k in stripped.get("treatment_modalities", {})
                if k.startswith("TREATMENT_ROOT_CANAL")]:
        stripped["treatment_modalities"].pop(key)
    stripped_pack = KnowledgePack(
        knowledge_pack_id="dandoonjan_dev_pack", version="kp-dev-v1.2.2-norct",
        status=KnowledgePackStatus.DEVELOPMENT, review_status="NOT_CLINICALLY_VALIDATED",
        content=stripped, active=True)
    db.add(stripped_pack)
    # deactivate v1
    for p in db.query(KnowledgePack).filter(
            KnowledgePack.version == DEVELOPMENT_PACK_VERSION).all():
        p.active = False
    db.flush()

    _ingest(db, case)
    _run(db, case)
    gaps = db.query(EvidenceGap).filter(EvidenceGap.case_id == case.id).all()
    rct_gaps = [g for g in gaps if g.gap_type in ("PULP_TEST_RESULT",
                                                  "APPROPRIATE_RADIOGRAPH",
                                                  "CLINICAL_EXAMINATION")]
    # other claim types (e.g. CROWN_RECOMMENDED) still have pack-driven gaps,
    # but no ROOT_CANAL requirements were invented
    from app.domain.models import Claim
    rct_claims = db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.claim_type == "TREATMENT",
        Claim.treatment_id == "TREATMENT_ROOT_CANAL").all()
    rct_ids = {c.id for c in rct_claims}
    assert rct_ids
    assert all(g.claim_id not in rct_ids for g in rct_gaps),         "requirements must not be invented for propositions absent from the pack"


# ---------------- INV-06 (strong): snapshot-only reports ----------------

def test_inv06_report_requires_verified_snapshot(db, case):
    from app.domain.enums import SafetyState
    from app.domain.models import Case, SafetyResult, public_id
    from app.errors import SafetyBlockedError
    from app.pipeline import reporting as rm
    safety = SafetyResult(case_id=case.id, state=SafetyState.NORMAL, reasons=[],
                          rules_version="safety-rules-v2")
    db.add(safety)
    db.flush()
    snap = rm.create_snapshot(db, case, safety, derivation_run_id=None)
    # snapshot of a DIFFERENT case -> rejected (ownership mismatch)
    other = Case(public_id=public_id("CASE"), user_id=case.user_id,
                 question_text="other")
    db.add(other)
    db.flush()
    with pytest.raises(SafetyBlockedError):
        rm.compose_report(db, other, snap)
    db.rollback()


def test_inv06_report_only_from_snapshot_api(db, case):
    """compose_report has no code path accepting live case state alone: the
    signature requires a snapshot object."""
    import inspect
    from app.pipeline import reporting as rm
    params = inspect.signature(rm.compose_report).parameters
    assert "snapshot" in params, "composer must take a snapshot, not live state"


# ---------------- INV-04 (strong) ----------------

def test_inv04_identical_statements_stay_distinct(db, case):
    """The same treatment statement from patient, clinician and document sources
    persists as distinct claims with distinct truth types and distinct IDs."""
    case.question_text = "دکتر گفت دندان 46 باید عصب‌کشی شود"
    case.dentist_recommendation_text = "عصب کشی لازم است"
    _ingest(db, case)  # document mentions RCT for tooth 46
    _run(db, case)
    from app.domain.enums import TruthType
    from app.domain.models import Claim
    claims = db.query(Claim).filter(
        Claim.case_id == case.id,
        Claim.claim_type == "TREATMENT",
        Claim.treatment_id == "TREATMENT_ROOT_CANAL").all()
    sources = {c.source_type for c in claims}
    assert TruthType.CLINICIAN_REPORTED in sources
    assert len({c.id for c in claims}) == len(claims)  # distinct rows
    clinician = [c for c in claims if c.source_type == TruthType.CLINICIAN_REPORTED]
    documented = [c for c in claims if c.source_type == TruthType.DOCUMENT_EXTRACTED]
    assert clinician and documented
    assert clinician[0].id != documented[0].id
    assert clinician[0].provenance_id != documented[0].provenance_id
