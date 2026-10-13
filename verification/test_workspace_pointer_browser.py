"""Focused shared artwork interaction checks with local Chrome and synthetic auth.
No external providers. POINTER_PHASE=before records the pre-fix evidence.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from verification.test_p1_browser import server, browser, page

OUT = Path('.tmp-workspace-pointer')
PHASE = os.environ.get('POINTER_PHASE', 'after')
RING = '.landing-orbits span'
LIGHT = """e => ({light: e.style.getPropertyValue('--ring-light'),
 x:e.style.getPropertyValue('--ring-light-x'),y:e.style.getPropertyValue('--ring-light-y'),
 opacity:getComputedStyle(e,'::after').opacity,
 background:getComputedStyle(e,'::after').background,
 specular:getComputedStyle(e,'::before').background})"""
GEOMETRY = """el => {
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}};
 const css=(e,p)=>{const s=getComputedStyle(e,p);return Object.fromEntries(['width','height','top','left','bottom','transform','scale','translate','filter','background','opacity','maskImage'].map(k=>[k,s[k]]))};
 return {art:rect(el),tooth:rect(el.querySelector('.workspace-tooth')),
 reflection:rect(el.querySelector('.landing-reflection')),reflectionCSS:css(el.querySelector('.landing-reflection')),
 shadow:css(el,'::after'),form:rect(document.querySelector('#case-form')),
 rings:[...el.querySelectorAll('.landing-orbits span')].map(rect)};
}"""


def enter(page, path):
    OUT.mkdir(exist_ok=True)
    page.emulate_media(reduced_motion='no-preference')
    page.wait_for_load_state('networkidle')
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(1000)
    if path == 'sample':
        # Keep the shared sample workspace visible, independent of processing speed.
        page.route('**/api/demo/sample', lambda r: r.fulfill(status=503, json={
            'message_fa': 'درخواست کامل نشد. لطفاً دوباره تلاش کنید.'}))
    if path != 'home':
        page.locator('#start-case' if path == 'new' else '#start-sample').click()
        expect(page.locator('#case-form')).to_be_visible()
        if path == 'sample':
            expect(page.locator('#workspace-error')).to_be_visible()
    return page.locator('#view-home' if path == 'home' else '#view-workspace')


def settle(page):
    # The existing 160ms easing snaps to rest after converging within .001.
    page.wait_for_timeout(1800)


def save(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / f'{PHASE}-{name}.json').write_text(json.dumps(data, indent=2))


@pytest.mark.parametrize('path', ['home', 'new', 'sample'])
def test_pointer_light_follows_mouse_and_respects_motion(page, path):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    view = enter(page, path)
    ring = view.locator(RING).first
    page.mouse.move(1400, 20)
    settle(page)
    resting = ring.evaluate(LIGHT)
    bounds = ring.bounding_box()
    page.mouse.move(bounds['x'] + bounds['width'] / 2, bounds['y'])
    settle(page)
    top = ring.evaluate(LIGHT)
    if path != 'home':
        approved = view.locator('.landing-artwork').evaluate(GEOMETRY)
    page.screenshot(path=str(OUT / f'{PHASE}-{path}-lit.png'),
                    mask=[page.locator('#account-panel')])
    page.mouse.move(bounds['x'], bounds['y'] + bounds['height'] / 2)
    settle(page)
    left = ring.evaluate(LIGHT)
    page.mouse.move(1400, 20)
    settle(page)
    away = ring.evaluate(LIGHT)
    if path != 'home':
        idle = view.locator('.landing-artwork').evaluate(GEOMETRY)
        for key in ['art', 'tooth', 'reflection', 'reflectionCSS', 'shadow', 'form']:
            assert approved[key] == idle[key], key
    save(path, {'resting': resting, 'top': top, 'left': left, 'away': away})
    assert float(top['light'] or 0) > .5, f'{path}: pointer never activates the ring'
    assert top['x'] != left['x'] and top['y'] != left['y'], 'Light does not follow the pointer'
    assert top['background'] != left['background'] and top['specular'] != left['specular']
    assert float(top['opacity']) > .5 and float(away['opacity']) == 0
    assert not away['light']
    if path == 'home' and PHASE == 'after' and (OUT / 'before-home.json').exists():
        baseline = json.loads((OUT / 'before-home.json').read_text())
        assert {'resting': resting, 'top': top, 'left': left, 'away': away} == baseline
    page.mouse.move(bounds['x'] + bounds['width'] / 2, bounds['y'])
    settle(page)
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_timeout(100)
    assert not ring.evaluate(LIGHT)['light']
    page.mouse.move(bounds['x'], bounds['y'] + bounds['height'] / 2)
    page.wait_for_timeout(200)
    assert not ring.evaluate(LIGHT)['light']
    page.emulate_media(reduced_motion='no-preference')
    # Touch input must not activate decorative motion on a fine-pointer desktop.
    page.evaluate("""({x,y})=>window.dispatchEvent(new PointerEvent('pointermove',
      {clientX:x,clientY:y,pointerType:'touch'}))""", {'x': bounds['x'], 'y': bounds['y']})
    page.wait_for_timeout(200)
    assert not ring.evaluate(LIGHT)['light']
    assert not errors


@pytest.mark.parametrize('path', ['new', 'sample'])
def test_approved_composition_and_responsive_pointer(page, path):
    view = enter(page, path)
    result = {}
    for width in [1440, 1280, 1100, 1051, 1050, 768, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.evaluate('scrollTo(0,0)')
        page.mouse.move(width - 1, 0)
        settle(page)
        art = view.locator('.landing-artwork')
        assert page.evaluate('document.documentElement.scrollWidth') == width
        if width <= 1050:
            expect(art).to_be_hidden()
            continue
        geometry = art.evaluate(GEOMETRY)
        result[str(width)] = geometry
        if width == 1440:
            assert geometry['art']['w'] == 399
        if PHASE == 'after':
            ring = view.locator(RING).first
            b = ring.bounding_box()
            page.mouse.move(b['x'] + b['width'] / 2, b['y'])
            settle(page)
            assert float(ring.evaluate(LIGHT)['light'] or 0) > .5
            assert art.evaluate(GEOMETRY)['tooth'] == geometry['tooth']
            assert page.evaluate('document.documentElement.scrollWidth') == width
            # A scroll invalidates cached geometry; use the ring's new screen position.
            page.evaluate('scrollTo(0,100)')
            settle(page)
            b = ring.bounding_box()
            page.mouse.move(b['x'] + b['width'] / 2, b['y'])
            settle(page)
            assert float(ring.evaluate(LIGHT)['light'] or 0) > .5
    save(f'{path}-geometry', result)
    baseline = OUT / f'before-{path}-geometry.json'
    if PHASE == 'after' and baseline.exists():
        assert result == json.loads(baseline.read_text()), 'Approved composition changed'
