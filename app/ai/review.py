"""Candidate review behind ModelGateway; durable content-free failure audit."""
import time
from app.ai.multimodal import bundle, provider_bundle, resolve_review
from app.ai.review_schema import VERSION, validate_review
from app.core.cases.dossier import latest, presentation
from app.domain.models import ReviewRun, DiagnosticHypothesis, HypothesisEvidence, public_id
from app.errors import ExtractionValidationError
from app.core.cases.sample import is_demo, DEMO_VERSION

MISSING_LABELS = {'symptoms':'علائم', 'duration':'مدت علائم', 'medical_history':'سابقه پزشکی',
    'medications':'داروها', 'allergies':'حساسیت‌ها', 'treatment_plan':'طرح درمان',
    'previous_reports':'گزارش قبلی', 'previous_treatments':'درمان قبلی', 'dental_images':'تصویر دندان'}


def demo_review(db, case, derivation_run_id, data, missing):
    """Render recorded facts/rule results; never interpret pixels or assess anew."""
    from app.core.cases.dossier import fields
    from app.domain.models import (Assessment, Claim, EvidenceGap, Finding,
                                   TreatmentItem, Extraction, Artifact, SafetyResult)
    from app.pipeline.reporting import GAP_FA, STATUS_FA, MODALITY_FA, SAFETY_NOTE_FA
    from app.api.presentation import TREATMENTS_FA, SOURCES_FA

    def scoped(model):
        return db.query(model).filter(model.case_id == case.id,
            model.derivation_run_id == derivation_run_id).order_by(model.id).all()

    sources = data['sources']
    def intake_ref(label):
        return [s['source_ref'] for s in sources if not s['artifact_id'] and s['label'] == label]

    def document_ref(artifact_id, page=None):
        return [s['source_ref'] for s in sources if s['artifact_id'] == artifact_id
                and (page is None or s['page'] is None or s['page'] == page)]

    def assertion(text, refs=(), insufficient=None):
        refs = list(dict.fromkeys(refs))
        return {'text': text, 'source_refs': refs,
                'insufficient_support': True if insufficient is None else insufficient}

    dossier = fields(case)
    claims = scoped(Claim)
    assessments = scoped(Assessment)
    gaps = scoped(EvidenceGap)
    findings = scoped(Finding)
    safety = scoped(SafetyResult)
    items = db.query(TreatmentItem).join(Extraction).join(Artifact).filter(
        Artifact.case_id == case.id, Extraction.derivation_run_id == derivation_run_id,
        TreatmentItem.derivation_run_id == derivation_run_id).all()
    item_by_locator = {(i.extraction.artifact_id, i.tooth_id, i.treatment_id, i.predicate.value): i for i in items}
    artifacts = {a.id: a for a in case.artifacts}
    document_lines, document_refs = [], []
    for finding in findings:
        artifact = artifacts.get(finding.artifact_id)
        # Clinical statements must originate in extracted text, never image pixels.
        if not artifact or artifact.detected_mime_type.startswith('image/') or finding.finding_type != 'TREATMENT_ITEM':
            continue
        item = item_by_locator.get((artifact.id, finding.normalized_subject,
                                   finding.normalized_object, finding.predicate))
        if item is None:
            continue
        tooth = (item.tooth_id or '').replace('TOOTH_', '') or 'نامشخص'
        treatment = TREATMENTS_FA.get(item.treatment_id.replace('TREATMENT_', ''), 'درمان نامشخص')
        document_lines.append(
            f'{treatment} دندان {tooth}، '
            f'{MODALITY_FA.get(item.predicate, "ثبت شده")}'
        )
        document_refs.extend(document_ref(artifact.public_id, item.page))
    for artifact in case.artifacts:
        if artifact.document_role == 'previous_report' and artifact.text_content and not artifact.detected_mime_type.startswith('image/'):
            document_lines.append(f'یادداشت قبلی ساختگی ({artifact.original_filename}): {artifact.text_content[:350]}')
            document_refs.extend(document_ref(artifact.public_id))

    unavailable = sorted({GAP_FA.get(g.gap_type, g.gap_type) for g in gaps if g.status.value == 'MISSING'})
    claim_by_id = {c.id: c for c in claims}
    assessment_lines = []
    for assessment in assessments:
        claim = claim_by_id.get(assessment.claim_id)
        if claim:
            treatment = TREATMENTS_FA.get((claim.treatment_id or '').replace('TREATMENT_', ''), 'ادعا')
            origin = SOURCES_FA.get(claim.source_type.value, 'منبع نیازمند بررسی')
            assessment_lines.append(f'{treatment} ({origin}): {STATUS_FA[assessment.status]}')

    patient = [
        assertion(f'در این نمونهٔ کاملاً ساختگی، به گفتهٔ شما: {dossier["symptoms"] or "علائم نامشخص"}؛ مدت: {dossier["duration"] or "نامشخص"}.', intake_ref('symptoms') + intake_ref('duration')),
        assertion(f'پیشنهاد دندان‌پزشک به روایت شما: {case.dentist_recommendation_text or "ثبت نشده"}. این روایت، تأیید مستقل یا اثبات ضرورت درمان نیست.', intake_ref('clinician_recommendation')),
        assertion('مدارک ساختگی ثبت می‌کنند: ' + ('؛ '.join(document_lines)[:2100] or 'مورد متنی قابل استخراج ثبت نشده') + '. ثبت پیشنهاد، ضرورت درمان را اثبات نمی‌کند.', document_refs),
        assertion('طبق ارزیابی همین اجرا، شواهد هنوز در دسترس یا تأییدشده نیست: ' + ('، '.join(unavailable) or 'مورد جداگانه‌ای ثبت نشده') + '. علائم و طرح درمان ارائه‌شده با تکمیل ارزیابی بالینی یکسان نیستند.', insufficient=True),
        assertion(f'برای گفت‌وگو دربارهٔ سؤال «{case.question_text[:500]}»، بپرسید چه نتایج معاینه، تست پالپ و رادیوگرافی پشتوانهٔ پیشنهاد هستند؛ دلیل پیشنهاد روکش پس از عصب‌کشی و گزینه‌های قابل بررسی چیست؟', intake_ref('main_question'), insufficient=True),
    ]
    professional = [*patient[:3],
        assertion(patient[3]['text'] + ' نتیجهٔ قواعد موجود: ' + '؛ '.join(assessment_lines)[:1500], insufficient=True),
        patient[4]]
    limitations = [assertion('Mock؛ فقط متن و نتایج قواعد همین اجرا بازگو شده‌اند. PNG الگوی انتقال/آزمون است، رادیوگرافی نیست و هیچ تفسیر یا یافتهٔ بالینی از آن استخراج نشده است. تشخیص یا تعیین ضرورت درمان انجام نمی‌شود؛ برداشت نیازمند تأیید دندان‌پزشک است.')]
    if missing:
        limitations.append(assertion('این بخش‌های شرح حال ثبت نشده است: ' + '، '.join(MISSING_LABELS.get(key, key) for key in missing)))
    if safety:
        limitations.append(assertion(SAFETY_NOTE_FA.get(safety[-1].state, 'محدودیت ایمنی اجرا باید رعایت شود.')))
    return {'patient_summary': patient, 'professional_report': professional,
            'diagnostic_hypotheses': [], 'safety_red_flags': [], 'limitations': limitations,
            'source_index': [{'source_ref': s['source_ref']} for s in sources]}


