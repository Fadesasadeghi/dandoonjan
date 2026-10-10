"""Restricted-processing presentation; disposable fixtures, no captures or PDFs."""
import pytest
from playwright.sync_api import expect

from verification.auth_gate3_support import (
    browser, server, page, signed_in, create, PLAN,
)


@pytest.mark.parametrize('namespace', ['ACCOUNT', 'DEMO'])
def test_knowledge_pack_restriction_preserves_case_and_evidence(page, server, namespace):
    if namespace == 'ACCOUNT':
        signed_in(page)
        create(page)
        page.locator('#files').set_input_files(PLAN)
        page.locator('#process-case').click()
    else:
        page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    page.wait_for_function('!state.busy')
    case_id = page.evaluate('state.caseId')
    artifacts = page.evaluate('state.files.map(row => row.artifactId)')
    prefix = '/api/demo/cases' if namespace == 'DEMO' else '/api/cases'
    calls = []

    def restricted(route):
        calls.append(route.request.url)
        route.fulfill(status=422, json={'detail': {
            'code': 'KNOWLEDGE_PACK_UNAVAILABLE',
            'message_fa': 'دانشنامه بالینی در دسترس نیست.',
        }})

    page.route(f'**{prefix}/*/process', restricted)
    page.locator('#add-evidence').click()
    page.locator('#process-case').click()
    page.wait_for_function('!state.busy')
    expect(page.locator('#outcome')).to_be_visible()
    expect(page.locator('#outcome-title')).to_have_text('تولید خروجی بالینی در دسترس نیست')
    message = page.locator('#outcome-text')
    expect(message).to_contain_text('دانشنامهٔ بالینی تأییدشده')
    expect(message).to_contain_text('امکان تولید خروجی بالینی وجود ندارد')
    expect(message).to_contain_text('پرونده و مدارک ثبت‌شدهٔ شما حفظ شده‌اند')
    expect(message).to_contain_text('تکرار پردازش یا افزودن مدرک، این محدودیت را برطرف نمی‌کند')
    expect(page.locator('#retry-process')).to_be_hidden()
    expect(page.locator('#process-case')).to_be_disabled()
    expect(page.locator('#workspace-error')).to_be_hidden()
    expect(page.locator('#outcome')).to_have_attribute('aria-live', 'polite')
    expect(page.locator('#report-content')).to_be_empty()
    expect(page.locator('#view-report')).not_to_be_visible()
    expect(page.locator('#report-export')).to_be_empty()
    assert page.evaluate('state.report') is None
    assert page.evaluate('state.caseId') == case_id
    assert page.evaluate('state.files.map(row => row.artifactId)') == artifacts
    expect(page.locator('#file-list [data-upload-state=uploaded]')).to_have_count(len(artifacts))
    saved = page.request.get(server['url'] + prefix + '/' + case_id)
    assert saved.status == 200
    assert {a['artifact_id'] for a in saved.json()['artifacts']} == set(artifacts)
    # Existing safe navigation remains usable without replaying processing.
    page.locator('#back-home').click()
    expect(page.locator('#view-home')).to_be_visible()
    page.locator('#return-draft').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    expect(message).to_be_visible()
    expect(page.locator('#process-case')).to_be_disabled()
    assert len(calls) == 1


def test_transient_processing_failure_keeps_explicit_retry(page):
    signed_in(page)
    case_id = create(page)
    page.locator('#files').set_input_files(PLAN)
    page.route('**/api/cases/*/process', lambda route: route.fulfill(
        status=503, json={'detail': {'code': 'SERVICE_UNAVAILABLE',
                                    'message_fa': 'سرویس موقتاً در دسترس نیست.'}}), times=1)
    page.locator('#process-case').click()
    page.wait_for_function('!state.busy')
    expect(page.locator('#outcome-title')).to_have_text('پردازش کامل نشد')
    expect(page.locator('#retry-process')).to_be_visible()
    expect(page.locator('#retry-process')).to_be_enabled()
    expect(page.locator('#process-case')).to_be_enabled()
    expect(page.locator('#workspace-error')).to_contain_text('سرویس موقتاً')
    page.locator('#retry-process').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    assert page.evaluate('state.caseId') == case_id
