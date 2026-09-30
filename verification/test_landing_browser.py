"""Landing-only visual gate, real local Chrome / Mock. Never calls a live provider.
New evidence stays separate from historical next-phase acceptance artifacts.
"""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

spec = importlib.util.spec_from_file_location('landing_prior', Path(__file__).with_name('test_p1_browser.py'))
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
server, browser, page = prior.server, prior.browser, prior.page
EVIDENCE = Path('docs/ui-redesign/gate-1/evidence/approved-hero')


def test_owner_approved_asset(page):
    tooth = page.locator('#landing-tooth')
    expect(tooth).to_have_attribute('src', '/ui/hero-tooth.png')
    assert tooth.get_attribute('srcset') is None
    assert tooth.evaluate('(el) => el.naturalWidth === 1312 && el.naturalHeight === 1199')
    assert page.locator('.landing-art svg').count() == 0


@pytest.mark.parametrize('width,height', [(1440, 900), (768, 1024), (390, 844)])
def test_landing_composition(page, width, height):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({'width': width, 'height': height})
    page.emulate_media(reduced_motion='reduce')
    requests, errors = [], []
    page.on('request', lambda r: requests.append(r.url))
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.reload()
    expect(page.locator('#landing-tooth')).to_be_visible()
    assert page.locator('#landing-tooth').evaluate('(el) => el.complete && el.naturalWidth > 0')
    prior.assert_no_overflow(page)
    expect(page.locator('#start-case')).to_have_accessible_name('ساخت پرونده')
    expect(page.locator('#start-sample')).to_have_accessible_name('مشاهده پرونده نمونه')
    # The limitation and both actions must fit the intended initial narrative.
    box = page.locator('.landing-limitation').bounding_box()
    assert box['y'] + box['height'] <= height
    if width <= 768:
        title = page.locator('#landing-title').bounding_box()
        art = page.locator('.landing-artwork').bounding_box()
        copy = page.locator('.lede').bounding_box()
        assert title['y'] < art['y'] < copy['y']
    assert all(urlparse(url).hostname == '127.0.0.1' for url in requests)
    assert not errors
    page.screenshot(path=str(EVIDENCE / f'landing-{width}.png'))
    page.screenshot(path=str(EVIDENCE / f'landing-{width}-full.png'), full_page=True)


def test_keyboard_reduced_motion_and_create(page):
    page.emulate_media(reduced_motion='reduce')
    page.reload()
    page.keyboard.press('Tab')
    expect(page.locator('.skip-link')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('.brand')).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('#start-case')).to_be_focused()
    assert page.locator('#start-case').evaluate('(el) => getComputedStyle(el).outlineStyle') == 'solid'
    for selector in ['.landing-artwork', '.landing-heading', '.landing-invitation']:
        assert page.locator(selector).evaluate('(el) => getComputedStyle(el).animationName') == 'none'
    assert page.evaluate('getComputedStyle(document.documentElement).scrollBehavior') == 'auto'
    page.screenshot(path=str(EVIDENCE / 'landing-keyboard-focus.png'))
    page.keyboard.press('Enter')
    expect(page.locator('#question')).to_be_focused()
    expect(page.locator('#view-workspace')).to_be_visible()


def test_failed_art_retains_composition_and_sample_flow(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.emulate_media(reduced_motion='reduce')
    page.route('**/hero-tooth.png', lambda route: route.abort())
    page.reload()
    expect(page.locator('.landing-fallback')).to_be_visible()
    expect(page.locator('#landing-tooth')).not_to_be_visible()
    prior.assert_no_overflow(page)
    page.screenshot(path=str(EVIDENCE / 'landing-390-fallback.png'))
    page.locator('#start-sample').focus()
    page.keyboard.press('Enter')
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    expect(page.locator('#report-content')).to_contain_text('کاملاً ساختگی')


def test_large_text_layout(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.emulate_media(reduced_motion='reduce')
    # Browser text scaling surrogate; verify expansion rather than clipping to fold.
    page.add_style_tag(content='#view-home {font-size:200%} #view-home h1 {font-size:88px} #view-home .lede {font-size:32px} #view-home .landing-limitation {font-size:26px}')
    prior.assert_no_overflow(page)
    expect(page.locator('#start-case')).to_be_visible()
    page.screenshot(path=str(EVIDENCE / 'landing-390-large-text.png'), full_page=True)


def test_normal_motion_recording(browser, server):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 900},
        reduced_motion='no-preference', record_video_dir=str(EVIDENCE / 'motion'),
        record_video_size={'width': 1440, 'height': 900})
    page = context.new_page()
    page.goto(server)
    page.wait_for_timeout(160)
    page.screenshot(path=str(EVIDENCE / 'landing-motion-early.png'))
    page.wait_for_timeout(1100)
    animations = page.locator('.landing-artwork').evaluate('el => el.getAnimations().map(a => ({state:a.playState, iterations:a.effect.getTiming().iterations}))')
    assert animations and all(a['state'] == 'finished' and a['iterations'] == 1 for a in animations)
    page.screenshot(path=str(EVIDENCE / 'landing-motion-settled.png'))
    page.locator('#start-case').hover()
    page.wait_for_timeout(350)
    page.locator('#start-case').click()
    expect(page.locator('#question')).to_be_focused()
    page.wait_for_timeout(300)
    version = browser.version
    context.close()
    page.video.save_as(str(EVIDENCE / 'landing-normal-motion.webm'))
    page.video.delete()
    (EVIDENCE / 'motion.json').write_text(json.dumps({'browser':version, 'animations':animations, 'scope':'finite entrance, hover, create action; local Chrome'}, indent=2))


def test_landing_rendered_contrast(page):
    """Measure actual composited backgrounds, including light fields/CTA gradient.
    This is scoped contrast evidence, not an automated accessibility certification.
    """
    from io import BytesIO
    from PIL import Image
    page.emulate_media(reduced_motion='reduce')
    page.reload()
    selectors = ['#landing-title', '#landing-title em', '.landing-eyebrow', '.lede',
                 '#start-case', '#start-sample', '.landing-sample-note', '.landing-limitation']
    records = page.evaluate('''selectors => selectors.map(selector => {
        const el = document.querySelector(selector), r = el.getBoundingClientRect();
        return {selector, color: getComputedStyle(el).color.match(/[\\d.]+/g).slice(0,3).map(Number),
            x:r.x, y:r.y, width:r.width, height:r.height};
    })''', selectors)
    # Hide ink only, retaining the exact composed backdrop for pixel measurement.
    page.add_style_tag(content='#view-home * {color:transparent!important;text-decoration-color:transparent!important}')
    background = Image.open(BytesIO(page.screenshot())).convert('RGB')
    def luminance(rgb):
        channels = [v/255 for v in rgb]
        return sum(w*(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4)
                   for w,v in zip([.2126,.7152,.0722], channels))
    results = []
    for item in records:
        fg = luminance(item['color'])
        ratios = []
        for y in range(max(0,int(item['y'])+10), min(background.height,int(item['y']+item['height'])-10), 3):
            for x in range(max(0,int(item['x'])+10), min(background.width,int(item['x']+item['width'])-10), 3):
                bg = luminance(background.getpixel((x,y)))
                ratios.append((max(fg,bg)+.05)/(min(fg,bg)+.05))
        assert ratios
        minimum = min(ratios)
        assert minimum >= 4.5, (item['selector'], minimum)
        results.append({'selector':item['selector'],'minimum_ratio':minimum})
    (EVIDENCE / 'landing-contrast.json').write_text(json.dumps({'scope':'sampled composited desktop text/CTA backgrounds', 'results':results}, indent=2))