def mock_review(data, missing):
    refs = [s['source_ref'] for s in data['sources']]
    document_refs = [s['source_ref'] for s in data['sources'] if s['artifact_id'] is not None]
    def assertion(text, sources=None):
        return {'text': text, 'source_refs': sources or [], 'insufficient_support': True}
    return {
        'patient_summary': [assertion('این خروجی نمونهٔ ساختگی است. برای روشن‌شدن علت علائم، معاینه لازم است.', refs[:1])],
        'professional_report': [assertion('مدارک ثبت‌شده برای بررسی منبع‌محور آماده‌اند؛ در اجرای Mock تحلیل بالینی تصویر غیرفعال است.', document_refs[:1])],
        'diagnostic_hypotheses': [{'label': 'حساسیت دندانی — فرضیهٔ نمایشی Mock',
            'confidence_label': 'LOW', 'supporting_evidence_refs': [],
            'contradicting_evidence_refs': [], 'insufficient_support': True,
            'missing_information': [assertion('این اطلاعات ثبت نشده است: ' + '، '.join(MISSING_LABELS.get(key, key) for key in missing))] if missing else [assertion('کفایت شواهد بالینی هنوز تأیید نشده است.')],
            'recommended_checks': [assertion('دربارهٔ معاینه و بررسی تکمیلی با دندان‌پزشک گفت‌وگو کنید.')]}],
        'safety_red_flags': [],
        'limitations': [assertion('Mock؛ تشخیص انجام نمی‌شود و تفسیر واقعی تصویر غیرفعال است. اطمینان کیفی، احتمال بیماری نیست؛ برداشت نیازمند تأیید دندان‌پزشک است.')],
        'source_index': [{'source_ref': ref} for ref in refs]}


