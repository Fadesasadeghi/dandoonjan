"""Shared artwork regression against the landing source, real Chrome/local Mock app.
Temporary captures only; WORKSPACE_TOOTH_PHASE=before records the pre-fix baseline.
"""
import json
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import expect
from verification.test_p1_browser import server, browser, page

OUT = Path('.tmp-workspace-tooth')
PHASE = os.environ.get('WORKSPACE_TOOTH_PHASE', 'after')

COMPOSITION = """el => {
 const root=el.getBoundingClientRect();
 const item=e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e);return {
  x:(r.x-root.x)/root.width,y:(r.y-root.y)/root.height,w:r.width/root.width,h:r.height/root.height,
  border:c.border,colors:[c.borderTopColor,c.borderRightColor,c.borderBottomColor,c.borderLeftColor],
  background:c.background,filter:c.filter,opacity:c.opacity,shadow:c.boxShadow,objectFit:c.objectFit};};
 const pseudo=p=>{const c=getComputedStyle(el,p);return Object.fromEntries(['background','filter','transform','width','height','left','bottom','opacity'].map(k=>[k,c[k]]));};
 return {width:el.offsetWidth,height:el.offsetHeight,parts:[...el.querySelectorAll('.landing-orbits span,.landing-reflection,.landing-reflection img,img:is(#landing-tooth,.workspace-tooth)')].map(item),shadow:pseudo('::after'),mask:getComputedStyle(el.querySelector('.landing-orbits')).maskImage};
}"""


def record(page, name, data):
    folder=OUT/PHASE
    folder.mkdir(parents=True, exist_ok=True)
    (folder/f'{name}.json').write_text(json.dumps(data,indent=2))
    page.screenshot(path=str(folder/f'{name}.png'), full_page=True)
    if PHASE=='after' and (OUT/'before'/f'{name}.json').exists():
        old=json.loads((OUT/'before'/f'{name}.json').read_text())
        assert data['form']==old['form'], f'{name}: form geometry changed'
        assert data['scroll']<=old['scroll'], f'{name}: horizontal extent increased'


def geometry(page):
    return page.evaluate("""() => ({form:[...document.querySelectorAll('#view-workspace > :not(.workspace-art),#case-form input,#case-form textarea,#case-form details,#case-form button')].map(e=>{const r=e.getBoundingClientRect();return {id:e.id,x:r.x,y:r.y+scrollY,w:r.width,h:r.height}}),scroll:document.documentElement.scrollWidth})""")


def match_composition(actual, source):
    assert actual['width']==source['width']==399
    assert actual['height']==source['height']==454
    assert len(actual['parts'])==len(source['parts'])==7
    assert actual['mask']==source['mask']
    assert actual['shadow']==source['shadow']
    for a,b in zip(actual['parts'],source['parts']):
        for k in ['x','y','w','h']:
            assert a[k]==pytest.approx(b[k],abs=.0002), (k,a,b)
        for k in ['background','filter','opacity','shadow','objectFit']:
            assert a[k]==b[k], (k,a,b)
        if not a['border'].startswith('0px') or not b['border'].startswith('0px'):
            assert a['border']==b['border'] and a['colors']==b['colors']


