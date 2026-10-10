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
        assert page.locator('#view-home .landing-artwork').evaluate("el => !el.style.getPropertyValue('--tooth-sheen') && getComputedStyle(el, '::before').content === 'none'")
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
                src:el.getAttribute('src'), appearance:[s.color,s.backgroundColor,s.borderColor,s.borderWidth,s.borderRadius,s.opacity,el.matches(".landing-product-context, .landing-story-copy, .landing-process li > span") ? "local surface polish" : s.boxShadow,s.filter]};
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


def test_tooth_reflection_static_asset_geometry_and_tracking(page):
    import hashlib
    import subprocess
    from pathlib import Path
    asset = Path(__file__).resolve().parents[1] / 'frontend/hero-tooth-aqua.png'
    assert hashlib.sha256(asset.read_bytes()).digest() == hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:frontend/hero-tooth-aqua.png'])).digest()
    page.emulate_media(reduced_motion='no-preference')
    page.reload()
    page.wait_for_function("document.querySelector('#view-home .landing-artwork').getAnimations().every(a => a.playState === 'finished')")
    tooth = page.locator('#landing-tooth')
    artwork = page.locator('#view-home .landing-artwork')
    before = tooth_box(page)
    def state():
        return artwork.evaluate("""el => ({opacity:parseFloat(getComputedStyle(el,'::before').opacity),
          x:parseFloat(el.style.getPropertyValue('--tooth-sheen-x') || 50),
          y:parseFloat(el.style.getPropertyValue('--tooth-sheen-y') || 50),
          mask:getComputedStyle(el,'::before').maskImage})""")
    def physical():
        return tooth.evaluate("el => {const s=getComputedStyle(el);return [s.transform,s.translate,s.rotate,s.scale,s.animationName]}")
    baseline_physical = physical()
    assert baseline_physical == ['matrix(0.947, 0, 0, 0.947, 0, 0)', 'none', 'none', 'none', 'none']
    assert state()['opacity'] == 0
    page.mouse.move(before['x'] + before['width']*.7, before['y'] + before['height']*.35)
    page.wait_for_timeout(1200)
    right = state()
    assert .43 < right['opacity'] <= .45
    assert right['x'] > 65 and right['y'] < 40
    assert 'hero-tooth-aqua.png' in right['mask']
    # Verify visible pixel contrast on opaque tooth surface, beyond CSS values.
    from io import BytesIO
    from PIL import Image, ImageChops
    lit = Image.open(BytesIO(tooth.screenshot())).convert('RGB')
    hide = page.add_style_tag(content='#view-home .landing-artwork::before {opacity:0!important}')
    unlit = Image.open(BytesIO(tooth.screenshot())).convert('RGB')
    hide.evaluate('el => el.remove()')
    alpha = Image.open(asset).getchannel('A')
    factor = min(lit.width / alpha.width, lit.height / alpha.height)
    resized = alpha.resize((round(alpha.width * factor), round(alpha.height * factor)))
    surface = Image.new('L', lit.size)
    surface.paste(resized, ((lit.width-resized.width)//2, (lit.height-resized.height)//2))
    differences = ImageChops.difference(lit, unlit)
    visible_pixels = sum(max(differences.getpixel((x,y))) >= 6 for y in range(lit.height) for x in range(lit.width) if surface.getpixel((x,y)) >= 250)
    assert visible_pixels >= 200, visible_pixels
    background = artwork.evaluate("el => getComputedStyle(el, '::before').backgroundImage")
    assert 'linear-gradient' in background
    import re
    colors = re.findall(r'rgba?\(([^)]+)\)', background)
    assert colors and all([float(c) for c in color.split(',')[:3]] == [255,255,255] for color in colors)
    # Verify four cardinal light directions and rendered changes across the same
    # opaque surface pixels, independent of the tooth's original shading.
    shots = {}
    for direction, px, py, expected_angle in [('right',.8,.5,-90), ('left',.2,.5,90), ('top',.5,.2,180), ('bottom',.5,.8,0)]:
        page.mouse.move(before['x'] + before['width']*px, before['y'] + before['height']*py)
        page.wait_for_timeout(1400)
        angle = float(artwork.evaluate("el => el.style.getPropertyValue('--tooth-light-angle').replace('deg','')"))
        error = (angle - expected_angle + 180) % 360 - 180
        assert abs(error) < 1
        shots[direction] = Image.open(BytesIO(tooth.screenshot())).convert('RGB')
        assert tooth_box(page) == before and physical() == baseline_physical
    for facing, opposite, axis, upper in [('right','left',0,False), ('left','right',0,True), ('top','bottom',1,True), ('bottom','top',1,False)]:
        changes=[]
        for y in range(surface.height):
            for x in range(surface.width):
                coordinate, length = (x, surface.width) if axis == 0 else (y, surface.height)
                in_side = coordinate < length*.4 if upper else coordinate > length*.6
                if in_side and surface.getpixel((x,y)) >= 250:
                    changes.append(sum(shots[facing].getpixel((x,y)))/3 - sum(shots[opposite].getpixel((x,y)))/3)
        assert changes and sum(changes)/len(changes) > 1
    page.mouse.move(before['x'] + before['width']*.3, before['y'] + before['height']*.65)
    page.wait_for_timeout(1200)
    left = state()
    assert left['x'] < 35 and left['y'] > 60
    assert tooth_box(page) == before and physical() == baseline_physical
    page.mouse.move(1435, 890)
    page.wait_for_function("!document.querySelector('#view-home .landing-artwork').style.getPropertyValue('--tooth-sheen')")
    assert state()['opacity'] == 0
    assert tooth_box(page) == before and physical() == baseline_physical
    page.mouse.move(before['x'] + before['width']*.7, before['y'] + before['height']*.35)
    page.wait_for_timeout(300)
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("!document.querySelector('#view-home .landing-artwork').style.getPropertyValue('--tooth-sheen')")
    assert artwork.evaluate("el => getComputedStyle(el, '::before').content") == 'none'