def run_review(gateway, case, derivation_run_id, *, artifacts=None):
    db = gateway.db
    provider = gateway.provider
    from app.config import get_settings
    run = ReviewRun(public_id=public_id('MRUN'), case_id=case.id,
        derivation_run_id=derivation_run_id, provider=provider.name,
        model=('mock-' + DEMO_VERSION if is_demo(case) else 'mock-review-v1') if provider.name == 'mock' else get_settings().ai_model_name,
        schema_version=VERSION, status='RUNNING', source_index=[])
    db.add(run)
    db.commit()
    start = time.monotonic()
    try:
        # Bind intake provenance to the revision used to prepare the input, not
        # whichever revision happens to be latest after provider execution.
        revision = latest(case)
        data = bundle(case, artifacts=artifacts)
        if gateway.input_guard:
            gateway.input_guard()  # Preparation can race an edit; stop before dispatch.
        if provider.name == 'mock':
            missing = presentation(case)['missing_information']
            raw = demo_review(db, case, derivation_run_id, data, missing) if is_demo(case) else mock_review(data, missing)
        else:
            outbound, mapping = provider_bundle(data)
            candidate = validate_review(provider.review(outbound), mapping, source_context=outbound)
            raw = resolve_review(candidate, mapping)
        if gateway.input_guard:
            gateway.input_guard()
        output = validate_review(raw, [s['source_ref'] for s in data['sources']], source_context=data)
        notes, note_refs = [], []
        for ref, coverage in data['coverage'].items():
            if coverage.get('partial'):
                notes.append('بخشی از متن مدرک ارسال شده است؛ بررسی کامل متن انجام نشده است.')
                note_refs.append(ref)
            if coverage.get('clinical_use') == 'NON_CLINICAL':
                notes.append('تصویر الگوی آزمون غیر بالینی است؛ رادیوگرافی یا شاهد بیماری نیست.')
                note_refs.append(ref)
        if data['omitted_artifacts']:
            notes.append('برخی مدارک ردشده به بررسی مدل وارد نشده‌اند و شاهد بررسی‌شده محسوب نمی‌شوند.')
        if data['missing_intake']:
            notes.append('بخش‌های متنی ثبت‌نشده در شرح حال: ' + '، '.join(MISSING_LABELS[key] for key in data['missing_intake']) + '؛ این وضعیت درباره محتوای مدارک جداگانه داوری نمی‌کند.')
        if notes:
            from app.ai.review_schema import Assertion
            output.limitations.append(Assertion(text=' '.join(dict.fromkeys(notes)), source_refs=list(dict.fromkeys(note_refs)), insufficient_support=True))
        output = validate_review(output.model_dump(), [s['source_ref'] for s in data['sources']], source_context=data)
        run.output = output.model_dump()
        run.source_index = data['sources']
        run.status = 'SUCCEEDED'
        run.runtime_ms = int((time.monotonic() - start) * 1000)
        by_ref = {s['source_ref']: s for s in data['sources']}
        artifacts = {a.public_id: a.id for a in case.artifacts}
        for rank, value in enumerate(output.diagnostic_hypotheses, 1):
            hypothesis = DiagnosticHypothesis(review_run_id=run.id, rank=rank,
                label=value.label, confidence_label=value.confidence_label,
                insufficient_support=value.insufficient_support)
            db.add(hypothesis)
            db.flush()
            for relation, refs in [('SUPPORTS', value.supporting_evidence_refs),
                                   ('CONTRADICTS', value.contradicting_evidence_refs)]:
                for ref in refs:
                    source = by_ref[ref]
                    db.add(HypothesisEvidence(hypothesis_id=hypothesis.id, source_ref=ref,
                        artifact_id=artifacts.get(source['artifact_id']),
                        dossier_revision_id=revision.id if not source['artifact_id'] and revision else None,
                        relationship_type=relation))
        db.commit()
        return run
    except Exception as exc:
        db.rollback()
        run.status = 'FAILED'
        from app.safe_logging import safe_error_code
        code = safe_error_code(exc)
        run.error_code = 'REVIEW_FAILED' if code == 'INTERNAL_ERROR' else code
        run.output = None
        run.runtime_ms = int((time.monotonic() - start) * 1000)
        db.commit()
        from app.errors import ProcessingInputChangedError
        if isinstance(exc, ProcessingInputChangedError):
            raise
        raise ExtractionValidationError('Review failed closed', failure_code=code,
            retry_after=getattr(exc, 'retry_after', None)) from None
