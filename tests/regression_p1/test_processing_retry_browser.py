"""Browser response-handling probes; failure responses are transport fixtures.

Durable failures are independently covered by test_processing_retry.py.
"""
import pytest
from playwright.sync_api import expect

from verification.test_p1_browser import server, browser, page, start, PLAN


@pytest.mark.parametrize('mode', ['ACCOUNT', 'DEMO'])
@pytest.mark.parametrize('failure', ['network', 'http', 'failed_run'])
def test_retry_response_parity_and_success_reload(page, mode, failure):
    prefix = '/api/demo/cases' if mode == 'DEMO' else '/api/cases'
    requests = []
    page.on('request', lambda r: requests.append((r.method, r.url)))

    def fail(route):
        if failure == 'network':
            route.abort()
        elif failure == 'http':
            route.fulfill(status=503, json={'detail': 'SYNTHETIC_UNAVAILABLE'})
        else:
            route.fulfill(status=200, json={
                'status': 'FAILED', 'report': None, 'snapshot': None,
                'reused': False, 'pipeline_run_id': 'RUN_SYNTHETIC_FIXTURE'})

    page.route('**' + prefix + '/*/process', fail, times=1)
    if mode == 'DEMO':
        page.locator('#start-sample').click()
    else:
        start(page, [PLAN])
    expect(page.locator('#outcome-title')).to_have_text('پردازش کامل نشد')
    expect(page.locator('#retry-process')).to_be_enabled()
    expect(page.locator('#analysis-scene')).not_to_be_visible()
    cid = page.evaluate('state.caseId')
    page.locator('#retry-process').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    assert page.evaluate('state.caseId') == cid
    assert sum(method == 'POST' and url.endswith(prefix) for method, url in requests) == 1
    assert sum(method == 'POST' and url.endswith('/process') for method, url in requests) == 2
    before = [(method, url) for method, url in requests if method in ('POST', 'PUT', 'PATCH')]
    page.reload()
    expect(page.locator('#view-home')).to_be_visible()
    page.locator('#resume-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    expect(page.locator('#print-report')).to_be_enabled()
    assert page.evaluate('state.caseId') == cid
    assert [(method, url) for method, url in requests if method in ('POST', 'PUT', 'PATCH')] == before
