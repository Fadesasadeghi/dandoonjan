"""Same-document navigation against isolated SQLite/Mock; no paid services."""
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from verification.test_p1_browser import server, browser, page, PLAN, assert_no_overflow


def mutations(page):
    requests = []
    page.on('request', lambda r: requests.append((r.method, r.url)) if r.method in ('POST', 'PUT', 'PATCH', 'DELETE') else None)
    return requests


def test_sample_is_one_history_action_without_mutation_replay(page):
    requests = mutations(page)
    expect(page.locator('#view-home')).to_be_visible()
    initial_length = page.evaluate('history.length')
    page.evaluate("""() => {
        window.sampleHistoryWrites = [];
        for (const method of ['pushState', 'replaceState']) {
            const original = history[method].bind(history);
            history[method] = (entry, ...args) => {
                window.sampleHistoryWrites.push({method, view: entry.view});
                return original(entry, ...args);
            };
        }
    }""")
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    expect(page.locator('#print-report')).to_be_enabled()
    entry = page.evaluate('history.state')
    case_id = entry['caseId']
    expected = [
        ('POST', '/api/demo/session'),
        ('POST', '/api/demo/cases'),
        ('PUT', f'/api/demo/cases/{case_id}/dossier'),
        ('PATCH', f'/api/demo/cases/{case_id}'),
        ('PUT', f'/api/demo/cases/{case_id}/dossier'),
        *[('POST', f'/api/demo/cases/{case_id}/artifacts')] * 4,
        ('POST', f'/api/demo/cases/{case_id}/process'),
    ]
    assert [(method, urlsplit(url).path) for method, url in requests] == expected
    before = list(requests)
    page.go_back()
    expect(page.locator('#view-home')).to_be_visible()
    page.go_forward()
    expect(page.locator('#view-report')).to_be_visible()
    expect(page.locator('#print-report')).to_be_enabled(timeout=30000)
    assert page.evaluate('history.state') == entry
    assert page.evaluate('state.caseId') == case_id
    assert page.evaluate('state.sample') is True
    assert requests == before
    assert page.evaluate('history.length') == initial_length + 1
    assert page.evaluate("sampleHistoryWrites.filter(write => write.method === 'pushState')") == [
        {'method': 'pushState', 'view': 'intake'}
    ]
    assert page.evaluate("sampleHistoryWrites.filter(write => write.method === 'replaceState').map(write => write.view)") == [
        'home', 'evidence', 'evidence', 'processing', 'report'
    ]


def evidence(page):
    page.locator('#start-case').click()
    page.locator('#question').fill('Synthetic question about tooth 46')
    page.locator('#dentist').fill('RCT recommended for tooth 46')
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()


def report(page):
    evidence(page)
    page.locator('#files').set_input_files(PLAN)
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    expect(page.locator('#print-report')).to_be_enabled()


def test_brand_keyboard_draft_and_intake_history(page):
    requests = mutations(page)
    page.evaluate('window.navigationMarker = 42')
    page.locator('#start-case').click()
    page.locator('#question').fill('unsaved draft')
    page.locator('.brand').focus()
    page.keyboard.press('Enter')
    expect(page.locator('#view-home')).to_be_visible()
    assert page.evaluate('window.navigationMarker') == 42
    page.locator('#return-draft').click()
    expect(page.locator('#question')).to_have_value('unsaved draft')
    page.go_back()
    expect(page.locator('#view-home')).to_be_visible()
    page.go_forward()
    expect(page.locator('#question')).to_have_value('unsaved draft')
    assert requests == []


def test_pending_files_and_edit_history_are_presentation_only(page):
    requests = mutations(page)
    evidence(page)
    page.locator('#document-role').select_option('prescription')
    page.locator('#files').set_input_files(PLAN)
    page.evaluate('window.selectedFile = state.files[0].file')
    before = list(requests)
    page.locator('#edit-case').click()
    page.locator('#question').fill('unsaved revision')
    page.go_back()
    expect(page.locator('#evidence-panel')).to_be_visible()
    page.go_forward()
    expect(page.locator('#evidence-panel')).not_to_be_visible()
    page.locator('.brand').click()
    page.locator('#return-draft').click()
    expect(page.locator('#question')).to_have_value('unsaved revision')
    expect(page.locator('#evidence-panel')).not_to_be_visible()
    assert page.evaluate("state.files[0].file === window.selectedFile && state.files[0].role === 'prescription' && state.files[0].uploadState === 'pending'")
    assert page.evaluate('state.files[0].file instanceof File')
    assert requests == before


