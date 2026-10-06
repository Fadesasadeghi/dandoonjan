"""C+: approved C interaction with localized specular reflection, local Chrome and synthetic/mock server."""
import pytest
from verification.test_p1_browser import server, browser, page


def offsets(page):
    return page.locator('#view-home .landing-orbits span').evaluate_all("els => els.map(el => el.style.getPropertyValue('--ring-light'))")


def centers(page):
    return page.locator('#view-home .landing-orbits span').evaluate_all("els => els.map(el => {const r=el.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]})")


def tooth_box(page):
    return page.locator('#landing-tooth').bounding_box()


def near_ring(page):
    b = page.locator('#view-home .landing-orbits span').first.bounding_box()
    return b['x'] + b['width'], b['y'] + b['height'] / 2


def test_light_proximity_static_tooth_and_smooth_return(page):
    page.emulate_media(reduced_motion='no-preference')
    page.reload()
    page.wait_for_function("document.querySelector('#view-home .landing-artwork').getAnimations().every(a => a.playState === 'finished')")
    before = tooth_box(page)
    ring_centers = centers(page)
    assert offsets(page) == ['', '', '', '']
    x, y = near_ring(page)
    page.mouse.move(x, y)
    page.wait_for_timeout(80)
    early = float(offsets(page)[0])
    early_center = centers(page)[0]
    page.wait_for_timeout(700)
    late = float(offsets(page)[0])
    assert 0 < early < late <= .65
    ring = page.locator('#view-home .landing-orbits span').first
    assert float(ring.evaluate("el => getComputedStyle(el, '::after').opacity")) > .5
    assert float(ring.evaluate("el => el.style.getPropertyValue('--ring-light-x').replace('%','')")) > 95
    assert 'radial-gradient' in ring.evaluate("el => getComputedStyle(el, '::after').maskImage")
    assert tooth_box(page) == before
    for actual, original, vector, light in zip(centers(page), ring_centers,
            [(3, -4), (-4, -3), (4, 3), (-3, 5)], offsets(page)):
        level = float(light or 0) / .65
        assert actual == pytest.approx([original[0] + vector[0] * level, original[1] + vector[1] * level], abs=.01)
        assert ((actual[0]-original[0])**2 + (actual[1]-original[1])**2)**.5 <= 6
    assert 0 < early_center[0] - ring_centers[0][0] < centers(page)[0][0] - ring_centers[0][0]
    scales = page.locator('#view-home .landing-orbits span').evaluate_all("els => els.map(el => Number(el.style.scale || 1))")
    for value, maximum in zip(scales, [1.016, 1.020, 1.012, 1.018]):
        assert 1 <= value <= maximum
    assert page.locator('#view-home .landing-orbits span').evaluate_all("els => els.every(el => !el.style.rotate)")
    # Less light when 80px away from the first ring's outline.
    page.mouse.move(x + 80, y)
    page.wait_for_timeout(1000)
    assert 0 < float(offsets(page)[0]) < late
    page.mouse.move(1435, 890)
    page.wait_for_timeout(80)
    assert float(offsets(page)[0]) > 0
    page.wait_for_function("[...document.querySelectorAll('#view-home .landing-orbits span')].every(el => !el.style.getPropertyValue('--ring-light'))")
    assert float(ring.evaluate("el => getComputedStyle(el, '::after').opacity")) == 0
    assert page.locator('#view-home .landing-orbits span').evaluate_all("els => els.every(el => !el.style.scale && !el.style.translate)")
    assert tooth_box(page) == before
    assert centers(page) == ring_centers
    assert offsets(page) == ['', '', '', '']
    page.mouse.move(x, y)
    page.wait_for_timeout(300)
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("[...document.querySelectorAll('#view-home .landing-orbits span')].every(el => !el.style.getPropertyValue('--ring-light'))")
    page.mouse.move(x + 2, y)
    page.wait_for_timeout(200)
    assert offsets(page) == ['', '', '', '']
    assert tooth_box(page) == before


