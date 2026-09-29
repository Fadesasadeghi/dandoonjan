"""Candidate review behind ModelGateway; durable content-free failure audit."""
import time
from app.ai.multimodal import bundle
from app.ai.review_schema import VERSION, validate_review
from app.core.cases.dossier import latest, presentation
from app.domain.models import ReviewRun, DiagnosticHypothesis, HypothesisEvidence, public_id
from app.errors import ExtractionValidationError


def mock_review(data, missing):
    refs = [s['source_ref'] for s in data['sources']]
    document_refs = [s['source_ref'] for s in data['sources'] if s['artifact_id'] is not None]
    missing_labels = {'symptoms':'علائم', 'duration':'مدت علائم', 'medical_history':'سابقه پزشکی',
        'medications':'داروها', 'allergies':'حساسیت‌ها', 'treatment_plan':'طرح درمان',
        'previous_reports':'گزارش قبلی', 'previous_treatments':'درمان قبلی', 'dental_images':'تصویر دندان'}
    def assertion(text, sources=None):
        return {'text': text, 'source_refs': sources or [], 'insufficient_support': not bool(sources)}
    return {
        'patient_summary': [assertion('این خروجی نمونهٔ ساختگی است. برای روشن‌شدن علت علائم، معاینه لازم است.')],
        'professional_report': [assertion('مدارک ثبت‌شده برای بررسی منبع‌محور آماده‌اند؛ در اجرای Mock تحلیل بالینی تصویر غیرفعال است.', document_refs[:1])],
        'diagnostic_hypotheses': [{'label': 'حساسیت دندانی — فرضیهٔ نمایشی Mock',
            'confidence_label': 'LOW', 'supporting_evidence_refs': [],
            'contradicting_evidence_refs': [], 'insufficient_support': True,
            'missing_information': [assertion('اطلاعات ثبت‌نشده: ' + '، '.join(missing_labels.get(key, key) for key in missing))] if missing else [],
            'recommended_checks': [assertion('دربارهٔ معاینه و بررسی تکمیلی با دندان‌پزشک گفت‌وگو کنید.')]}],
        'safety_red_flags': [],
        'limitations': [assertion('Mock؛ بدون تحلیل واقعی تصویر یا اعتبارسنجی بالینی. اطمینان کیفی، احتمال بیماری نیست.')],
        'source_index': [{'source_ref': ref} for ref in refs]}


def run_review(gateway, case, derivation_run_id):
    db = gateway.db
    provider = gateway.provider
    from app.config import get_settings
    run = ReviewRun(public_id=public_id('MRUN'), case_id=case.id,
        derivation_run_id=derivation_run_id, provider=provider.name,
        model='mock-review-v1' if provider.name == 'mock' else get_settings().ai_model_name,
        schema_version=VERSION, status='RUNNING', source_index=[])
    db.add(run)
    db.commit()
    start = time.monotonic()
    try:
        data = bundle(case)
        raw = (mock_review(data, presentation(case)['missing_information'])
               if provider.name == 'mock' else provider.review(data))
        output = validate_review(raw, [s['source_ref'] for s in data['sources']])
        run.output = output.model_dump()
        run.source_index = data['sources']
        run.status = 'SUCCEEDED'
        run.runtime_ms = int((time.monotonic() - start) * 1000)
        revision = latest(case)
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
    except Exception:
        db.rollback()
        run.status = 'FAILED'
        run.error_code = 'REVIEW_FAILED'
        run.output = None
        run.runtime_ms = int((time.monotonic() - start) * 1000)
        db.commit()
        raise ExtractionValidationError('Review failed closed') from None
