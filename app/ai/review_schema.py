"""Versioned candidate firewall. References are traceability, not clinical truth."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.ai.preflight import failure

VERSION = 'multimodal-review-v3'


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_max_length=3000)


class Assertion(Strict):
    text: str = Field(min_length=1)
    source_refs: list[str] = Field(max_length=32)
    insufficient_support: bool


class Hypothesis(Strict):
    truth_type: Literal['MODEL_INFERRED'] = 'MODEL_INFERRED'
    label: str = Field(min_length=1, max_length=200)
    confidence_label: Literal['LOW', 'MEDIUM', 'HIGH']
    supporting_evidence_refs: list[str] = Field(max_length=32)
    contradicting_evidence_refs: list[str] = Field(max_length=32)
    missing_information: list[Assertion] = Field(max_length=20)
    recommended_checks: list[Assertion] = Field(max_length=20)
    insufficient_support: bool


class SourceRef(Strict):
    source_ref: str


class ReviewOutput(Strict):
    patient_summary: list[Assertion] = Field(max_length=6)
    professional_report: list[Assertion] = Field(max_length=20)
    diagnostic_hypotheses: list[Hypothesis] = Field(max_length=8)
    safety_red_flags: list[Assertion] = Field(max_length=20)
    limitations: list[Assertion] = Field(max_length=20)
    source_index: list[SourceRef] = Field(max_length=100)


def escalated_state(deterministic, flags):
    # Restricted states are not ordered against each other: none can be replaced.
    if deterministic in ('BLOCKED', 'MANUAL_REVIEW', 'URGENT_EVALUATION'):
        return deterministic
    return 'URGENT_EVALUATION' if flags else deterministic


def validate_review(raw, allowed_refs):
    output = ReviewOutput.model_validate(raw)
    allowed = set(allowed_refs)
    supplied = [s.source_ref for s in output.source_index]
    if len(supplied) != len(set(supplied)) or set(supplied) != allowed:
        raise failure('reference')
    assertions = [*output.patient_summary, *output.professional_report,
                  *output.safety_red_flags, *output.limitations]
    texts = []
    for hypothesis in output.diagnostic_hypotheses:
        refs = hypothesis.supporting_evidence_refs + hypothesis.contradicting_evidence_refs
        if not set(refs) <= allowed or (not hypothesis.supporting_evidence_refs and not hypothesis.insufficient_support):
            raise failure('reference')
        if set(hypothesis.supporting_evidence_refs) & set(hypothesis.contradicting_evidence_refs):
            raise failure('reference')
        assertions += hypothesis.missing_information + hypothesis.recommended_checks
        texts.append(hypothesis.label)
    for assertion in assertions:
        if not set(assertion.source_refs) <= allowed or (not assertion.source_refs and not assertion.insufficient_support):
            raise failure('reference')
        texts.append(assertion.text)
    # Defense in depth, not a clinical validator. Provider instructions and schema
    # constrain the task; these checks reject known prescription/overclaim forms.
    from app.pipeline.assessment import FORBIDDEN_PHRASES
    joined = ' '.join(texts).lower()
    for disclaimer in ('تشخیص قطعی نیست', 'not a definitive diagnosis', 'not a calibrated probability'):
        joined = joined.replace(disclaimer, '')
    forbidden = [*FORBIDDEN_PHRASES, 'definitive diagnosis', 'diagnosed with',
                 'take amoxicillin', 'take ibuprofen', 'prescribe', 'تشخیص قطعی',
                 'مصرف کنید', 'مصرف کن', 'قطع کنید', 'تجویز می', 'حتماً مبتلا', 'definitely have', 'you have pulpitis', 'you have periodontitis',
                 'start antibiotics', 'stop taking', 'take aspirin', 'undergo extraction',
                 'you need a root canal', 'you must take']
    numeric_confidence = re.search(
        r'(confidence|probability|likelihood|اطمینان|احتمال)[^.!?\n]{0,40}(?:[.,٫،]\s*)?\d|\d[\d.,٫/ ]*\s*(confidence|probability|احتمال|اطمینان)', joined)
    directive = re.search(
        r'\byou (?:have|are suffering from)\b|\b(?:take|start|stop|increase|decrease)\s+(?:\w+\s+){0,2}(?:antibiotics?|medication|aspirin|amoxicillin|ibuprofen|treatment)\b', joined)
    if numeric_confidence or directive or any(term in joined for term in forbidden) or re.search(r'\d\s*(%|٪|percent|درصد|mg\b|میلی.?گرم)', joined):
        raise failure('safety')
    return output
