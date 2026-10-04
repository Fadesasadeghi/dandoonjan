"""Offline Chrome acceptance. Evidence stays separate from the protected RC."""
import importlib.util
import json
import os
from pathlib import Path
import pytest
from playwright.sync_api import expect

spec = importlib.util.spec_from_file_location('prior_browser', Path(__file__).with_name('test_p1_browser.py'))
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
server, browser, page = prior.server, prior.browser, prior.page
EVIDENCE = Path(os.environ.get('NEXT_PHASE_EVIDENCE', 'docs/next-phase/evidence'))


@pytest.mark.parametrize('width', [390, 768, 1440])
def test_four_stages_reports_pdf_and_fallback(page, width):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({'width': width, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    assert page.locator('canvas').count() == 0
    assert all('/reference/' not in src for src in page.locator('img').evaluate_all('(els) => els.map(e => e.src)'))
    prior.assert_no_overflow(page)
    page.screenshot(path=str(EVIDENCE / f'landing-{width}.png'), full_page=True)
    page.locator('#start-case').click()
    summary = page.locator('#intake-panel .dossier-section summary').first
    expect(summary).to_be_visible()
    summary.click()
    expect(page.locator('#symptoms')).to_be_visible()
    page.locator('#symptoms').fill('Synthetic cold sensitivity')
    page.locator('#duration').fill('3 days')
    prior.assert_no_overflow(page)
    page.screenshot(path=str(EVIDENCE / f'dossier-{width}.png'), full_page=True)
    page.locator('#back-home').click()
    # Delay only transport delivery to capture the real pending state.
    def delayed(route):
        response = route.fetch()
        page.screenshot(path=str(EVIDENCE / f'analysis-{width}.png'), full_page=True)
        route.fulfill(response=response)
    page.route('**/process', delayed)
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    expect(page.locator('[data-audience=patient]')).to_be_visible()
    page.locator('#professional-view').click()
    expect(page.locator('[data-audience=professional]')).to_be_visible()
    expect(page.locator('[data-audience=patient]')).not_to_be_visible()
    page.locator('#patient-view').click()
    prior.assert_no_overflow(page)
    page.screenshot(path=str(EVIDENCE / f'results-{width}.png'), full_page=True)
    page.locator('.result-disclosure summary').first.focus()
    page.keyboard.press('Enter')
    assert page.locator('.result-disclosure').first.get_attribute('open') is not None
    assert page.locator(':focus-visible').count() == 1
    # Export is generated from both audience sections in the shared report DOM.
    page.emulate_media(media='print')
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator('[data-audience=professional]')).to_be_visible()
    if width == 1440:
        cid = prior.case_id(page)
        recorded = page.evaluate('(cid) => fetch(`/api/cases/${cid}/report`).then(r => r.json())', cid)
        (EVIDENCE / 'offline-run.json').write_text(json.dumps(recorded, ensure_ascii=False, indent=2), encoding='utf-8')
        pdf = page.pdf(path=str(EVIDENCE / 'offline-report.pdf'), prefer_css_page_size=True)
        import pymupdf
        with pymupdf.open(stream=pdf, filetype='pdf') as doc:
            assert 1 <= len(doc) <= 12
            text = ''.join(p.get_text() for p in doc)
            assert recorded['review']['run']['model'] in text and 'MRUN-' in text and 'SNP-' in text
            for sheet in doc:
                assert sheet.get_text().strip()
                for block in sheet.get_text('blocks'):
                    assert block[0] >= 0 and block[2] <= sheet.rect.width + 1
                    assert block[1] >= 0 and block[3] <= sheet.rect.height + 1
            doc[0].get_pixmap().save(str(EVIDENCE / 'pdf-page-1.png'))
    assert not errors


def test_tooth_asset_failure_does_not_block_intake(page):
    page.route('**/hero-tooth-aqua.png', lambda route: route.abort())
    page.route('**/tooth.svg', lambda route: route.abort())
    page.reload()
    page.locator('#start-case').click()
    page.locator('#question').fill('Synthetic question')
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()


def test_process_saves_edits_in_visible_dossier(page):
    page.locator('#start-case').click()
    page.locator('#question').fill('Synthetic first question')
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    page.locator('#question').fill('Synthetic updated question')
    page.locator('#files').set_input_files(prior.PLAN)
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    cid = prior.case_id(page)
    assert page.evaluate('(cid) => fetch(`/api/cases/${cid}`).then(r => r.json())', cid)['question'] == 'Synthetic updated question'


@pytest.mark.parametrize('width,height', [(1440, 900), (768, 1024), (390, 844)])
def test_rendered_palette_contrast(page, width, height):
    """Keep the 4.5:1 requirement; sample the backdrop actually behind the text.

    The former body-color comparison ignored the approved home light field and
    solid CTA backgrounds. Share the landing pixel sampler so this wider flow
    suite verifies eight text/control samples at all three required viewports.
    """
    spec = importlib.util.spec_from_file_location(
        'landing_contrast', Path(__file__).with_name('test_landing_browser.py'))
    landing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(landing)
    landing.test_landing_rendered_contrast(page, width, height)
