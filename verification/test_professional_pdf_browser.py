"""Offline, synthetic export contract; PDF bytes stay in memory."""
import copy
import importlib.util
import re
from pathlib import Path

import pymupdf
import pytest
from playwright.sync_api import expect

spec = importlib.util.spec_from_file_location('pdf_prior', Path(__file__).with_name('test_p1_browser.py'))
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
server, browser, page = prior.server, prior.browser, prior.page


def synthetic(kind='STANDARD', long=False):
    ref = 'ART-PRIVATE:page:2'
    assertion = lambda text: {'text': text, 'source_refs': [ref], 'insufficient_support': True}
    return {
        'report_id': 'RPT-PRIVATE', 'snapshot_id': 'SNP-PRIVATE',
        'report_kind': kind, 'safety_state': 'CAUTION',
        'sections': [
            {'section': 'your_question', 'text': 'پرسش بیمار (دندان ۴۶ / 46)؟'},
            {'section': 'dentist_recommendation', 'text': 'پیشنهاد به روایت شما'},
            {'section': 'missing_evidence', 'text': 'معاینه حضوری\nتست پالپ'},
            {'section': 'questions_to_ask', 'text': '• پرسش اول؟\n• پرسش دوم؟'},
            {'section': 'safety_note', 'text': 'در صورت وجود درد یا تورم، پیگیری با دندان‌پزشک لازم است. این گزارش جایگزین معاینه نیست.'},
            {'section': 'review_pending', 'text': 'بررسی دستی لازم است؛ گزارش شواهد آماده نیست.'}],
        'presentation': {'materials': [{'filename': '../private/طرح\u202e-Plan\x01 (46).pdf', 'image_analysis_disabled': False}],
            'claims': [{'label': 'ادعای موجود', 'source': 'استخراج‌شده از سند', 'status': 'مدارک کافی نیست',
                        'evidence': [{'filename': '../private/طرح\u202e-Plan\x01 (46).pdf', 'relationship': 'مرتبط؛ اثبات ضرورت درمان نیست'}],
                        'missing': ['معاینه']} ]},
        'review': None if kind != 'STANDARD' else {
            'patient_summary': [assertion('PATIENT-ONLY خلاصه بیمار')],
            'professional_report': [assertion(f'PROFESSIONAL-ONLY بند {i} ' + ('متن فارسی (RCT 46)، ۱۲۳؛ English. ' * 25 if long else 'جزئیات تخصصی')) for i in range(20 if long else 1)],
            'limitations': [assertion('محدودیت موجود؛ نیازمند تأیید')],
            'safety_red_flags': [],
            'diagnostic_hypotheses': [{'label': 'فرضیه نمایشی', 'confidence_label': 'LOW', 'insufficient_support': True,
                'supporting_evidence_refs': [ref], 'contradicting_evidence_refs': [],
                'missing_information': [assertion('اطلاعات ناقص')], 'recommended_checks': [assertion('بررسی قابل گفت‌وگو')]}],
            'source_index': [{'source_ref': ref, 'artifact_id': 'ART-PRIVATE', 'kind': 'DOCUMENT_EXTRACTED',
                             'label': 'document-1', 'document_role': 'treatment_plan', 'page': 2, 'sha256': 'abcdef' * 10}],
            'run': {'run_id': 'MRUN-PRIVATE', 'provider': 'PRIVATE-PROVIDER', 'model': 'PRIVATE-MODEL',
                    'runtime_ms': 98765, 'created_at': '2026-01-01', 'mode': 'MOCK'}}}


def load(page, report):
    page.route('**/api/cases/*/report', lambda r: r.fulfill(json={**report, 'case_id': r.request.url.split('/cases/')[1].split('/')[0]}))
    prior.start(page, [prior.PLAN])
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    page.evaluate("window.print = () => window.dispatchEvent(new Event('beforeprint'))")


def prepare(page, audience='patient'):
    page.locator(f'#{audience}-view').click()
    page.locator('#print-report').click()
    expect(page.locator('body')).to_have_class(re.compile('export-prepared'))


