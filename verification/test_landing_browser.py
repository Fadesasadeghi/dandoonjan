"""Landing-only visual gate, real local Chrome / Mock. Never calls a live provider.
New evidence stays separate from historical next-phase acceptance artifacts.
"""
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

spec = importlib.util.spec_from_file_location('landing_prior', Path(__file__).with_name('test_p1_browser.py'))
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
server, browser, page = prior.server, prior.browser, prior.page
EVIDENCE = Path(os.environ.get('LANDING_BROWSER_EVIDENCE', 'docs/ui-redesign/gate-1/evidence/reference-match/lower-desktop-pass'))


def test_owner_approved_asset(page):
    tooth = page.locator('#landing-tooth')
    expect(tooth).to_have_attribute('src', '/ui/hero-tooth-aqua.png')
    from PIL import Image
    asset = Image.open(prior.ROOT / 'frontend/hero-tooth-aqua.png')
    assert asset.format == 'PNG' and asset.mode == 'RGBA'
    assert asset.size == (1175, 1338) and asset.getextrema()[3] == (0, 255)
    assert tooth.get_attribute('srcset') is None
    assert tooth.evaluate('(el) => el.naturalWidth === 1175 && el.naturalHeight === 1338')
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
    assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(158, 215, 224)'
    if width == 1440:
        assert page.locator('.landing-art').bounding_box()['x'] < page.locator('.landing-heading').bounding_box()['x']
    if width == 390:
        assert 230 <= page.locator('#landing-tooth').bounding_box()['height'] <= 270
        assert page.locator('#start-case').bounding_box()['width'] >= width - 40
    expect(page.locator('#start-case')).to_have_accessible_name('ساخت پرونده جدید')
    expect(page.locator('#start-sample')).to_have_accessible_name('مشاهده پرونده نمونه')
    # The limitation and both actions must fit the intended initial narrative.
    box = page.locator('.landing-limitation').bounding_box()
    assert box['y'] > page.locator('.landing-features').bounding_box()['y'] if width == 1440 else box['height'] > 0
    if width <= 768:
        title = page.locator('#landing-title').bounding_box()
        art = page.locator('#view-home .landing-artwork').bounding_box()
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
    for link in page.locator('.landing-nav a').all():
        page.keyboard.press('Tab')
        expect(link).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.locator('#start-case')).to_be_focused()
    assert page.locator('#start-case').evaluate('(el) => getComputedStyle(el).outlineStyle') == 'solid'
    for selector in ['#view-home .landing-artwork', '.landing-heading', '.landing-invitation']:
        assert page.locator(selector).evaluate('(el) => getComputedStyle(el).animationName') == 'none'
    assert page.evaluate('getComputedStyle(document.documentElement).scrollBehavior') == 'auto'
    page.screenshot(path=str(EVIDENCE / 'landing-keyboard-focus.png'))
    page.keyboard.press('Enter')
    expect(page.locator('#question')).to_be_focused()
    expect(page.locator('#view-workspace')).to_be_visible()