def test_processing_back_completion_and_obsolete_forward(page):
    requests = mutations(page)
    evidence(page)
    page.locator('#files').set_input_files(PLAN)
    held = []
    page.route('**/api/cases/*/process', lambda r: held.append(r), times=1)
    page.locator('#process-case').click()
    expect(page.locator('#activity')).to_have_text('در حال پردازش در سرور؛ لطفاً منتظر بمانید…')
    assert len(held) == 1
    page.go_back()
    expect(page.locator('#evidence-panel')).to_be_visible()
    expect(page.locator('#process-case')).to_be_disabled()
    page.go_forward()
    expect(page.locator('#analysis-scene')).to_be_visible()
    page.go_back()
    before = list(requests)
    held[0].continue_()
    expect(page.locator('#process-case')).to_be_enabled(timeout=30000)
    expect(page.locator('#view-workspace')).to_be_visible()
    expect(page.locator('#view-report')).not_to_be_visible()
    page.go_forward()
    expect(page.locator('#view-report')).to_be_visible()
    expect(page.locator('#print-report')).to_be_enabled(timeout=30000)
    expect(page.locator('#analysis-scene')).not_to_be_visible()
    page.go_back()
    expect(page.locator('#evidence-panel')).to_be_visible()
    assert requests == before
    assert sum(method == 'POST' and url.endswith('/process') for method, url in requests) == 1


def test_processing_completion_stays_home_and_draft_return_resolves(page):
    requests = mutations(page)
    evidence(page)
    page.locator('#files').set_input_files(PLAN)
    held = []
    page.route('**/api/cases/*/process', lambda r: held.append(r), times=1)
    page.locator('#process-case').click()
    expect(page.locator('#activity')).to_have_text('در حال پردازش در سرور؛ لطفاً منتظر بمانید…')
    page.locator('.brand').click()
    expect(page.locator('#view-home')).to_be_visible()
    held[0].continue_()
    page.wait_for_function('!state.busy')
    expect(page.locator('#view-home')).to_be_visible()
    page.locator('#return-draft').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    assert sum(url.endswith('/process') for _, url in requests) == 1


@pytest.mark.parametrize('wrong_identity', [None, 'case_id', 'report_id', 'snapshot_id', 'run_id'])
def test_report_history_revalidates_exact_result(page, wrong_identity):
    requests = mutations(page)
    report(page)
    entry = page.evaluate('history.state')
    page.go_back()
    expect(page.locator('#evidence-panel')).to_be_visible()
    if wrong_identity:
        def different(r):
            payload = r.fetch().json()
            if wrong_identity == 'run_id':
                payload['review']['run']['run_id'] = 'another-run'
            else:
                payload[wrong_identity] = 'another-identity'
            r.fulfill(json=payload)
        page.route('**/api/cases/*/report', different)
    else:
        changed = page.request.patch(f"{page.url.rstrip('/')}/api/cases/{entry['caseId']}", form={'question': 'changed backend input'},
                                     headers={'X-CSRF-Token': page.evaluate('Account.csrf')})
        assert changed.status == 200
    before = list(requests)
    page.go_forward()
    expect(page.locator('#report-unavailable')).to_be_visible(timeout=30000)
    expect(page.locator('#report-content')).to_be_empty()
    expect(page.locator('#print-report')).to_be_disabled()
    page.locator('#return-evidence').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    assert requests == before


