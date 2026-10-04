"""Demo content/recovery against isolated local SQLite and Mock."""
import pytest
from playwright.sync_api import expect
from verification.test_p1_browser import server, browser, page
from verification.test_navigation_browser import mutations


def test_sample_content_roles_and_messages(page):
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    for audience in ('patient', 'professional'):
        page.locator(f'#{audience}-view').click()
        summary = page.locator(f'[data-audience={audience}]')
        for term in ('حساسیت', 'سه روز', 'روکش', 'معاینه', 'پالپ', 'رادیوگرافی', 'گفت‌وگو'):
            expect(summary).to_contain_text(term)
    rows = page.locator('#report-files li')
    assert rows.count() == 4
    for i in (0, 2, 3):
        expect(rows.nth(i)).to_contain_text('ساختگی')
    expect(rows.nth(1)).to_contain_text('رادیوگرافی نیست')
    assert page.evaluate('state.files.map(row => row.role)') == ['treatment_plan', 'dental_image', 'treatment_plan', 'previous_report']


@pytest.mark.parametrize('asset', ['sample','sample-image','sample-plan'])
def test_asset_failure_creates_nothing(page, asset):
    requests = mutations(page)
    page.route(f'**/api/demo/{asset}', lambda r: r.fulfill(status=503, body='unavailable'))
    page.locator('#start-sample').click()
    expect(page.locator('#workspace-error')).to_be_visible()
    page.wait_for_function('!state.busy')
    assert requests == []
    assert page.evaluate('state.caseId') is None
    assert page.evaluate('state.files.length') == 0


def test_upload_failure_blocks_process_and_retries_same_case(page):
    requests = mutations(page)
    page.route('**/api/demo/cases/*/artifacts', lambda r: r.fulfill(status=503, json={'detail':'unavailable'}), times=1)
    page.locator('#start-sample').click()
    expect(page.locator('#workspace-error')).to_be_visible(timeout=30000)
    page.wait_for_function('!state.busy')
    cid = page.evaluate('state.caseId')
    assert cid
    assert not any(url.endswith('/process') for _, url in requests)
    assert page.evaluate("state.files.filter(row => row.uploadState === 'uploaded').length") == 3
    page.locator('#file-list .retry-file').click()
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    assert page.evaluate('state.caseId') == cid
    assert sum(url.endswith('/api/demo/cases') for _, url in requests) == 1
    assert sum(url.endswith('/artifacts') for _, url in requests) == 5


def test_sample_refresh_resume_and_namespace_isolation(page):
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    cid = page.evaluate('state.caseId')
    origin = page.evaluate('location.origin')
    assert page.request.get(origin+f'/api/cases/{cid}').status == 404
    page.reload()
    page.locator('#resume-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    assert page.evaluate('state.caseId') == cid
    assert page.evaluate('state.sample') is True


def test_lost_demo_session_does_not_claim_old_case(page):
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    cid = page.evaluate('state.caseId')
    page.context.clear_cookies(name='dandoonjan_dev_demo')
    page.reload()
    page.locator('#resume-case').click()
    expect(page.locator('#workspace-error')).to_be_visible(timeout=30000)
    page.wait_for_function('!state.busy')
    assert page.evaluate('state.report') is None
    page.locator('.brand').click()
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    assert page.evaluate('state.caseId') != cid
    assert page.request.get(page.evaluate('location.origin')+f'/api/demo/cases/{cid}').status == 404


def test_storage_sample_hint_cannot_authorize(page):
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    page.evaluate("sessionStorage.setItem('dandoonjan_active_case', JSON.stringify({id:state.caseId,sample:false}))")
    page.reload()
    page.locator('#resume-case').click()
    expect(page.locator('#workspace-error')).to_be_visible(timeout=30000)
    page.wait_for_function('!state.busy')
    assert page.evaluate('state.report') is None
