"""Versioned candidate firewall. References are traceability, not clinical truth."""
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.ai.preflight import failure

VERSION = 'multimodal-review-v4'


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


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).replace('\u200c', ' ').replace('ي','ی').replace('ك','ک').split()).lower()


def persian_narrative(text, *, label=False):
    # Narrative only: IDs/enums remain exact. Short technical abbreviations and
    # established dental tokens may coexist with Persian explanatory language.
    cleaned = re.sub(r'\b(?:TOOTH_\d+|src_[a-f0-9]+|OPG|CBCT|RCT|FDI|LOW|MEDIUM|HIGH|Mock|mm|pulpitis|periodontitis)\b', '', text, flags=re.I)
    letters = [c for c in cleaned if c.isalpha()]
    persian = [c for c in letters if '\u0600' <= c <= '\u06ff']
    if len(persian) < (3 if label else 8) or len(persian) < len(letters) * 0.5:
        raise failure('schema')
    if not label and len(set(re.findall(r'[^\W\d_]+', cleaned))) < 3:
        raise failure('schema')
    if not label and not set(re.findall(r'[^\W\d_]+', normalized(cleaned))) & {
            'است','نیست','برای','این','شده','که','در','نیازمند','با','باید','اما','هنوز','به','را'}:
        raise failure('schema')


def grounded_quote(assertion, context):
    """Sufficient-support narrative must be an attributed quote, not model inference."""
    if not context:
        return False
    sources = {s['source_ref']: s for s in context['sources']}
    text = {s['source_ref']: s['text'] for s in context.get('text', [])}
    quotes = re.findall('«([^»]+)»', assertion.text)
    frame = normalized(assertion.text)
    kind = ('PATIENT_REPORTED' if 'به گفته شما' in frame else
            'CLINICIAN_REPORTED' if 'به روایت' in frame else
            'DOCUMENT_EXTRACTED' if 'در متن سند' in frame else None)
    outside = normalized(re.sub('«[^»]*»', '', assertion.text)).strip(' :؛،.!؟')
    if outside not in ('به گفته شما', 'به روایت', 'در متن سند'):
        return False
    return bool(kind and quotes and assertion.source_refs and all(
        any(sources.get(ref, {}).get('kind') == kind and quote in text.get(ref, '')
            for ref in assertion.source_refs) for quote in quotes) and all(
        sources.get(ref, {}).get('kind') == kind and any(quote in text.get(ref, '') for quote in quotes)
        for ref in assertion.source_refs))


