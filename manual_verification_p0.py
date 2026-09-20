"""Manual executable verification for P0.1 scenarios (locked decisions).

Run: python manual_verification_p0.py
Covers: A (claim semantics + no circular evidence), B (idempotent rerun),
C (malicious TOOTH_900 + retry D1), D (manual review fail-closed),
E (snapshot tampering), F (multi-tooth no cartesian), G (revision isolation),
H (safety before early exit).
"""
import os
import pymupdf

os.environ["DJ_DATABASE_URL"] = "sqlite://"
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
import app.domain.models
from app.db import Base

engine = create_engine("sqlite://")
Base.metadata.create_all(engine)
db = sessionmaker(bind=engine, expire_on_commit=False)()

from app.domain.enums import DerivationStatus
from app.domain.models import (Assessment, AssessmentSnapshot, Case, Claim,
                               EvidenceLink, ProcessingRun, Report, User, public_id)
from app.core.artifacts.ingestion import ingest_artifact
from app.pipeline import orchestrator as orc
from app.ai.gateway import ModelGateway


def pdf(text):
    doc = pymupdf.open(); p = doc.new_page(); p.insert_text((72, 72), text)
    data = doc.tobytes(); doc.close(); return data


def new_case(q="", rec=""):
    u = User(public_id=public_id("USR")); db.add(u); db.flush()
    c = Case(public_id=public_id("CASE"), user_id=u.id, question_text=q,
             dentist_recommendation_text=rec)
    db.add(c); db.flush(); return c


def rct_claims(case):
    return db.query(Claim).filter(
        Claim.case_id == case.id, Claim.claim_type == "TREATMENT",
        Claim.treatment_id == "TREATMENT_ROOT_CANAL").all()


results = []

# Scenario A: clinician says RCT; plan mentions RCT; no clinical evidence
c = new_case("آیا دندان 46 باید عصب‌کشی شود؟", "دکتر گفت عصب کشی لازم است")
ingest_artifact(db, c, filename="plan.pdf", declared_mime="application/pdf",
                data=pdf("Treatment Plan\nTooth 46: RCT"))
r = orc.run_case_pipeline(db, c)
cl = [x for x in rct_claims(c) if x.source_type.value == "CLINICIAN_REPORTED"]
assert cl and cl[0].modality.value in ("RECOMMENDED", "REQUIRED")
asm = db.query(Assessment).filter(Assessment.claim_id == cl[0].id).one()
links = db.query(EvidenceLink).filter(EvidenceLink.claim_id == cl[0].id).all()
assert all(l.relationship_type.value != "SUPPORTS" for l in links)
a_ok = (asm.status.value == "INSUFFICIENT_EVIDENCE"
        and r["status"] == "REPORT_READY"
        and r["report_kind"] == "STANDARD")
results.append(("A", "clinician claim assessed (modality preserved); plan mention "
                     f"!= necessity; assessment={asm.status.value}", a_ok))

# Scenario B: identical case processed twice — reuse, no new derivation
r2 = orc.run_case_pipeline(db, c)
n_pipeline_runs = db.query(ProcessingRun).filter(
    ProcessingRun.case_id == c.id, ProcessingRun.module == "pipeline").count()
b_ok = (r2.get("reused") is True and n_pipeline_runs == 1
        and r2.get("report_kind") == "STANDARD")
results.append(("B", f"second run reused={r2.get('reused')}, pipeline runs="
                     f"{n_pipeline_runs}, contract has report_kind", b_ok))

# Scenario C: malicious provider emits TOOTH_900
class Malicious:
    name = "malicious"
    def run(self, prompt, content, params):
        if prompt.prompt_id == "claim_builder":
            return {"claims": [{"claim_type": "TREATMENT", "subject": "TOOTH_900",
                                "predicate": "REQUIRES_TREATMENT",
                                "object_value": "TREATMENT_ROOT_CANAL",
                                "treatment": "TREATMENT_ROOT_CANAL",
                                "modality": "REQUIRED", "confidence": 0.9}]}
        from app.ai.providers import MockProvider
        return MockProvider().run(prompt, content, params)
class GWBad(ModelGateway):
    def __init__(self, db_):
        super().__init__(db_); self.provider = Malicious()

c2 = new_case("دندان 18 چی؟", "کشیدن لازم است")
ingest_artifact(db, c2, filename="plan.pdf", declared_mime="application/pdf",
                data=pdf("Treatment Plan\nTooth 18: extraction"))
orc.ModelGateway = GWBad
r3 = orc.run_case_pipeline(db, c2)
orc.ModelGateway = ModelGateway
bad = db.query(Claim).filter(Claim.subject == "TOOTH_900").all()
c_ok = (not bad and r3["status"] == "FAILED")
results.append(("C", f"TOOTH_900 rejected before persistence (bad rows={len(bad)}, "
                     f"case status={r3['status']})", c_ok))

# Scenario C2: retry after failure with same input succeeds (D1)
rs = orc.run_case_pipeline(db, c2)
attempts = sorted(p.attempt for p in db.query(ProcessingRun).filter(
    ProcessingRun.case_id == c2.id, ProcessingRun.module == "pipeline").all())
c2_ok = (rs["status"] == "REPORT_READY" and attempts == [1, 2])
results.append(("C2", f"retry succeeded, attempts={attempts}, no IntegrityError", c2_ok))

# Scenario D: manual review triggered (low-confidence extraction) -> review-pending
class LowConf:
    name = "low_conf"
    def run(self, prompt, content, params):
        from app.ai.providers import MockProvider
        out = MockProvider().run(prompt, content, params)
        if prompt.prompt_id in ("treatment_plan_extractor", "invoice_extractor"):
            out = dict(out)
            out["fields"] = [{**f, "confidence": 0.3} for f in out["fields"]]
            out["treatment_items"] = [{**i, "confidence": 0.3}
                                      for i in out.get("treatment_items", [])]
        return out
