"""Versioned, independently editable intake. Completeness is not clinical adequacy."""
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import object_session
from app.domain.models import DossierRevision, public_id
from app.pipeline.runs import lock_case

FIELDS = ('symptoms', 'duration', 'medical_history', 'medications', 'allergies',
          'treatment_plan', 'previous_reports', 'previous_treatments')


class DossierPatch(BaseModel):
    model_config = ConfigDict(extra='forbid', str_max_length=10000)
    symptoms: str | None = None
    duration: str | None = None
    medical_history: str | None = None
    medications: str | None = None
    allergies: str | None = None
    treatment_plan: str | None = None
    previous_reports: str | None = None
    previous_treatments: str | None = None


def latest(case):
    db = object_session(case)
    return db.query(DossierRevision).filter_by(case_id=case.id).order_by(DossierRevision.id.desc()).first() if db else None


def fields(case):
    revision = latest(case)
    return {name: getattr(revision, name, '') for name in FIELDS}


def presentation(case):
    values = fields(case)
    missing = [key for key, value in values.items()
               if value.strip().lower() in ('', 'unknown', 'نامشخص', 'نمی‌دانم', 'نمی دانم')]
    if not case.question_text.strip():
        missing.append('main_question')
    if not any(a.detected_mime_type.startswith('image/') for a in case.artifacts):
        missing.append('dental_images')
    return {'fields': values, 'case_version': case.version,
            'missing_information': missing, 'clinical_adequacy': 'NOT_EVALUATED'}


def update(db, case, patch):
    lock_case(db, case.id)
    db.refresh(case)
    values = fields(case)
    updated = {**values, **{k: v.strip() for k, v in patch.model_dump(exclude_none=True).items()}}
    if updated != values or latest(case) is None:
        case.version += 1
        db.add(DossierRevision(public_id=public_id('DSR'), case_id=case.id,
                               case_version=case.version, **updated))
        db.flush()
    return presentation(case)