def validate_review(raw, allowed_refs, *, source_context=None):
    output = ReviewOutput.model_validate(raw)
    ordered = list(allowed_refs)
    allowed = set(ordered)
    if len(ordered) != len(allowed):
        raise failure('reference')
    supplied = [s.source_ref for s in output.source_index]
    if len(supplied) != len(set(supplied)) or set(supplied) != allowed:
        raise failure('reference')
    assertions = [*output.patient_summary, *output.professional_report,
                  *output.safety_red_flags, *output.limitations]
    texts = []
    for hypothesis in output.diagnostic_hypotheses:
        refs = hypothesis.supporting_evidence_refs + hypothesis.contradicting_evidence_refs
        if not set(refs) <= allowed or len(refs) != len(set(refs)) or (not hypothesis.supporting_evidence_refs and not hypothesis.insufficient_support):
            raise failure('reference')
        if set(hypothesis.supporting_evidence_refs) & set(hypothesis.contradicting_evidence_refs):
            raise failure('reference')
        if source_context:
            context = {s['source_ref']: s for s in source_context['sources']}
            if any(context.get(ref, {}).get('clinical_use') == 'NON_CLINICAL' for ref in refs):
                raise failure('reference')
        assertions += hypothesis.missing_information + hypothesis.recommended_checks
        texts.append(hypothesis.label)
    for assertion in assertions:
        if not set(assertion.source_refs) <= allowed or len(assertion.source_refs) != len(set(assertion.source_refs)) or (not assertion.source_refs and not assertion.insufficient_support):
            raise failure('reference')
        if not assertion.insufficient_support and not grounded_quote(assertion, source_context):
            raise failure('reference')
        if source_context and any(s.get('partial') for s in source_context['sources']):
            claim = normalized(assertion.text)
            if re.search(r'(کل متن|تمام متن|متن کامل).{0,40}(بررسی|خوانده|ارسال)', claim) and not any(
                    token in claim for token in ('نشده','نیست','نمی','نه ')):
                raise failure('reference')
        if source_context and any(s['source_ref'] in assertion.source_refs and
                s.get('clinical_use') == 'NON_CLINICAL' for s in source_context['sources']):
            claim = normalized(assertion.text)
            # The application-owned pattern may be described as transport data,
            # never as a clinical image, even with a low-confidence marker.
            if re.search(r'رادیوگرافی|پوسیدگی|التهاب پالپ|عفونت|بیماری', claim) and not any(
                    token in claim for token in ('نیست','نمی','نشده','غیر بالینی')):
                raise failure('safety')
        if re.search(r'\bsrc_[a-zA-Z0-9_]+\b|\b(?:CASE|ART)-[a-zA-Z0-9]+', assertion.text):
            raise failure('reference')
        texts.append(assertion.text)
    # Defense in depth, not a clinical validator. Provider instructions and schema
    # constrain the task; these checks reject known prescription/overclaim forms.
    from app.pipeline.assessment import FORBIDDEN_PHRASES
    joined = normalized(' '.join(texts))
    for disclaimer in ('تشخیص قطعی نیست', 'not a definitive diagnosis', 'not a calibrated probability'):
        joined = joined.replace(disclaimer, '')
    forbidden = [*FORBIDDEN_PHRASES, 'definitive diagnosis', 'diagnosed with',
                 'take amoxicillin', 'take ibuprofen', 'prescribe', 'تشخیص قطعی',
                 'مصرف کنید', 'مصرف کن', 'قطع کنید', 'تجویز می', 'حتماً مبتلا', 'definitely have', 'you have pulpitis', 'you have periodontitis',
                 'start antibiotics', 'stop taking', 'take aspirin', 'undergo extraction',
                 'you need a root canal', 'you must take']
    confidence_text = re.sub(r'دندان\s*[0-9۰-۹٠-٩]+', '', joined)
    numeric_confidence = re.search(
        r'(confidence|probability|likelihood|اطمینان|احتمال)(?![^\W\d_])[^.!?\n]{0,40}(?:[.,٫،]\s*)?\d|\d[\d.,٫/ ]*\s*(confidence|probability|احتمال|اطمینان)', confidence_text)
    directive = re.search(
        r'\byou (?:have|are suffering from)\b|\b(?:take|start|stop|increase|decrease)\s+(?:\w+\s+){0,2}(?:antibiotics?|medication|aspirin|amoxicillin|ibuprofen|treatment)\b', joined)
    authority = re.search(r'قطع[اًی]+\s+به|نتیجه\s+تضمینی|نادیده\s+بگیرید|باید\s+کشیده|(?:التهاب پالپ|پوسیدگی|عفونت)\s+قطعی\s+است', joined)
    # Narrow unqualified diagnosis forms; cautious hypotheses and reported
    # history remain valid. This is not clinical semantic entailment.
    for text in texts:
        claim = normalized(text)
        if not any(token in claim for token in ('احتمال','ممکن','نیست','نمی','نشده','به گفته','به روایت','در متن سند')) and (
                re.search(r'شما.{0,35}(?:التهاب پالپ|پوسیدگی|عفونت).{0,15}دارید', claim) or
                re.search(r'(?:تصویر|رادیوگرافی).{0,65}(?:التهاب پالپ|پوسیدگی|عفونت).{0,20}(?:وجود دارد|دیده می شود|است)', claim)):
            raise failure('safety')
    if numeric_confidence or directive or authority or any(normalized(term) in joined for term in forbidden) or re.search(r'\d\s*(%|٪|percent|درصد|mg\b|میلی.?گرم)', joined):
        raise failure('safety')
    # Validate by field role, never by equality with a label. A short label
    # repeated in a summary still has to satisfy the full narrative contract.
    for assertion in assertions:
        persian_narrative(assertion.text)
    for hypothesis in output.diagnostic_hypotheses:
        persian_narrative(hypothesis.label, label=True)
        if not hypothesis.missing_information or not hypothesis.recommended_checks:
            raise failure('schema')
    if not output.patient_summary or not output.professional_report or not output.limitations:
        raise failure('schema')
    limits = normalized(' '.join(a.text for a in output.limitations))
    if 'تشخیص' not in limits or not any(token in limits for token in ('نیست','نمی','تأیید نشده')):
        raise failure('schema')
    if not any(token in limits for token in ('نیازمند','لازم','باید')) or not any(token in limits for token in ('دندان پزشک','دندانپزشک')):
        raise failure('schema')
    for section in (output.patient_summary, output.professional_report):
        if allowed and not any(a.source_refs for a in section):
            raise failure('reference')
        if all(normalized(a.text).startswith('این گزارش تشخیص') for a in section):
            raise failure('schema')
    output.source_index = [SourceRef(source_ref=ref) for ref in ordered]
    return output