@pytest.mark.parametrize('audience', ['patient', 'professional'])
def test_separate_whitelisted_export_and_restore(page, audience):
    report = synthetic()
    before = copy.deepcopy(report)
    load(page, report)
    page.locator(f'#{audience}-view').click()
    page.locator('.result-disclosure').first.evaluate('el => el.open = true')
    screen = page.locator('#report-content').inner_html()
    frozen = page.evaluate('JSON.stringify(state.report)')
    prepare(page, audience)
    exported = page.locator('#report-export').inner_text()
    assert ('PATIENT-ONLY' in exported) == (audience == 'patient')
    assert ('PROFESSIONAL-ONLY' in exported) == (audience == 'professional')
    assert ('فرضیه نمایشی' in exported) == (audience == 'professional')
    for token in ['PRIVATE-PROVIDER', 'PRIVATE-MODEL', '98765', 'RPT-', 'SNP-', 'MRUN-', 'ART-', 'abcdef', 'document-1', 'snapshot', 'runtime_ms']:
        assert token not in exported
    assert report['sections'][4]['text'] in exported
    assert 'طرح-Plan (46).pdf' in exported
    assert '../' not in exported and '\u202e' not in exported and '\x01' not in exported
    assert page.locator('#report-export .export-limitation .export-reference').count() > 0
    assert page.locator('#report-export bdi').count() > 0
    page.emulate_media(media='print')
    expect(page.locator('#view-report')).not_to_be_visible()
    expect(page.locator('#report-export')).to_be_visible()
    pdf = page.pdf(prefer_css_page_size=True, print_background=False)
    with pymupdf.open(stream=pdf, filetype='pdf') as doc:
        assert abs(doc[0].rect.width - 595.28) < 2
        text = ''.join(p.get_text() for p in doc)
        assert ('PATIENT-ONLY' in text) == (audience == 'patient')
        for token in ['PRIVATE-PROVIDER', 'PRIVATE-MODEL', 'SNP-', 'MRUN-', 'ART-', 'abcdef']:
            assert token not in text
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    page.emulate_media(media='screen')
    expect(page.locator('#report-export')).to_be_empty()
    assert page.locator('#report-content').inner_html() == screen
    assert page.evaluate('JSON.stringify(state.report)') == frozen
    expect(page.locator(f'#{audience}-view')).to_have_attribute('aria-pressed', 'true')
    # A second native print cannot reuse a completed/cancelled export.
    page.emulate_media(media='print')
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator('#view-report')).not_to_be_visible()
    expect(page.locator('#report-export')).not_to_be_visible()
    assert report == before


def test_native_print_without_preparation(page):
    load(page, synthetic())
    page.emulate_media(media='print')
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator('#view-report')).not_to_be_visible()
    expect(page.locator('#report-export')).not_to_be_visible()
    pdf = page.pdf(prefer_css_page_size=True)
    with pymupdf.open(stream=pdf, filetype='pdf') as doc:
        assert 'PATIENT-ONLY' not in ''.join(p.get_text() for p in doc)


@pytest.mark.parametrize('kind', ['URGENT', 'REVIEW_PENDING'])
def test_restricted_safety_exports(page, kind):
    report = synthetic(kind)
    load(page, report)
    page.locator('#print-report').click()
    expect(page.locator('body')).to_have_class(re.compile('export-prepared'))
    text = page.locator('#report-export').inner_text()
    required = report['sections'][4 if kind == 'URGENT' else 5]['text']
    assert required in text
    assert 'ادعای موجود' not in text and 'طرح-Plan' not in text


@pytest.mark.parametrize('failure', ['stale', 'identity'])
def test_export_refuses_stale_or_substitution(page, failure):
    report = synthetic()
    load(page, report)
    page.unroute('**/api/cases/*/report')
    if failure == 'stale':
        page.route('**/api/cases/*/report', lambda r: r.fulfill(status=404, json={'detail': 'REPORT_NOT_READY'}))
    else:
        page.route('**/api/cases/*/report', lambda r: r.fulfill(json={**report, 'report_id': 'RPT-OTHER', 'case_id': prior.case_id(page)}))
    page.locator('#print-report').click()
    page.wait_for_function('!state.busy')
    assert not page.locator('body').evaluate("el => el.classList.contains('export-prepared')")
    expect(page.locator('#report-export')).to_be_empty()