def test_shared_workspace_artwork(page):
    if PHASE=='before' and (OUT/'before'/'landing.css').exists():
        page.route('**/ui/landing.css', lambda route: route.fulfill(path=str((OUT/'before'/'landing.css').resolve())))
    page.emulate_media(reduced_motion='reduce')
    page.reload()
    page.wait_for_function("Account.status === 'authenticated'")
    page.evaluate('document.fonts.ready')
    page.wait_for_load_state('networkidle')
    page.evaluate("Promise.all([...document.images].filter(i=>i.src).map(i=>i.decode().catch(()=>{})))")
    page.wait_for_timeout(250)
    folder=OUT/PHASE
    folder.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(folder/'landing.png'),full_page=True,mask=[page.locator('#account-panel')])
    source=page.locator('#view-home .landing-artwork').evaluate(COMPOSITION)
    (folder/'landing-composition.json').write_text(json.dumps(source,indent=2))
    if PHASE=='after' and (OUT/'before'/'landing.png').exists():
        assert ImageChops.difference(Image.open(OUT/'before'/'landing.png'),Image.open(folder/'landing.png')).getbbox() is None, 'Landing pixels changed'
    measured=[]
    overflow=[]
    page.locator('#start-case').click()
    expect(page.locator('#question')).to_be_visible()
    for width in [1440,1280,1100,1051,768,390]:
        page.set_viewport_size({'width':width,'height':1000})
        page.evaluate('scrollTo(0,0)')
        data=geometry(page)
        record(page,f'new-{width}',data)
        overflow.append((width,data['scroll']))
        if width>1050:
            composition=page.locator('#view-workspace .landing-artwork').evaluate(COMPOSITION)
            (folder/f'new-{width}-composition.json').write_text(json.dumps(composition,indent=2))
            measured.append(composition)
        if width<=1050:
            expect(page.locator('.workspace-art')).to_be_hidden()
    page.set_viewport_size({'width':1440,'height':1000})
    page.locator('#question').fill('Synthetic artwork regression question')
    page.locator('#case-form details').first.locator('summary').click()
    expect(page.locator('#symptoms')).to_be_visible()
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible(timeout=20000)
    # Fresh navigation retains authentication but starts a clean presentation.
    page.goto(page.url.split('/case/')[0])
    page.wait_for_function("Account.status === 'authenticated'")
    pending=[]
    page.route('**/api/demo/sample',lambda route:pending.append(route))
    page.locator('#start-sample').click()
    expect(page.locator('#sample-notice')).to_be_visible()
    page.wait_for_function("document.querySelector('#question').value.length > 0")
    page.evaluate('scrollTo(0,0)')
    record(page,'sample-1440',geometry(page))
    sample_composition=page.locator('#view-workspace .landing-artwork').evaluate(COMPOSITION)
    (folder/'sample-composition.json').write_text(json.dumps(sample_composition,indent=2))
    measured.append(sample_composition)
    assert pending
    pending[0].continue_()
    expect(page.locator('#view-report')).to_be_visible(timeout=60000)
    for composition in measured:
        match_composition(composition, source)
    assert all(width==scroll for width,scroll in overflow), f'Workspace horizontal overflow: {overflow}'


def test_workspace_scale_survives_reveal(page):
    page.emulate_media(reduced_motion='no-preference')
    page.reload()
    page.wait_for_function("Account.status === 'authenticated'")
    page.wait_for_function("document.querySelector('#view-home .landing-artwork').getAnimations().every(a=>a.playState==='finished')")
    source=page.locator('#view-home .landing-artwork').evaluate(COMPOSITION)
    page.locator('#start-case').click()
    page.wait_for_function("document.querySelector('#view-workspace .landing-artwork').getAnimations().every(a=>a.playState==='finished')")
    sizes=[]
    for width in [1440,1280,1100,1051]:
        page.set_viewport_size({'width':width,'height':1000})
        page.evaluate('scrollTo(0,0)')
        artwork=page.locator('#view-workspace .landing-artwork')
        match_composition(artwork.evaluate(COMPOSITION),source)
        size=artwork.evaluate("""el=>{const r=el.getBoundingClientRect(),p=el.parentElement.getBoundingClientRect();return {container:p.width,width:r.width,height:r.height,scale:getComputedStyle(el).scale,left:r.left,right:r.right,scroll:document.documentElement.scrollWidth}}""")
        assert size['width']==pytest.approx(size['container']*.87,abs=.01)
        assert size['height']==pytest.approx(size['width']*454/399,abs=.01)
        assert size['scroll']==width
        sizes.append({'viewport':width,**size})
    folder=OUT/'after'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'normal-motion-sizes.json').write_text(json.dumps(sizes,indent=2))