@pytest.mark.parametrize('width,touch,reduced', [(390, True, 'no-preference'), (768, False, 'no-preference'), (1440, True, 'no-preference'), (1440, False, 'reduce')])
def test_disabled_devices_and_reduced_motion(browser, server, width, touch, reduced):
    context = browser.new_context(viewport={'width': width, 'height': 900}, has_touch=touch, reduced_motion=reduced)
    try:
        page = context.new_page()
        page.goto(server)
        page.wait_for_function("document.querySelector('#view-home .landing-artwork').getAnimations().every(a => a.playState === 'finished')")
        before = tooth_box(page)
        page.mouse.move(*near_ring(page))
        page.wait_for_timeout(400)
        assert offsets(page) == ['', '', '', '']
        assert page.locator('#view-home .landing-orbits span').evaluate_all("els => els.every(el => !el.style.scale && !el.style.translate && getComputedStyle(el, '::after').content === 'none' && getComputedStyle(el, '::before').content === 'none')")
        assert tooth_box(page) == before
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize('width', [1440, 768, 390])
def test_frozen_geometry_and_typography_against_baseline(page, width):
    import subprocess
    baseline = subprocess.check_output(['git', 'show', 'HEAD:frontend/landing.css']).decode('utf-8')
    page.set_viewport_size({'width': width, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    def snapshot():
        page.wait_for_function("Account.status === 'authenticated'")
        page.evaluate('document.fonts.ready')
        return page.locator('#view-home, #view-home *, .site-header, .site-header *').evaluate_all("""els => els.map(el => {
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return {text:el.textContent, box:[r.x,r.y,r.width,r.height],
                type:[s.fontFamily,s.fontSize,s.fontWeight,s.fontStyle,s.lineHeight,s.letterSpacing,s.wordSpacing],
                src:el.getAttribute('src'), appearance:[s.color,s.backgroundColor,s.borderColor,s.borderWidth,s.borderRadius,s.opacity,s.boxShadow,s.filter]};
        })""")
    page.route('**/ui/landing.css', lambda route: route.fulfill(body=baseline, content_type='text/css'))
    page.reload()
    before = snapshot()
    page.unroute('**/ui/landing.css')
    page.reload()
    assert snapshot() == before


def test_specular_tracks_ring_angle_and_fades(page):
    page.emulate_media(reduced_motion='no-preference')
    page.reload()
    page.wait_for_function("document.querySelector('#view-home .landing-artwork').getAnimations().every(a => a.playState === 'finished')")
    ring = page.locator('#view-home .landing-orbits span').first
    b = ring.bounding_box()
    cx, cy = b['x'] + b['width']/2, b['y'] + b['height']/2
    before = tooth_box(page)
    def reflection():
        return ring.evaluate("""el => ({
            x:parseFloat(el.style.getPropertyValue('--ring-specular-x') || 100),
            y:parseFloat(el.style.getPropertyValue('--ring-specular-y') || 50),
            opacity:parseFloat(getComputedStyle(el, '::before').opacity),
            ambient:getComputedStyle(el, '::after').opacity
        })""")
    assert reflection()['opacity'] == 0
    page.mouse.move(cx + b['width']/2, cy)
    page.wait_for_timeout(1000)
    right = reflection()
    assert right['x'] > 98 and abs(right['y']-50) < 2
    assert .5 < right['opacity'] <= .65
    assert right['opacity'] == float(right['ambient'])
    page.mouse.move(cx, cy - b['height']/2)
    page.wait_for_timeout(80)
    intermediate = reflection()
    assert 50 < intermediate['x'] < right['x']
    page.wait_for_timeout(1000)
    top = reflection()
    assert abs(top['x']-50) < 2 and top['y'] < 2
    page.mouse.move(cx - b['width']/2, cy)
    page.wait_for_timeout(1000)
    left = reflection()
    assert left['x'] < 2 and abs(left['y']-50) < 2
    assert tooth_box(page) == before
    # Narrow masked surface reflection, separate from the unchanged ambient gradient.
    assert '38px' in ring.evaluate("el => getComputedStyle(el, '::before').backgroundImage")
    assert '110px' in ring.evaluate("el => getComputedStyle(el, '::after').backgroundImage")
    assert ring.evaluate("el => getComputedStyle(el, '::after').filter") == 'blur(2px)'
    page.mouse.move(1435, 890)
    page.wait_for_function("!document.querySelector('#view-home .landing-orbits span').style.getPropertyValue('--ring-light')")
    assert reflection()['opacity'] == 0
    assert ring.evaluate("el => !el.style.getPropertyValue('--ring-specular-x') && !el.style.getPropertyValue('--ring-specular-y')")
    assert tooth_box(page) == before