def test_new_session_does_not_restore_previous_case(page):
    evidence(page)
    old = page.evaluate('history.state')
    metadata = page.evaluate("JSON.parse(sessionStorage.getItem('dandoonjan_active_case'))")
    assert metadata['version'] == 2 and metadata['namespace'] == 'ACCOUNT'
    assert metadata['accountId'] == page.evaluate('Account.user.public_id')
    page.locator('.brand').click()
    page.locator('#start-case').click()
    page.locator('#question').fill('new draft')
    assert page.evaluate('history.state.session') != old['session']
    page.go_back()
    page.go_back()
    expect(page.locator('#view-home')).to_be_visible()
    assert page.evaluate('state.caseId') is None
    page.locator('#return-draft').click()
    expect(page.locator('#question')).to_have_value('new draft')
    # Even a previously captured entry cannot bind to the new session.
    page.evaluate('(entry) => restoreNavigation(entry)', old)
    expect(page.locator('#view-home')).to_be_visible()
    assert page.evaluate('state.caseId') is None


def test_refresh_has_no_fabricated_processing_or_mutation(page):
    requests = mutations(page)
    evidence(page)
    page.locator('#question').fill('not saved after creation')
    before = list(requests)
    page.reload()
    expect(page.locator('#view-home')).to_be_visible()
    expect(page.locator('#return-draft')).not_to_be_visible()
    expect(page.locator('#analysis-scene')).not_to_be_visible()
    assert requests == before


@pytest.mark.parametrize('width', [390, 768, 1440])
def test_navigation_affordances_geometry(page, width):
    page.set_viewport_size({'width': width, 'height': 1000})
    evidence(page)
    page.locator('.brand').click()
    expect(page.locator('#return-draft')).to_be_visible()
    assert_no_overflow(page)
    box = page.locator('#return-draft').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= width and box['height'] >= 44
    folder = Path(os.environ.get('NAVIGATION_SCREENSHOTS', '/tmp/dandoonjan-navigation'))
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / f'home-draft-{width}.png'), full_page=True)
    page.locator('#return-draft').click()
    page.locator('#files').set_input_files(PLAN)
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    page.go_back()
    page.route('**/api/cases/*/report', lambda r: r.fulfill(status=404, json={'detail': 'REPORT_NOT_READY'}))
    page.go_forward()
    expect(page.locator('#report-unavailable')).to_be_visible()
    assert_no_overflow(page)
    page.screenshot(path=str(folder / f'report-unavailable-{width}.png'), full_page=True)


def test_report_revalidation_response_does_not_hijack_navigation(page):
    requests = mutations(page)
    report(page)
    page.go_back()
    held = []
    page.route('**/api/cases/*/report', lambda r: held.append(r), times=1)
    page.go_forward()
    expect(page.locator('#view-report')).to_be_visible()
    expect(page.locator('#report-content')).to_be_empty()
    expect(page.locator('#print-report')).to_be_disabled()
    page.wait_for_function("navigation.current.view === 'report'")
    page.locator('.brand').click()
    before = list(requests)
    assert len(held) == 1
    held[0].continue_()
    page.wait_for_load_state('networkidle')
    expect(page.locator('#view-home')).to_be_visible()
    assert requests == before


def test_failed_processing_forward_resolves_to_evidence_without_replay(page):
    requests = mutations(page)
    evidence(page)
    held = []
    page.route('**/api/cases/*/process', lambda r: held.append(r), times=1)
    page.locator('#process-case').click()
    expect(page.locator('#activity')).to_have_text('در حال پردازش در سرور؛ لطفاً منتظر بمانید…')
    page.go_back()
    held[0].abort()
    expect(page.locator('#process-case')).to_be_enabled()
    before = list(requests)
    page.go_forward()
    expect(page.locator('#evidence-panel')).to_be_visible()
    expect(page.locator('#analysis-scene')).not_to_be_visible()
    expect(page.locator('#outcome-title')).to_have_text('پردازش کامل نشد')
    assert requests == before


def test_native_fragments_do_not_switch_workflow(page):
    page.locator('#landing-more').click()
    page.go_back()
    page.go_forward()
    expect(page.locator('#view-home')).to_be_visible()
    report(page)
    page.locator('#professional-view').click()
    page.locator('.result-disclosure summary').first.click()
    link = page.locator('.source-link:visible').first
    link.click()
    page.go_back()
    expect(page.locator('#print-report')).to_be_enabled()
    page.go_forward()
    expect(page.locator('#print-report')).to_be_enabled()
    expect(page.locator('#view-report')).to_be_visible()