def test_long_a4_mixed_content_and_fragmentation(page, tmp_path):
    load(page, synthetic(long=True))
    prepare(page, 'professional')
    page.emulate_media(media='print')
    assert page.locator('#report-export .export-assertion').first.evaluate("el => getComputedStyle(el).breakInside") == 'avoid'
    assert page.locator('#report-export h2').first.evaluate("el => getComputedStyle(el).breakAfter") == 'avoid'
    pdf = page.pdf(prefer_css_page_size=True, print_background=False)
    (tmp_path / 'professional-long-a4.pdf').write_bytes(pdf)
    with pymupdf.open(stream=pdf, filetype='pdf') as doc:
        assert len(doc) >= 3
        text = ''.join(p.get_text() for p in doc)
        assert text.count('PROFESSIONAL-ONLY') == 20
        for sheet in doc:
            assert sheet.get_text().strip()
            for block in sheet.get_text('blocks'):
                assert block[0] >= 0 and block[2] <= sheet.rect.width + 1
                assert block[1] >= 0 and block[3] <= sheet.rect.height + 1
            blocks = [b for b in sheet.get_text('dict')['blocks'] if b['type'] == 0]
            for index, block in enumerate(blocks):
                sizes = [s['size'] for line in block['lines'] for s in line['spans']]
                if sizes and max(sizes) == pytest.approx(15, abs=.1):
                    assert index + 1 < len(blocks), 'section heading stranded at page end'
            if 'PROFESSIONAL-ONLY' in sheet.get_text():
                assert '[1]' in sheet.get_text(), 'assertion references detached from their page'
        for number in [0, len(doc)//2, len(doc)-1]:
            doc[number].get_pixmap().save(str(tmp_path / f'page-{number+1}.png'))
        doc[0].get_pixmap(colorspace=pymupdf.csGRAY).save(str(tmp_path / 'page-1-grayscale.png'))
    assert page.locator('#report-export').get_attribute('dir') == 'rtl'


def test_real_demo_export_preserves_report_and_reuse(page):
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    cid = prior.case_id(page)
    before = page.request.get(f'{page.url.rstrip("/")}/api/cases/{cid}/report').json()
    page.evaluate("window.print = () => window.dispatchEvent(new Event('beforeprint'))")
    prepare(page, 'professional')
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    after = page.request.get(f'{page.url.rstrip("/")}/api/cases/{cid}/report').json()
    assert after == before
    reused = page.request.post(f'{page.url.rstrip("/")}/api/cases/{cid}/process').json()
    assert reused['snapshot'] == before['snapshot_id']


def test_oversized_assertion_splits_without_losing_content(page, tmp_path):
    report = synthetic()
    report['review']['professional_report'][0]['text'] = 'OVERSIZED-BEGIN\n' + ('فارسی (English 46)، ۱۲۳؛\n' * 100) + 'OVERSIZED-END'
    load(page, report)
    prepare(page, 'professional')
    page.emulate_media(media='print')
    pdf = page.pdf(prefer_css_page_size=True)
    (tmp_path / 'oversized-a4.pdf').write_bytes(pdf)
    with pymupdf.open(stream=pdf, filetype='pdf') as doc:
        assert len(doc) >= 4
        text = ''.join(p.get_text() for p in doc)
        assert 'OVERSIZED-BEGIN' in text.replace('\n', '') and 'OVERSIZED-END' in text.replace('\n', ''), [word for word in text.split() if 'OVERSIZED' in word or 'END' in word]
        assert '\ufffd' not in text
        for sheet in doc:
            for b in sheet.get_text('blocks'):
                assert 0 <= b[0] <= b[2] <= sheet.rect.width + 1
                assert 0 <= b[1] <= b[3] <= sheet.rect.height + 1


def test_export_uses_revalidated_content_and_escapes_filename(page):
    report = synthetic()
    load(page, report)
    page.unroute('**/api/cases/*/report')
    fresh = copy.deepcopy(report)
    fresh['review']['patient_summary'][0]['text'] = 'FRESH-RESPONSE متن معتبر'
    fresh['presentation']['materials'][0]['filename'] = 'C:\\folder\\پرونده <img src=x onerror=alert(1)>.pdf'
    page.route('**/api/cases/*/report', lambda r: r.fulfill(json={**fresh, 'case_id': r.request.url.split('/cases/')[1].split('/')[0]}))
    prepare(page)
    text = page.locator('#report-export').inner_text()
    assert 'FRESH-RESPONSE' in text and 'PATIENT-ONLY' not in text
    assert '<img src=x onerror=alert(1)>.pdf' in text and 'C:' not in text
    assert page.locator('#report-export img').count() == 0
    # Export preparation leaves the normal report DOM untouched.
    assert 'PATIENT-ONLY' in page.locator('#report-content').inner_text()


def test_failed_print_restores_screen_and_discards_document(page):
    load(page, synthetic())
    title = page.title()
    page.evaluate("() => { window.print = () => { throw new Error('print unavailable'); }; }")
    page.locator('#print-report').click()
    page.wait_for_function('!state.busy')
    expect(page.locator('#report-export')).to_be_empty()
    assert page.title() == title
    page.emulate_media(media='print')
    expect(page.locator('#view-report')).not_to_be_visible()


def test_source_distinction_and_unresolved_reference_fail_closed(page):
    report = synthetic()
    second = {**report['review']['source_index'][0], 'source_ref': 'CASE-PRIVATE:v1:clinician_recommendation',
              'artifact_id': None, 'kind': 'CLINICIAN_REPORTED', 'label': 'clinician_recommendation', 'page': None}
    report['review']['source_index'].append(second)
    report['review']['professional_report'][0]['source_refs'].append(second['source_ref'])
    load(page, report)
    prepare(page, 'professional')
    text = page.locator('#report-export').inner_text()
    assert '[1]' in text and '[2]' in text
    assert 'گفتهٔ دندان‌پزشک به روایت شما' in text and 'محتوای سند' in text
    assert page.locator('#report-export .export-source').count() == 2
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    page.unroute('**/api/cases/*/report')
    report['review']['professional_report'][0]['source_refs'].append('ART-UNRESOLVED')
    page.route('**/api/cases/*/report', lambda r: r.fulfill(json={**report, 'case_id': r.request.url.split('/cases/')[1].split('/')[0]}))
    page.locator('#print-report').click()
    page.wait_for_function('!state.busy')
    expect(page.locator('#report-export')).to_be_empty()


def test_legacy_report_preserves_existing_empty_result_qualification(page):
    report = synthetic()
    report['review'] = None
    report['sections'][2]['text'] = 'شواهد کاملی ثبت شده است.'
    load(page, report)
    page.locator('#print-report').click()
    expect(page.locator('body')).to_have_class(re.compile('export-prepared'))
    text = page.locator('#report-export').inner_text()
    assert 'شواهد کاملی ثبت شده است.' not in text
    assert 'این به معنی کامل بودن ارزیابی بالینی نیست.' in text
    assert report['sections'][4]['text'] in text
