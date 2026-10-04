"""Evidence visual checks against local SQLite/Mock, with optional temporary captures."""
import os
import tempfile
import subprocess
import io
from PIL import Image, ImageChops
from pathlib import Path

import pytest
from playwright.sync_api import expect
from verification.test_p1_browser import server, browser, page, PLAN, BAD, assert_no_overflow


@pytest.mark.parametrize('width', [1440, 768, 390])
def test_evidence_geometry_keyboard_and_upload(page, width):
    page.set_viewport_size({'width': width, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    output = os.environ.get('EVIDENCE_CAPTURE_DIR', str(Path(tempfile.gettempdir()) / 'dandoonjan-evidence'))
    phase = os.environ.get('EVIDENCE_CAPTURE_PHASE', 'after')

    def capture(name):
        if output:
            folder = Path(output)
            folder.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(folder / f'{phase}-{name}-{width}.png'), full_page=True)

    capture('landing')
    page.locator('#start-case').click()
    expect(page.locator('#question')).to_be_focused()
    page.locator('#question').fill('پرسش ساختگی دربارهٔ پیشنهاد درمان')
    page.locator('.dossier-section summary').first.focus()
    page.keyboard.press('Enter')
    expect(page.locator('#symptoms')).to_be_visible()
    page.keyboard.press('Tab')
    expect(page.locator('#symptoms')).to_be_focused()
    assert_no_overflow(page)
    capture('intake')
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    assert_no_overflow(page)
    capture('empty')
    page.locator('#document-role').select_option('prescription')
    page.locator('#document-role').focus()
    page.keyboard.press('Tab')
    expect(page.locator('#files')).to_be_focused()
    assert page.locator('#files').evaluate('(el) => getComputedStyle(el).outlineStyle') == 'solid'
    page.locator('#files').set_input_files([PLAN, BAD])
    expect(page.locator('#file-list li')).to_have_count(2)
    expect(page.locator('#file-list')).to_contain_text('در انتظار ارسال')
    assert_no_overflow(page)
    for selector in ['#question', '#document-role', '#files', '#process-case']:
        box = page.locator(selector).bounding_box()
        assert box['height'] >= 44
        assert box['x'] >= 0 and box['x'] + box['width'] <= width
    capture('selected')
    # Capture the true pending scene while transport is in flight.
    def processing(route):
        response = route.fetch()
        capture('processing')
        route.fulfill(response=response)
    page.route('**/process', processing)
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    expect(page.locator('#report-files [data-upload-state="rejected"]')).to_be_visible()
    assert_no_overflow(page)
    capture('report')
    page.locator('#add-evidence').click()
    expect(page.locator('#files')).to_be_focused()
    expect(page.locator('#file-list [data-upload-state="rejected"]')).to_be_visible()
    expect(page.locator('#file-list [data-upload-state="uploaded"]')).to_be_visible()
    assert_no_overflow(page)
    capture('validation')


@pytest.mark.parametrize('width', [1440, 768, 390])
def test_approved_screens_pixel_preservation(page, width):
    """Compare this edit to HEAD without changing the working tree or Git index."""
    page.set_viewport_size({'width': width, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    baseline_html = subprocess.check_output(['git', 'show', 'HEAD:frontend/index.html']).decode('utf-8')
    baseline_css = subprocess.check_output(['git', 'show', 'HEAD:frontend/landing.css']).decode('utf-8')
    output = Path(tempfile.gettempdir()) / 'dandoonjan-evidence'
    output.mkdir(parents=True, exist_ok=True)
    shots = {}
    home_styles = {}
    for phase in ['before', 'after']:
        page.context.clear_cookies()
        page.evaluate('sessionStorage.clear()')
        if phase == 'before':
            page.route('**/ui/landing.css', lambda r: r.fulfill(body=baseline_css, content_type='text/css'))
            page.route(page.url, lambda r: r.fulfill(body=baseline_html, content_type='text/html'))
        page.reload()
        page.evaluate('document.fonts.ready')
        page.evaluate('scrollTo(0, 0)')
        home_styles[phase] = page.locator('#view-home, #view-home *, .site-header, .site-header *, .site-footer').evaluate_all('els => els.map(e => {const s = getComputedStyle(e); return Array.from(s).map(k => [k, s.getPropertyValue(k)])})')
        shots[phase] = {'landing': page.screenshot(full_page=True)}
        page.screenshot(path=str(output / f'{phase}-approved-landing-{width}.png'), full_page=True)
        roles = page.locator('#document-role option').evaluate_all('(els) => els.map(e => e.value)')
        (output / f'{phase}-roles-{width}.txt').write_text(str(roles))
        def pending(route):
            response = route.fetch()
            shots[phase]['processing'] = page.screenshot(full_page=True)
            page.screenshot(path=str(output / f'{phase}-approved-processing-{width}.png'), full_page=True)
            route.fulfill(response=response)
        page.route('**/process', pending)
        page.locator('#start-sample').click()
        expect(page.locator('#view-report')).to_be_visible(timeout=30000)
        page.evaluate('document.fonts.ready')
        # Dynamic case/run IDs are hidden in the closed technical disclosures.
        shots[phase]['report'] = page.screenshot(full_page=True)
        page.screenshot(path=str(output / f'{phase}-approved-report-{width}.png'), full_page=True)
        page.unroute_all(behavior='wait')
    assert home_styles['before'] == home_styles['after']
    for screen in ['processing', 'report']:
        before = Image.open(io.BytesIO(shots['before'][screen])).convert('RGB')
        after = Image.open(io.BytesIO(shots['after'][screen])).convert('RGB')
        assert before.size == after.size
        assert ImageChops.difference(before, after).getbbox() is None, f'{screen} pixel regression at {width}'


@pytest.mark.parametrize('width,height', [(1440, 900), (768, 1024), (390, 844)])
def test_landing_contrast_matches_approved_baseline(page, width, height):
    """Record unchanged baseline failures; do not relax the existing 4.5:1 test."""
    from verification.test_landing_browser import test_landing_rendered_contrast
    failures = {}
    for phase in ['before', 'after']:
        if phase == 'before':
            html = subprocess.check_output(['git', 'show', 'HEAD:frontend/index.html']).decode('utf-8')
            css = subprocess.check_output(['git', 'show', 'HEAD:frontend/landing.css']).decode('utf-8')
            page.route(page.url, lambda r: r.fulfill(body=html, content_type='text/html'))
            page.route('**/ui/landing.css', lambda r: r.fulfill(body=css, content_type='text/css'))
        page.reload()
        try:
            test_landing_rendered_contrast(page, width, height)
            failures[phase] = None
        except AssertionError as error:
            failures[phase] = str(error)
        page.unroute_all(behavior='wait')
    assert failures['before'] == failures['after']
