"""Domain + ontology + state machine unit tests."""


def test_truth_types_exist():
    from app.domain.enums import TruthType
    assert {t.value for t in TruthType} >= {
        "PATIENT_REPORTED", "CLINICIAN_REPORTED", "DOCUMENT_EXTRACTED",
        "MODEL_INFERRED", "CLINICAL_KNOWLEDGE", "SYSTEM_DERIVED"}


def test_claim_vs_finding_distinct_entities():
    from app.domain.models import Claim, Finding
    assert Claim.__tablename__ != Finding.__tablename__


def test_tooth_normalization_fa():
    from app.core.ontology.ontology import normalize_tooth
    assert normalize_tooth("دندان ۶ پایین راست") == "TOOTH_46"
    assert normalize_tooth("46") == "TOOTH_46"
    assert normalize_tooth("lower right first molar") == "TOOTH_46"
    assert normalize_tooth("tooth 900") is None


def test_tooth_900_rejected_by_ontology():
    import pytest
    from app.core.ontology.ontology import OntologyValidationError, validate_tooth
    with pytest.raises(OntologyValidationError):
        validate_tooth("TOOTH_900")


def test_treatment_normalization():
    from app.core.ontology.ontology import normalize_treatment
    assert normalize_treatment("عصب کشی") == "TREATMENT_ROOT_CANAL"
    assert normalize_treatment("RCT") == "TREATMENT_ROOT_CANAL"
    assert normalize_treatment("root canal") == "TREATMENT_ROOT_CANAL"


def test_invalid_transitions_rejected(case):
    import pytest
    from app.core.cases.state_machine import transition
    from app.domain.enums import CaseStatus
    from app.errors import InvalidTransitionError
    with pytest.raises(InvalidTransitionError):
        transition(case, CaseStatus.REPORT_READY)


def test_state_machine_happy_path(case):
    from app.core.cases.state_machine import transition
    from app.domain.enums import CaseStatus
    transition(case, CaseStatus.INTAKE_COMPLETE)
    transition(case, CaseStatus.PROCESSING)
    transition(case, CaseStatus.READY_FOR_ASSESSMENT)
    transition(case, CaseStatus.ASSESSED)
    transition(case, CaseStatus.REPORT_READY)
    assert case.status == CaseStatus.REPORT_READY


def test_knowledge_pack_is_versioned_and_unvalidated(db):
    from app.core.knowledge.pack import get_active_pack
    pack = get_active_pack(db)
    assert pack.version
    assert pack.status.value == "DEVELOPMENT"
    assert pack.review_status == "NOT_CLINICALLY_VALIDATED"
    assert "NOT CLINICALLY VALIDATED" in pack.content["notes"]


def test_knowledge_pack_production_gate():
    import os
    os.environ["DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK"] = "true"
    from app.config import get_settings
    get_settings.cache_clear()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.domain.models  # noqa
    from app.db import Base
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        import pytest
        from app.core.knowledge.pack import get_active_pack
        from app.errors import KnowledgePackUnavailableError
        with pytest.raises(KnowledgePackUnavailableError):
            get_active_pack(db)
    finally:
        db.close()
        os.environ.pop("DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK")
        get_settings.cache_clear()
