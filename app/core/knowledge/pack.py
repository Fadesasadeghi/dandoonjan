"""Versioned Knowledge Pack boundary (Phase 8 / D-Q3).

Clinical evidence requirements come ONLY from here — never from model memory.
Keys are composite "<TREATMENT_ID>|<MODALITY>" so recommendation and necessity are
different propositions with (potentially) different requirements.
V0 ships a DEVELOPMENT pack explicitly marked NOT CLINICALLY VALIDATED.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import KnowledgePackStatus
from app.domain.models import KnowledgePack
from app.errors import KnowledgePackUnavailableError

DEVELOPMENT_PACK_VERSION = "kp-dev-v1.2.0-modality"
DEVELOPMENT_PACK_ID = "dandoonjan_dev_pack"

# Smallest DEVELOPMENT entries needed to prove routing and assessment (D-Q3).
# NOT CLINICALLY VALIDATED. RECOMMENDED entries intentionally share the same
# requirement shape as REQUIRED for now; separating them is clinical work that is
# explicitly out of scope.
_RCT_REQUIREMENTS = [
    {"gap_type": "CLINICAL_EXAMINATION", "importance": "HIGH"},
    {"gap_type": "SYMPTOM_HISTORY", "importance": "MEDIUM"},
    {"gap_type": "PULP_TEST_RESULT", "importance": "HIGH"},
    {"gap_type": "APPROPRIATE_RADIOGRAPH", "importance": "HIGH"},
]
_EXTRACTION_REQUIREMENTS = [
    {"gap_type": "CLINICAL_EXAMINATION", "importance": "HIGH"},
    {"gap_type": "APPROPRIATE_RADIOGRAPH", "importance": "HIGH"},
]

DEVELOPMENT_PACK: dict = {
    "treatment_modalities": {
        "TREATMENT_ROOT_CANAL|REQUIRED": {"required_evidence": _RCT_REQUIREMENTS},
        "TREATMENT_ROOT_CANAL|RECOMMENDED": {"required_evidence": _RCT_REQUIREMENTS},
        "TREATMENT_ROOT_CANAL|PLANNED": {"required_evidence": _RCT_REQUIREMENTS},
        "TREATMENT_EXTRACTION|REQUIRED": {"required_evidence": _EXTRACTION_REQUIREMENTS},
        "TREATMENT_EXTRACTION|RECOMMENDED": {"required_evidence": _EXTRACTION_REQUIREMENTS},
        "TREATMENT_EXTRACTION|PLANNED": {"required_evidence": _EXTRACTION_REQUIREMENTS},
        "TREATMENT_CROWN|RECOMMENDED": {
            "required_evidence": [{"gap_type": "TREATMENT_PLAN_ENTRY",
                                   "importance": "MEDIUM"}]},
        "TREATMENT_CROWN|PLANNED": {
            "required_evidence": [{"gap_type": "TREATMENT_PLAN_ENTRY",
                                   "importance": "MEDIUM"}]},
        "TREATMENT_FILLING|RECOMMENDED": {
            "required_evidence": [{"gap_type": "CLINICAL_EXAMINATION",
                                   "importance": "MEDIUM"},
                                  {"gap_type": "APPROPRIATE_RADIOGRAPH",
                                   "importance": "MEDIUM"}]},
        "TREATMENT_FILLING|PLANNED": {
            "required_evidence": [{"gap_type": "CLINICAL_EXAMINATION",
                                   "importance": "MEDIUM"},
                                  {"gap_type": "APPROPRIATE_RADIOGRAPH",
                                   "importance": "MEDIUM"}]},
    },
    "notes": "DEVELOPMENT PACK — NOT CLINICALLY VALIDATED. For demo/evaluation only. "
             "Keys are '<TREATMENT_ID>|<MODALITY>'; recommendation is not necessity.",
}


def seed_knowledge_pack(db: Session, version: str = DEVELOPMENT_PACK_VERSION,
                        content: dict | None = None) -> KnowledgePack:
    content = content or DEVELOPMENT_PACK
    pack = db.query(KnowledgePack).filter(
        KnowledgePack.knowledge_pack_id == DEVELOPMENT_PACK_ID,
        KnowledgePack.version == version).one_or_none()
    if pack:
        return pack
    pack = KnowledgePack(
        knowledge_pack_id=DEVELOPMENT_PACK_ID,
        version=version,
        status=KnowledgePackStatus.DEVELOPMENT,
        review_status="NOT_CLINICALLY_VALIDATED",
        content=content,
        active=True,
    )
    db.add(pack)
    db.flush()
    return pack


def get_active_pack(db: Session) -> KnowledgePack:
    settings = get_settings()
    pack = (db.query(KnowledgePack)
            .filter(KnowledgePack.active == True)  # noqa: E712
            .order_by(KnowledgePack.id.desc()).first())
    if pack is None:
        pack = seed_knowledge_pack(db)
    if settings.require_clinician_reviewed_knowledge_pack and \
            pack.status != KnowledgePackStatus.CLINICIAN_REVIEWED:
        raise KnowledgePackUnavailableError(
            "active knowledge pack is not clinician-reviewed; refusing to assess")
    return pack


def requirements_for(pack: KnowledgePack, treatment_id: str | None,
                     modality: str | None) -> list[dict] | None:
    """Requirements for a treatment+modality proposition; None when the pack has no
    rule (nothing may be invented)."""
    if not treatment_id or not modality:
        return None
    return pack.content.get("treatment_modalities", {}).get(f"{treatment_id}|{modality}")