def test_failed_art_retains_composition_and_sample_flow(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.emulate_media(reduced_motion='reduce')
    page.route('**/hero-tooth-aqua.png', lambda route: route.abort())
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
    assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(158, 215, 224)'
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
    animations = page.locator('#view-home .landing-artwork').evaluate('el => el.getAnimations().map(a => ({state:a.playState, iterations:a.effect.getTiming().iterations}))')
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


@pytest.mark.parametrize('width,height', [(1440, 900), (768, 1024), (390, 844)])
def test_landing_rendered_contrast(page, width, height):
    """Measure actual composited backgrounds, including light fields/CTA gradient.
    This is scoped contrast evidence, not an automated accessibility certification.
    """
    from io import BytesIO
    from PIL import Image
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({'width': width, 'height': height})
    page.emulate_media(reduced_motion='reduce')
    page.reload()
    selectors = ['#landing-title', '#landing-title em', '.landing-eyebrow', '.lede',
                 '#start-case', '#start-sample', '#landing-more', '.landing-sample-note', '.landing-limitation',
                 '.brand', '.landing-auth', '.landing-faq h2', '.landing-faq summary', '.landing-story .landing-eyebrow',
                 '#landing-story-title', '.landing-story-copy p:first-child',
                 '.landing-story-copy p:last-child', '.site-footer']
    selectors += [f'.landing-nav a:nth-child({i})' for i in range(1,5)]
    selectors += [f'.landing-feature:nth-child({i}) {tag}' for i in range(1, 5) for tag in ['h2', 'p']]
    selectors += ['#landing-demo-title','.landing-story-support','.landing-faq-intro .landing-eyebrow']
    selectors += [f'.landing-process li:nth-child({i}) {tag}' for i in range(1,5) for tag in ['h3','p']]
    selectors += [f'.landing-faq details:nth-child({i}) {tag}' for i in range(1,4) for tag in ['summary','p']]
    page.locator('.landing-faq details').evaluate_all('(els)=>els.forEach(el=>el.open=true)')
    records = page.evaluate('''selectors => selectors.map(selector => {
        const el = document.querySelector(selector);
        let r = el.getBoundingClientRect();
        if (selector === '.brand') {
            const text = document.createRange();
            text.selectNodeContents(el.querySelector('.brand-home-wordmark') || el.firstChild);
            r = text.getBoundingClientRect();
        }
        const style = getComputedStyle(selector === '.brand' ? el.querySelector('.brand-home-wordmark') : el);
        return {selector, color: style.color.match(/[\\d.]+/g).slice(0,3).map(Number),
            font_size:parseFloat(style.fontSize), font_weight:parseFloat(style.fontWeight), x:r.x, y:r.y, width:r.width, height:r.height};
    }).filter(item => item.width > 0 && item.height > 0)''', selectors)
    # Capture real ink before hiding it; the heading mask uses only rendered glyphs.
    page.evaluate('document.fonts.ready')
    ink = Image.open(BytesIO(page.screenshot(full_page=True))).convert('RGB')
    # Hide ink only, retaining the exact composed backdrop for pixel measurement.
    page.add_style_tag(content='#view-home *, body:has(#view-home.active) .site-header *, body:has(#view-home.active) .site-footer {color:transparent!important;text-decoration-color:transparent!important}')
    background = Image.open(BytesIO(page.screenshot(full_page=True))).convert('RGB')
    def luminance(rgb):
        channels = [v/255 for v in rgb]
        return sum(w*(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4)
                   for w,v in zip([.2126,.7152,.0722], channels))
    results = []
    for item in records:
        fg = luminance(item['color'])
        samples = []
        # Actual production backgrounds remain unchanged for measurement.
        glyph_sample = True
        # Apply WCAG size/weight thresholds. Compare ink-on/ink-off pixels
        # to locate glyphs instead of measuring empty space or decorative icons.
        # At least half foreground coverage rejects faint antialias fringes and
        # excludes empty container space without assuming a font or text width.
        inset_x, inset_y, step = (0, 0, 1) if glyph_sample else (24, 10, 3)
        for y in range(max(0,int(item['y'])+inset_y), min(background.height,int(item['y']+item['height'])-inset_y), step):
            for x in range(max(0,int(item['x'])+inset_x), min(background.width,int(item['x']+item['width'])-inset_x), step):
                rgb = background.getpixel((x,y))
                if glyph_sample:
                    rendered = ink.getpixel((x,y))
                    full_difference = max(abs(a-b) for a,b in zip(item['color'],rgb))
                    ink_difference = max(abs(a-b) for a,b in zip(rendered,rgb))
                    if not full_difference or ink_difference < max(8, full_difference * .5):
                        continue
                bg = luminance(rgb)
                ratio = (max(fg,bg)+.05)/(min(fg,bg)+.05)
                samples.append((ratio, x, y, rgb))
        assert samples, (item['selector'], 'no representative text samples')
        minimum, x, y, rgb = min(samples)
        results.append({'selector':item['selector'], 'minimum_ratio':minimum,
                        'required_ratio':3.0 if item['font_size'] >= 24 or (item['font_size'] >= 18.6667 and item['font_weight'] >= 700) else 4.5, 'foreground_rgb':item['color'],
                        'worst_background_rgb':list(rgb), 'worst_pixel':[x,y],
                        'sample_count':len(samples),
                        'method':'rendered glyph interiors, >=50% coverage; no text shadows; actual composited background' if glyph_sample else 'composited text/control interior'})
    (EVIDENCE / f'landing-contrast-{width}.json').write_text(json.dumps({'scope':'actual rendered glyph backdrops; WCAG AA 3:1 large text, 4.5:1 normal text', 'results':results}, indent=2))
    failures = [(item['selector'],item['minimum_ratio']) for item in results if item['minimum_ratio'] < item['required_ratio']]
    assert not failures, failures


def test_header_treatment_stays_on_home(page):
    header = page.locator('.site-header')
    assert header.evaluate('el => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
    assert header.evaluate('el => getComputedStyle(el).borderBottomWidth') == '0px'
    expect(page.locator('.landing-nav')).to_be_visible()
    expect(page.locator('#resume-case')).not_to_be_visible()
    page.locator('#start-case').click()
    assert header.evaluate('el => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
    expect(page.locator('.landing-nav')).not_to_be_visible()
    assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(158, 215, 224)'
    expect(page.locator('#landing-auth')).not_to_be_visible()
    expect(page.locator('#view-workspace .workspace-tooth')).to_be_visible()
    page.locator('#back-home').click()
    assert header.evaluate('el => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'


def test_desktop_reference_geometry(page):
    page.set_viewport_size({'width': 1440, 'height': 900})
    page.emulate_media(reduced_motion='reduce')
    # Final owner-approved tooth element bounds; the protected PNG contains transparent margins.
    box = page.locator('#landing-tooth').bounding_box()
    for key, expected in zip(['x','y','width','height'], [232.574,152.031,377.853,429.938]):
        assert abs(box[key] - expected) < .1
    circles = page.locator('#view-home .landing-orbits span')
    expect(circles).to_have_count(4)
    for circle, target in zip(circles.all(), [(146,106,342,342),(332,191,383,383),(180,335,300,300),(365,345,300,300)]):
        actual = circle.bounding_box()
        assert all(abs(actual[key] - expected) <= 3 for key, expected in zip(['x','y','width','height'], target))
        assert circle.evaluate('el => parseFloat(getComputedStyle(el).borderTopWidth)') <= 2
        assert actual['width'] == actual['height']
        assert circle.evaluate('el => getComputedStyle(el).boxShadow') != 'none'
    for selector, width in [('#start-case',254.8),('#landing-more',189.28)]:
        actual = page.locator(selector).bounding_box()
        assert abs(actual['width'] - width) < 1 and abs(actual['height'] - 62.79) < 1
    expect(page.locator('.landing-feature')).to_have_count(4)
    icon = page.locator('.feature-icon').first.bounding_box()
    assert icon['width'] == icon['height'] == 52
    assert abs(icon['y'] + icon['height'] / 2 - 642) < 1
    auth = page.locator('#landing-auth').bounding_box()
    assert abs(auth['x'] - 110) <= 3 and abs(auth['y'] - 30) <= 3
    assert abs(auth['width'] - 148) <= 1 and abs(auth['height'] - 50) <= 1
    for selector in ['#landing-title', '.lede']:
        assert 820 <= page.locator(selector).bounding_box()['x'] <= 850
    assert page.locator('#landing-title').evaluate('el=>parseFloat(getComputedStyle(el).fontWeight)') >= 600
    assert page.locator('#view-home .landing-reflection img').get_attribute('src') == '/ui/hero-tooth-aqua.png'
    assert not page.locator('img').evaluate_all('(els)=>els.some(el=>el.src.includes("/reference/"))')


def test_desktop_reference_copy_and_placeholder(page):
    expect(page.locator('#landing-title')).to_have_text('همراه هوشمند سلامت دندان شما')
    expect(page.locator('.lede')).to_have_text('تحلیل تصاویر و توضیحات شما با هوش مصنوعی و ارائه راهنمایی‌های اولیه و قابل فهم، در کنار شما.')
    assert page.locator('.landing-nav a').all_text_contents() == ['خانه','درباره ما','چطور کار می‌کند؟','سوالات متداول']
    for link in page.locator('.landing-nav a').all():
        assert page.locator(link.get_attribute('href')).count() == 1
    auth = page.locator('#landing-auth')
    expect(auth).to_be_disabled()
    expect(auth).to_have_accessible_name('ورود / ثبت‌نام — در نسخهٔ آینده فعال خواهد شد')
    requests = []
    page.on('request', lambda request: requests.append(request.url))
    auth.click(force=True)
    page.wait_for_timeout(100)
    expect(page.locator('#view-home')).to_be_visible()
    assert not requests
    expect(page.locator('#sample-context')).to_contain_text('تصاویر را واقعاً تحلیل نمی‌کند')


def test_desktop_clean_typography_and_icons(page):
    for selector in ['#landing-title', '.lede', '.brand', '.landing-nav a', '.landing-feature h2', '.landing-feature p', '.landing-actions .btn']:
        for el in page.locator(selector).all():
            assert el.evaluate('el=>getComputedStyle(el).textShadow') == 'none'
            assert el.evaluate('el=>parseFloat(getComputedStyle(el).webkitTextStrokeWidth)') == 0
    expect(page.locator('#start-case')).to_have_text('ساخت پرونده جدید')
    expect(page.locator('#landing-more')).to_have_text('بیشتر بدانید‹')
    assert page.locator('#landing-more').get_attribute('href') == '#landing-story-title'
    assert page.locator('.landing-feature h2').all_text_contents() == ['راهنمایی قابل فهم','تحلیل هوشمند','سریع و ساده','حفظ حریم خصوصی']
    for svg in page.locator('.feature-icon svg').all():
        assert svg.get_attribute('fill') == 'none'
        assert svg.get_attribute('stroke') == 'currentColor'
        # Owner icon-assembly correction: 52px glass, 36px SVG viewport.
        assert svg.bounding_box()['width'] == 36


def test_desktop_soft_language_and_local_fonts(page):
    page.emulate_media(reduced_motion='reduce')
    cdp = page.context.new_cdp_session(page)
    cdp.send('DOM.enable'); cdp.send('CSS.enable')
    root = cdp.send('DOM.getDocument')['root']['nodeId']
    evidence = {}
    for selector in ['#landing-title', '.lede', '.landing-nav a', '.landing-feature h2']:
        node = cdp.send('DOM.querySelector', {'nodeId':root,'selector':selector})['nodeId']
        fonts = cdp.send('CSS.getPlatformFontsForNode', {'nodeId':node})['fonts']
        evidence[selector] = fonts
        (EVIDENCE / 'rendered-local-fonts.json').write_text(json.dumps(evidence,indent=2))
        assert page.locator(selector).first.evaluate('el=>getComputedStyle(el).fontFamily').startswith('Calibri')
        assert any(font['familyName'].startswith('Calibri') and font['glyphCount'] > 0 for font in fonts), fonts
    (EVIDENCE / 'rendered-local-fonts.json').write_text(json.dumps(evidence,indent=2))
    for selector,width,height in [('#start-case',254.8,62.79),('#landing-more',189.28,62.79),('#landing-auth',148,50)]:
        el=page.locator(selector); box=el.bounding_box()
        assert abs(box['width']-width)<1 and abs(box['height']-height)<1
        assert el.evaluate('el=>parseFloat(getComputedStyle(el).borderTopLeftRadius)') >= box['height']/2
    assert page.locator('.landing-invitation #start-sample, .landing-invitation #resume-case, .landing-invitation .landing-limitation').count() == 0
    expect(page.locator('.landing-product-context #start-sample')).to_be_visible()
    expect(page.locator('.landing-product-context .landing-limitation')).to_be_visible()
    assert page.locator('.landing-product-context #resume-case').count() == 1


def test_measured_desktop_rhythm(page):
    page.set_viewport_size({'width':1440,'height':900})
    page.emulate_media(reduced_motion='reduce'); page.reload()
    selectors=['.site-header','.brand','.landing-nav','#landing-auth','#landing-tooth','#view-home .landing-orbits span:nth-child(1)','#view-home .landing-orbits span:nth-child(2)','#view-home .landing-orbits span:nth-child(3)','#view-home .landing-orbits span:nth-child(4)','#landing-title','.lede','#start-case','#landing-more','.feature-icon','.landing-feature h2','.landing-feature p']
    records={selector:page.locator(selector).first.bounding_box() for selector in selectors}
    (EVIDENCE/'desktop-geometry.json').write_text(json.dumps(records,indent=2))
    title=records['#landing-title'];desc=records['.lede'];cta=records['#start-case']
    assert abs(desc['y']-(title['y']+title['height'])-24)<1
    assert abs(cta['y']-(desc['y']+desc['height'])-43.11)<1
    assert 480 <= cta['y'] <= 495
    icon = records['.feature-icon']
    assert icon['width'] == icon['height'] == 52
    assert abs(icon['y'] + icon['height'] / 2 - 642) < 1
    for el in page.locator('.landing-feature p').all():
        box=el.bounding_box(); assert box['y']+box['height'] < 900


def test_premium_finish_frozen_geometry_and_browser_chrome_allowance(page):
    page.emulate_media(reduced_motion='reduce'); page.reload()
    # Preserve the final composition across desktop viewport-height changes, not an obsolete raster.
    selectors=['#landing-tooth','#landing-title','.lede','#start-case','#landing-more']
    frozen={selector:page.locator(selector).bounding_box() for selector in selectors}
    # An outer window height does not equal its CSS viewport. Reserve 160px
    # for browser/OS chrome by also testing the unchanged desktop at 740px.
    page.set_viewport_size({'width':1440,'height':740})
    for selector in selectors:
        actual=page.locator(selector).bounding_box()
        assert all(abs(actual[key]-frozen[selector][key])<.1 for key in ['x','y','width','height'])
    prior.assert_no_overflow(page)
    # The approved lower row may extend below a short viewport; it must remain scroll-reachable.
    for el in page.locator('.landing-feature p').all():
        el.evaluate("el=>el.scrollIntoView({block:'center'})")
        box=el.bounding_box()
        assert 0 <= box['y'] and box['y']+box['height'] <= 740
    page.evaluate('window.scrollTo(0,0)')
    for selector in ['#landing-more','#landing-auth','.feature-icon']:
        assert page.locator(selector).first.evaluate('el=>getComputedStyle(el).backdropFilter') != 'none'
    reflection=page.locator('#view-home .landing-reflection')
    assert reflection.evaluate('el=>getComputedStyle(el).opacity') == '0.42'
    assert reflection.bounding_box()['height'] < 100
    page.set_viewport_size({'width':1440,'height':900})


def test_lower_background_has_no_1100px_seam(page):
    from io import BytesIO
    from PIL import Image
    page.set_viewport_size({'width':1440,'height':900})
    page.emulate_media(reduced_motion='reduce'); page.reload()
    screenshot=Image.open(BytesIO(page.screenshot(full_page=True))).convert('RGB')
    for x in [10,50,1380,1430]:
        a=screenshot.getpixel((x,1099)); b=screenshot.getpixel((x,1100))
        assert max(abs(c-d) for c,d in zip(a,b)) <= 3, (x,a,b)


def test_lower_desktop_glass_capture_and_native_faq(page):
    page.set_viewport_size({'width':1440,'height':900})
    page.emulate_media(reduced_motion='reduce'); page.reload()
    requests=[]; page.on('request',lambda request:requests.append(request.url))
    # Pin approved hero geometry/styles across FAQ interactions rather than comparing
    # historical rasters or compositor-sensitive blurred image pixels.
    hero_selectors=['#landing-title','#landing-tooth','.lede','#start-case','#landing-more',
                    '#view-home .landing-orbits span','.feature-icon']
    def hero_state():
        return {selector:page.locator(selector).evaluate_all("""els=>els.map(el=>{
            const r=el.getBoundingClientRect(), s=getComputedStyle(el);
            return {x:r.x,y:r.y,width:r.width,height:r.height,color:s.color,
                    background:s.background,border:s.border,opacity:s.opacity,
                    shadow:s.boxShadow,transform:s.transform,font:s.font};
        })""") for selector in hero_selectors}
    before=hero_state()
    expect(page.locator('.landing-product-context')).to_contain_text('از اطلاعات حساس در دمو استفاده نکنید')
    expect(page.locator('.landing-limitation')).to_contain_text('جایگزین معاینه، تشخیص یا تجویز درمان نیست')
    assert page.locator('.landing-process h3').all_text_contents() == ['مدارک و توضیحات','مرتب‌سازی شواهد','مشخص شدن ابهام‌ها','سؤال‌های بهتر برای دندان‌پزشک']
    details=page.locator('.landing-faq details'); expect(details).to_have_count(3)
    first=details.first; summary=first.locator('summary'); summary.focus(); page.keyboard.press('Enter')
    expect(first).to_have_attribute('open',''); expect(first.locator('p')).to_be_visible()
    assert summary.evaluate('el=>getComputedStyle(el).outlineStyle') == 'solid'
    page.keyboard.press('Space'); assert first.get_attribute('open') is None
    for item in details.all():
        item.locator('summary').click(); expect(item.locator('p')).to_be_visible()
        assert item.locator('summary').evaluate('el=>getComputedStyle(el).listStyleType') == 'none'
        assert item.locator('summary').evaluate('el=>getComputedStyle(el,"::after").borderBottomColor') == 'rgb(23, 98, 122)'
    details.evaluate_all('els=>els.forEach(el=>el.open=false)')
    page.evaluate('window.scrollTo(0,0)')
    assert hero_state()==before, 'FAQ changed approved hero geometry/styles'
    page.screenshot(path=str(EVIDENCE/'landing-1440-full.png'),full_page=True)
    for name,selector,offset in [('transition','.landing-product-context',190),('editorial','.landing-story',110),('faq','.landing-faq',110)]:
        page.evaluate('([selector,offset])=>window.scrollTo(0,document.querySelector(selector).getBoundingClientRect().top+window.scrollY-offset)',[selector,offset])
        page.screenshot(path=str(EVIDENCE/f'landing-1440-{name}.png'))
        prior.assert_no_overflow(page)
    assert all(urlparse(url).hostname=='127.0.0.1' for url in requests)
