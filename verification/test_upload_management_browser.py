from playwright.sync_api import expect
import pytest
from verification.test_p1_browser import server, browser, page, PLAN


@pytest.mark.parametrize('width', [390,768,1440])
def test_local_rows_and_roles(page, width):
    from verification.test_p1_browser import assert_no_overflow
    page.set_viewport_size({'width':width, 'height':900})
    page.locator('#start-case').click()
    page.locator('#question').fill('Synthetic question')
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    page.locator('#files').set_input_files([
        {'name': 'one.txt', 'mimeType': 'text/plain', 'buffer': PLAN['buffer']},
        {'name': 'two.txt', 'mimeType': 'text/plain', 'buffer': PLAN['buffer'] + b' two'},
        {'name': 'bad.heic', 'mimeType': 'image/heic', 'buffer': b'GIF89a'},
    ])
    rows = page.locator('#file-list li')
    rows.nth(1).locator('.file-role').select_option('prescription')
    assert page.evaluate('state.files[0].role') == 'unspecified'
    assert page.evaluate('state.files[1].role') == 'prescription'
    identity = page.evaluate('state.files[1].localId')
    requests = []
    page.on('request', lambda r: requests.append(r.url) if r.method != 'GET' else None)
    rows.nth(0).locator('.remove-file').click()
    assert rows.count() == 2
    assert page.evaluate('state.files[0].localId') == identity
    rows.nth(1).locator('.remove-file').click()
    assert rows.count() == 1
    assert_no_overflow(page)
    assert requests == []


def test_sample_processing_state_separate(page):
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    assert page.locator('#report-files [data-upload-state=uploaded]').count() == 4
    assert page.locator('#report-files .remove-file').count() == 0
    assert page.locator('#report-files .file-role').count() == 0
    assert page.locator('#report-files [data-processing-state=limited]').count() >= 1


def test_duplicate_metadata_and_resume(page):
    from verification.test_p1_browser import start
    start(page, [PLAN])
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    page.locator('#add-evidence').click()
    page.locator('#document-role').select_option('prescription')
    page.locator('#files').set_input_files([{**PLAN, 'name':'renamed.txt'}])
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    duplicate = page.locator('#report-files [data-upload-state=duplicate]')
    expect(duplicate).to_contain_text('نام فایل و نوع مدرک')
    assert duplicate.locator('.remove-file, .file-role').count() == 0
    cid = page.evaluate('state.caseId')
    assert len(page.request.get(page.evaluate('location.origin') + f'/api/cases/{cid}').json()['artifacts']) == 1
    page.reload()
    page.locator('#resume-case').click()
    page.wait_for_function('!state.busy && state.files.length === 1')
    assert page.evaluate('state.files.map(r => [r.file, r.uploadState, r.processingState, r.role ?? null])') == [[None, 'uploaded', 'unknown', None]]


def test_lost_response_retries_without_duplicate_artifact(page):
    from verification.test_p1_browser import start
    def lose(route):
        response = route.fetch()
        assert response.status == 201
        route.abort('failed')
    page.route('**/api/cases/*/artifacts', lose, times=1)
    start(page, [PLAN])
    page.wait_for_function('!state.busy')
    page.locator('#add-evidence').click()
    row = page.locator('#file-list [data-upload-state=retryable]')
    expect(row).to_be_visible()
    assert row.locator('.file-role, .remove-file').count() == 0
    row.locator('.retry-file').click()
    assert page.locator('#file-list .file-role').count() == 0
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    cid = page.evaluate('state.caseId')
    assert len(page.request.get(page.evaluate('location.origin') + f'/api/cases/{cid}').json()['artifacts']) == 1
    assert page.locator('#report-files [data-upload-state=duplicate]').count() == 1
