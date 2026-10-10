"""Local middle surfaces: HEAD pixel freeze, stationary geometry, reduced motion."""
import math
import subprocess
from io import BytesIO

import pytest
from PIL import Image, ImageChops, ImageDraw
from verification.test_p1_browser import server, browser, page

TARGETS = '.landing-product-context, .landing-story-copy, .landing-story'


def settle(page):
    page.wait_for_function("Account.status === 'authenticated'")
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(1500)


def snapshot(page):
    return page.locator('#view-home *, .site-header *').evaluate_all("""els => els.map(el => {
      const s=getComputedStyle(el), b=el.getBoundingClientRect();
      return [el.textContent,[b.x,b.y,b.width,b.height],s.fontFamily,s.fontSize,s.fontWeight,
        s.lineHeight,s.letterSpacing,s.translate,s.scale,s.transform];
    })""")


def shot(page):
    return Image.open(BytesIO(page.screenshot(full_page=True))).convert('RGB')


def allowed_mask(page, size):
    mask = Image.new('L', size)
    draw = ImageDraw.Draw(mask)
    for selector in ['.landing-product-context', '.landing-story-copy']:
        b = page.locator(selector).bounding_box()
        radius = float(page.locator(selector).evaluate('el => parseFloat(getComputedStyle(el).borderRadius)'))
        y = b['y'] + page.evaluate('scrollY')
        draw.rounded_rectangle((b['x'], y, b['x']+b['width'], y+b['height']), radius, fill=255)
    b = page.locator('.landing-story').bounding_box()
    cx, cy = b['x']+b['width']+85-235, b['y']+page.evaluate('scrollY')-25+185
    # Only the existing 1px outline, with a 2px antialias allowance.
    points=[]
    for i in range(721):
        t=i*math.pi/360
        x,y=235*math.cos(t),185*math.sin(t)
        a=-18*math.pi/180
        points.append((cx+x*math.cos(a)-y*math.sin(a),cy+x*math.sin(a)+y*math.cos(a)))
    draw.line(points,fill=255,width=5)
    return mask


@pytest.mark.parametrize('width,reduced', [(1440,'no-preference'),(1440,'reduce'),(768,'reduce'),(390,'reduce')])
def test_pixels_outside_components_and_frozen_geometry(page, width, reduced):
    page.set_viewport_size({'width':width,'height':1000})
    page.emulate_media(reduced_motion=reduced)
    baseline={name:subprocess.check_output(['git','show',f'HEAD:frontend/{name}']) for name in ['landing.css','landing.js']}
    def handler(body, name):
        def fulfill(route):
            route.fulfill(body=body.decode('utf-8'),content_type='text/css' if name.endswith('css') else 'application/javascript')
        return fulfill
    for name,body in baseline.items():
        page.route(f'**/ui/{name}',handler(body,name))
    page.reload(); settle(page)
    page.locator('.landing-story-copy').scroll_into_view_if_needed()
    b=page.locator('.landing-product-context').bounding_box()
    page.mouse.move(b['x']+b['width']*.55,b['y']+b['height']*.5)
    settle(page)
    scroll=page.evaluate("scrollY")
    geometry=snapshot(page); before=shot(page)
    for name in baseline: page.unroute(f'**/ui/{name}')
    page.reload(); settle(page)
    page.evaluate('(top) => window.scrollTo({top,behavior:"instant"})',scroll)
    b=page.locator('.landing-product-context').bounding_box()
    page.mouse.move(b['x']+b['width']*.55,b['y']+b['height']*.5)
    settle(page)
    assert snapshot(page)==geometry
    after=shot(page)
    mask=allowed_mask(page,after.size) if width>1050 else Image.new('L',after.size)
    difference=ImageChops.difference(before,after)
    outside=difference.copy(); outside.paste((0,0,0),mask=mask)
    assert outside.getbbox() is None, outside.getbbox()
    if width>1050: assert difference.getbbox() is not None
    # An active step and outline must also stay within that same mask.
    if width==1440 and reduced=='no-preference':
        for selector in ['.landing-process li', '.landing-story']:
            b=page.locator(selector).first.bounding_box()
            x,y=(b['x']+b['width']-150,b['y']+30) if selector=='.landing-story' else (b['x']+b['width']-23,b['y']+23)
            page.mouse.move(x,y); settle(page)
            active=shot(page)
            diff=ImageChops.difference(after,active); diff.paste((0,0,0),mask=mask)
            assert diff.getbbox() is None, diff.getbbox()
            assert snapshot(page)==geometry


def test_local_tracking_stationary_reset_and_reduced_motion(page):
    page.emulate_media(reduced_motion='no-preference'); page.reload(); settle(page)
    page.locator('.landing-story-copy').scroll_into_view_if_needed(); settle(page)
    before=snapshot(page)
    card=page.locator('.landing-product-context')
    b=card.bounding_box()
    for fraction in [.25,.75]:
        page.mouse.move(b['x']+b['width']*fraction,b['y']+b['height']/2); settle(page)
        assert float(card.evaluate("el => el.style.getPropertyValue('--local-light')"))>.95
        assert float(card.evaluate("el => el.style.getPropertyValue('--local-x').replace('%','')"))==pytest.approx(fraction*100,abs=1)
    assert card.evaluate('el => getComputedStyle(el).overflow')=='clip'
    steps=page.locator('.landing-process li')
    b=steps.nth(1).bounding_box()
    page.mouse.move(b['x']+b['width']-23,b['y']+23); settle(page)
    levels=steps.evaluate_all("els => els.map(el => parseFloat(el.style.getPropertyValue('--local-light')||0))")
    assert levels[1]>.95 and levels[3]==0
    story=page.locator('.landing-story'); b=story.bounding_box()
    cx,cy=b['x']+b['width']+85-235,b['y']-25+185
    angles=[]
    for t in [0,math.pi/2]:
        a=-18*math.pi/180; x,y=235*math.cos(t),185*math.sin(t)
        page.mouse.move(cx+x*math.cos(a)-y*math.sin(a),cy+x*math.sin(a)+y*math.cos(a)); settle(page)
        assert float(story.evaluate("el => el.style.getPropertyValue('--local-light')"))>.95
        angles.append(float(story.evaluate("el => el.style.getPropertyValue('--local-angle').replace('deg','')")))
    assert abs(angles[1]-angles[0])>80
    assert story.evaluate("el => getComputedStyle(el,'::after').backgroundImage")=='none'
    assert snapshot(page)==before
    page.mouse.move(5,995); settle(page)
    assert page.locator(TARGETS+', .landing-process li').evaluate_all("els => els.every(el => !el.style.getPropertyValue('--local-light'))")
    page.emulate_media(reduced_motion='reduce')
    page.mouse.move(cx,cy); settle(page)
    assert card.evaluate("el => getComputedStyle(el,'::after').content")=='none'
    assert story.evaluate("el => getComputedStyle(el,'::after').content")=='none'
    assert page.locator(TARGETS+', .landing-process li').evaluate_all("els => els.every(el => !el.style.getPropertyValue('--local-light'))")