class GW2(ModelGateway):
    def __init__(self, db_):
        super().__init__(db_); self.provider = LowConf()
orc.ModelGateway = GW2
c3 = new_case("دندان 46 چی؟", "عصب کشی لازم است")
ingest_artifact(db, c3, filename="plan.pdf", declared_mime="application/pdf",
                data=pdf("Treatment Plan\nTooth 46: RCT"))
r4 = orc.run_case_pipeline(db, c3)
orc.ModelGateway = ModelGateway
rep = db.query(Report).filter(Report.case_id == c3.id).one()
d_ok = (r4["report_kind"] == "REVIEW_PENDING"
        and rep.content["report_kind"] == "REVIEW_PENDING"
        and c3.status.value == "MANUAL_REVIEW_REQUIRED")
results.append(("D", "manual review -> review-pending report only, "
                     f"case={c3.status.value}", d_ok))

# Scenario E: snapshot mutation + tamper detection
c4 = new_case("سوال", "عصب کشی لازم است")
ingest_artifact(db, c4, filename="plan.pdf", declared_mime="application/pdf",
                data=pdf("Treatment Plan\nTooth 46: RCT"))
orc.run_case_pipeline(db, c4)
from app.governance.immutability import (ImmutabilityViolationError,
                                         verify_snapshot_integrity)
snap = db.query(AssessmentSnapshot).filter(AssessmentSnapshot.case_id == c4.id).one()
mutation_rejected = False
try:
    snap.payload["question"] = "hacked"
    db.flush()
except ImmutabilityViolationError:
    mutation_rejected = True
db.rollback()
delete_rejected = False
try:
    db.delete(snap)
    db.flush()
except ImmutabilityViolationError:
    delete_rejected = True
db.rollback()
db.execute(update(AssessmentSnapshot).where(AssessmentSnapshot.id == snap.id)
           .values(payload={"question": "tampered"}))
db.commit()
db.expire_all()
snap2 = db.query(AssessmentSnapshot).filter(AssessmentSnapshot.case_id == c4.id).one()
tamper_detected = verify_snapshot_integrity(snap2) is False
e_ok = (mutation_rejected and delete_rejected and tamper_detected)
results.append(("E", f"ORM mutation rejected={mutation_rejected}, DELETE rejected="
                     f"{delete_rejected}, DB tamper detected={tamper_detected}", e_ok))

# Scenario F: multi-tooth document — no cartesian claims (D-Q2)
c5 = new_case("چند دندان مشکل دارند؟", "")
ingest_artifact(db, c5, filename="plan.pdf", declared_mime="application/pdf",
                data=pdf("Treatment Plan\nTooth 46: RCT\nTooth 36: Filling"))
r5 = orc.run_case_pipeline(db, c5)
pairs = {(x.subject, x.treatment_id) for x in db.query(Claim).filter(
    Claim.case_id == c5.id, Claim.claim_type == "TREATMENT",
    Claim.source_type == "DOCUMENT_EXTRACTED").all()}
f_ok = (pairs == {("TOOTH_46", "TREATMENT_ROOT_CANAL"),
                  ("TOOTH_36", "TREATMENT_FILLING")})
results.append(("F", f"atomic pairs only: {sorted(pairs)}", f_ok))

# Scenario G: revision isolation — changed input replaces ACTIVE set (D-Q1)
c6 = new_case("آیا دندان 46 باید عصب‌کشی شود؟", "دکتر گفت عصب کشی لازم است")
ingest_artifact(db, c6, filename="plan.pdf", declared_mime="application/pdf",
                data=pdf("Treatment Plan\nTooth 46: RCT"))
orc.run_case_pipeline(db, c6)
v1_claims = db.query(Claim).filter(Claim.case_id == c6.id).count()
c6.question_text = "بررسی مجدد: کشیدن لازم است؟"
c6.dentist_recommendation_text = "دکتر گفت کشیدن لازم است"
c6.version += 1
db.commit()
orc.run_case_pipeline(db, c6)
active_now = db.query(Claim).filter(
    Claim.case_id == c6.id,
    Claim.derivation_status == DerivationStatus.ACTIVE).count()
superseded = db.query(Claim).filter(
    Claim.case_id == c6.id,
    Claim.derivation_status == DerivationStatus.SUPERSEDED).count()
g_ok = (active_now <= v1_claims and superseded >= v1_claims)
results.append(("G", f"revision rerun: active={active_now}, superseded={superseded}, "
                     "no accumulation", g_ok))

# Scenario H: safety runs even with no usable artifacts (D3)
c7 = new_case("خونریزی شدید دارم و تورم صورت دارم", "")
ingest_artifact(db, c7, filename="blank.pdf", declared_mime="application/pdf",
                data=pdf(""))
r7 = orc.run_case_pipeline(db, c7)
h_ok = (r7["status"] == "NEEDS_MORE_EVIDENCE"
        and r7["safety_state"] == "URGENT_EVALUATION"
        and r7["report_kind"] == "URGENT")
results.append(("H", f"urgent screened with no artifacts: status={r7['status']}, "
                     f"safety={r7['safety_state']}", h_ok))

print()
all_ok = True
for sid, msg, ok in results:
    print(f"Scenario {sid}: {'PASS' if ok else 'FAIL'} - {msg}")
    all_ok &= ok
print("\nALL SCENARIOS:", "PASS" if all_ok else "FAIL")
raise SystemExit(0 if all_ok else 1)
