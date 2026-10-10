"""Modal-only computed-style/interaction checks. No screenshots or PDFs."""
import os
import subprocess
import re

import pytest
from playwright.sync_api import expect

from verification.auth_gate3_support import server, browser, page, open_auth


def test_password_visibility_toggle_mouse_and_keyboard_runtime(page, server):
    # Optional local URL lets owner-reported runtime issues be checked against
    # the same disposable browser harness without making the suite host-specific.
    url = os.environ.get('AUTH_VISIBILITY_BASE_URL', server['url'])
    if page.url != url + '/':
        page.goto(url)
    errors = []
    responses = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: responses.append((response.url, response.status)))
    page.reload(wait_until='load')
    assert page.evaluate("typeof Account !== 'undefined' && typeof Account.initialize === 'function'")
    expect(page.locator('#account-password-visibility')).to_be_attached()
    assert page.locator('#account-password-visibility').evaluate('el => typeof el.onclick') == 'function'
    open_auth(page)
    password = page.locator('#account-password')
    toggle = page.locator('#account-password-visibility')
    value = 'Synthetic password visibility check 12345'
    password.fill(value)
    page.evaluate("window.visibilityFormSubmitCount=0;document.getElementById('account-form').addEventListener('submit',()=>window.visibilityFormSubmitCount++)")
    expect(password).to_have_attribute('type', 'password')
    expect(toggle).to_have_attribute('aria-label', 'نمایش گذرواژه')
    toggle.click()
    expect(password).to_have_attribute('type', 'text')
    expect(password).to_have_value(value)
    expect(toggle).to_have_attribute('aria-label', 'پنهان کردن گذرواژه')
    expect(toggle).to_have_attribute('aria-pressed', 'true')
    expect(toggle.locator('.visibility-show')).to_be_hidden()
    expect(toggle.locator('.visibility-hide')).to_be_visible()
    toggle.focus()
    page.keyboard.press('Space')
    expect(password).to_have_attribute('type', 'password')
    expect(password).to_have_value(value)
    expect(toggle).to_have_attribute('aria-label', 'نمایش گذرواژه')
    expect(toggle).to_have_attribute('aria-pressed', 'false')
    expect(toggle.locator('.visibility-show')).to_be_visible()
    expect(toggle.locator('.visibility-hide')).to_be_hidden()
    assert page.evaluate('window.visibilityFormSubmitCount') == 0
    assert errors == []
    if os.environ.get('AUTH_VISIBILITY_BASE_URL'):
        assert any(url.endswith('/api/auth/me') and status == 404 for url, status in responses)
        assert any(url.endswith('/api/auth/csrf') and status == 404 for url, status in responses)


def test_failed_passive_auth_bootstrap_keeps_modal_controls_wired(page):
    responses = []
    methods = []
    page.on('response', lambda response: responses.append((response.url, response.status)))
    page.on('request', lambda request: methods.append((request.url, request.method)))
    page.route('**/api/auth/me', lambda route: route.fulfill(status=404, content_type='application/json', body='{"detail":{"code":"NOT_FOUND"}}'))
    page.route('**/api/auth/csrf', lambda route: route.fulfill(status=404, content_type='application/json', body='{"detail":{"code":"NOT_FOUND"}}'))
    page.reload(wait_until='load')
    page.wait_for_function("Account.status === 'unavailable'")
    assert page.locator('#account-password-visibility').evaluate('el => typeof el.onclick') == 'function'

    open_auth(page)
    page.wait_for_function("document.querySelector('#account-status').textContent.includes('در دسترس نیست')")
    password = page.locator('#account-password')
    toggle = page.locator('#account-password-visibility')
    value = 'Synthetic bootstrap failure password 12345'
    password.fill(value)
    page.evaluate("window.visibilityFormSubmitCount=0;document.getElementById('account-form').addEventListener('submit',()=>window.visibilityFormSubmitCount++)")
    toggle.click()
    expect(password).to_have_attribute('type', 'text')
    expect(password).to_have_value(value)
    expect(toggle).to_have_attribute('aria-label', 'پنهان کردن گذرواژه')
    expect(toggle.locator('.visibility-show')).to_be_hidden()
    expect(toggle.locator('.visibility-hide')).to_be_visible()
    toggle.click()
    expect(password).to_have_attribute('type', 'password')
    expect(password).to_have_value(value)
    expect(toggle).to_have_attribute('aria-label', 'نمایش گذرواژه')
    expect(toggle.locator('.visibility-show')).to_be_visible()
    expect(toggle.locator('.visibility-hide')).to_be_hidden()
    page.locator('#account-register-mode').click()
    expect(page.locator('#account-register-mode')).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('#account-login-mode')).to_have_attribute('aria-pressed', 'false')
    page.locator('#account-login-mode').click()
    expect(page.locator('#account-login-mode')).to_have_attribute('aria-pressed', 'true')
    page.locator('#account-close').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    assert page.evaluate('window.visibilityFormSubmitCount') == 0
    assert any(url.endswith('/api/auth/me') and status == 404 for url, status in responses)
    assert any(url.endswith('/api/auth/csrf') and status == 404 for url, status in responses)
    assert not any(url.endswith(('/api/auth/login', '/api/auth/register')) and method == 'POST' for url, method in methods)


def test_initialize_without_replacing_existing_app_hooks_after_auth_404(page):
    responses = []
    methods = []
    errors = []
    page.on('response', lambda response: responses.append((response.url, response.status)))
    page.on('request', lambda request: methods.append((request.url, request.method)))
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/api/auth/me', lambda route: route.fulfill(status=404, content_type='application/json', body='{"detail":{"code":"NOT_FOUND"}}'))
    page.route('**/api/auth/csrf', lambda route: route.fulfill(status=404, content_type='application/json', body='{"detail":{"code":"NOT_FOUND"}}'))
    page.reload(wait_until='load')
    page.wait_for_function("Account.status === 'unavailable'")
    page.evaluate("window.unhandledAccountRejections=[];addEventListener('unhandledrejection',event=>window.unhandledAccountRejections.push(String(event.reason)))")
    assert page.evaluate("typeof Account !== 'undefined' && typeof Account.initialize === 'function'")
    assert page.locator('#account-password-visibility').count() == 1

    result = page.evaluate("""async () => {
      try { await Account.initialize(); return {resolved:true}; }
      catch (error) { return {resolved:false, name:error.name, message:error.message}; }
    }""")
    assert result['resolved'], f"Account.initialize rejected: {result}"
    assert page.locator('#account-password-visibility').evaluate('el => typeof el.onclick') == 'function'
    assert page.locator('#account-login-mode').evaluate('el => typeof el.onclick') == 'function'
    assert page.locator('#account-register-mode').evaluate('el => typeof el.onclick') == 'function'
    assert page.locator('#account-close').evaluate('el => typeof el.onclick') == 'function'

    open_auth(page)
    password = page.locator('#account-password')
    toggle = page.locator('#account-password-visibility')
    value = 'Synthetic repeated initialization 12345'
    password.fill(value)
    page.evaluate("window.visibilityFormSubmitCount=0;document.getElementById('account-form').addEventListener('submit',()=>window.visibilityFormSubmitCount++)")
    toggle.click()
    expect(password).to_have_attribute('type', 'text')
    expect(password).to_have_value(value)
    expect(toggle).to_have_attribute('aria-label', 'پنهان کردن گذرواژه')
    expect(toggle.locator('.visibility-show')).to_be_hidden()
    expect(toggle.locator('.visibility-hide')).to_be_visible()
    toggle.focus()
    page.keyboard.press('Space')
    expect(password).to_have_attribute('type', 'password')
    expect(password).to_have_value(value)
    expect(toggle).to_have_attribute('aria-label', 'نمایش گذرواژه')
    expect(toggle.locator('.visibility-show')).to_be_visible()
    expect(toggle.locator('.visibility-hide')).to_be_hidden()
    page.locator('#account-register-mode').click()
    expect(page.locator('#account-register-mode')).to_have_attribute('aria-pressed', 'true')
    page.locator('#account-login-mode').click()
    expect(page.locator('#account-login-mode')).to_have_attribute('aria-pressed', 'true')
    page.locator('#account-close').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    assert page.evaluate('window.visibilityFormSubmitCount') == 0
    assert page.evaluate('window.unhandledAccountRejections') == []
    assert errors == []
    assert any(url.endswith('/api/auth/me') and status == 404 for url, status in responses)
    assert any(url.endswith('/api/auth/csrf') and status == 404 for url, status in responses)
    assert not any(url.endswith(('/api/auth/login', '/api/auth/register')) and method == 'POST' for url, method in methods)


def contrast(first, second):
    def luminance(rgb):
        values = [int(v) / 255 for v in rgb]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * weight
                   for v, weight in zip(values, [.2126, .7152, .0722]))
    low, high = sorted([luminance(first), luminance(second)])
    return (high + .05) / (low + .05)


def test_soft_aqua_controls_keep_contrast_and_disabled_distinction(page):
    open_auth(page)
    rgb = r'rgba?\((\d+), (\d+), (\d+)'
    for selector in ['#account-login-mode', '#account-submit']:
        control = page.locator(selector)
        style = control.evaluate('el => {const s=getComputedStyle(el); return {text:s.color,fill:s.backgroundImage}}')
        assert 'linear-gradient' in style['fill']
        stops = re.findall(rgb, style['fill'])
        assert stops == [('115', '184', '207'), ('158', '215', '224')]
        assert all(contrast(re.search(rgb, style['text']).groups(), stop) >= 4.5 for stop in stops)
    expect(page.locator('#account-register-mode')).to_have_css('background-image', 'none')
    page.locator('#account-submit').hover()
    style = page.locator('#account-submit').evaluate('el => {const s=getComputedStyle(el); return {text:s.color,fill:s.backgroundImage}}')
    assert all(contrast(re.search(rgb, style['text']).groups(), stop) >= 4.5 for stop in re.findall(rgb, style['fill']))
    page.locator('#account-email').focus()
    ring = page.locator('#account-email').evaluate('el => getComputedStyle(el).outlineColor')
    surface = page.locator('#account-dialog').evaluate('el => getComputedStyle(el).backgroundColor')
    assert contrast(re.search(rgb, ring).groups(), re.search(rgb, surface).groups()) >= 3
    # Styling-only probe; auth pending/disabled behavior has separate regression coverage.
    page.locator('#account-submit').evaluate('el => el.disabled = true')
    expect(page.locator('#account-submit')).to_have_css('opacity', '0.65')
    page.locator('#account-submit').evaluate('el => el.disabled = false')
    expect(page.locator('#account-submit')).to_have_css('opacity', '1')


@pytest.mark.parametrize('width', [320, 390, 768, 1440])
def test_auth_fields_icons_visibility_toggle_and_pill_geometry(page, width):
    page.set_viewport_size({'width': width, 'height': 844})
    open_auth(page)
    modes = page.locator('#account-modes')
    expect(modes).to_have_css('border-radius', '999px')
    expect(page.locator('#account-login-mode')).to_have_css('border-radius', '999px')
    expect(page.locator('#account-register-mode')).to_have_css('border-radius', '999px')
    email = page.locator('#account-email')
    password = page.locator('#account-password')
    envelope = page.locator('.account-email-field .account-field-icon')
    lock = page.locator('.account-password-field .account-field-icon')
    toggle = page.locator('#account-password-visibility')
    expect(envelope).to_have_count(1)
    expect(lock).to_have_count(1)
    expect(toggle).to_have_count(1)
    assert envelope.get_attribute('aria-hidden') == 'true'
    assert lock.get_attribute('aria-hidden') == 'true'
    assert toggle.get_attribute('type') == 'button'
    assert toggle.get_attribute('aria-label') == 'نمایش گذرواژه'
    assert toggle.get_attribute('aria-pressed') == 'false'
    email_box, envelope_box = email.bounding_box(), envelope.bounding_box()
    assert envelope_box['x'] >= email_box['x'] + email_box['width'] - 44
    password_box, lock_box, toggle_box = password.bounding_box(), lock.bounding_box(), toggle.bounding_box()
    assert lock_box['x'] >= password_box['x'] + password_box['width'] - 44
    assert toggle_box['x'] + toggle_box['width'] <= password_box['x'] + 54
    assert page.locator('#account-dialog').evaluate('el => el.scrollWidth <= el.clientWidth')
    dialog_box = page.locator('#account-dialog').bounding_box()
    assert dialog_box['x'] >= 0 and dialog_box['x'] + dialog_box['width'] <= width
    assert email.evaluate('el => getComputedStyle(el).paddingRight') == '44px'
    assert password.evaluate('el => [getComputedStyle(el).paddingLeft,getComputedStyle(el).paddingRight]') == ['54px', '44px']

    value = 'Synthetic password value 12345'
    password.fill(value)
    page.evaluate("window.visibilityFormSubmitCount=0;document.getElementById('account-form').addEventListener('submit',()=>window.visibilityFormSubmitCount++)")
    page.keyboard.press('Tab')
    toggle.focus()
    assert toggle.evaluate('el => {const s=getComputedStyle(el); return [s.outlineStyle,s.outlineWidth,s.outlineOffset]}') == ['solid', '2px', '2px']
    # Exercise the actual pointer path; the earlier regression only used Enter.
    toggle.click()
    expect(password).to_have_attribute('type', 'text')
    expect(toggle).to_have_attribute('aria-label', 'پنهان کردن گذرواژه')
    expect(toggle.locator('.visibility-show')).to_be_hidden()
    expect(toggle.locator('.visibility-hide')).to_be_visible()
    expect(password).to_have_value(value)
    page.keyboard.press('Enter')
    expect(password).to_have_attribute('type', 'password')
    expect(toggle).to_have_attribute('aria-label', 'نمایش گذرواژه')
    expect(toggle.locator('.visibility-show')).to_be_visible()
    expect(toggle.locator('.visibility-hide')).to_be_hidden()
    expect(toggle).to_have_attribute('aria-pressed', 'false')
    expect(password).to_have_value(value)
    toggle.click()
    expect(password).to_have_attribute('type', 'text')
    expect(toggle).to_have_attribute('aria-label', 'پنهان کردن گذرواژه')
    expect(password).to_have_value(value)
    page.keyboard.press('Space')
    expect(password).to_have_attribute('type', 'password')
    expect(toggle).to_have_attribute('aria-label', 'نمایش گذرواژه')
    expect(password).to_have_value(value)
    assert page.evaluate('window.visibilityFormSubmitCount') == 0
    expect(password).to_have_attribute('autocomplete', 'current-password')

    page.locator('#account-register-mode').click()
    expect(page.locator('#account-login-mode')).to_have_attribute('aria-pressed', 'false')
    expect(page.locator('#account-register-mode')).to_have_attribute('aria-pressed', 'true')
    expect(password).to_have_attribute('autocomplete', 'new-password')
    expect(password).to_have_value('')
    email.fill('invalid address')
    page.locator('#account-submit').click()
    expect(email).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#account-status')).to_contain_text('ایمیل معتبر')


def presentation(page):
    page.mouse.move(0, 0)
    page.evaluate('scrollTo({left:0, top:0, behavior:"instant"})')
    return page.locator('#view-home, #view-home *, .site-header, .site-header *').evaluate_all('''els => els.map(el => {
        const s = getComputedStyle(el), r = el.getBoundingClientRect();
        return [r.x, r.y, r.width, r.height, ...Array.from(s).map(k => s.getPropertyValue(k))];
    })''')


def typography(page):
    return page.locator('#account-dialog, #account-dialog *').evaluate_all('''els => els.map(el => {
        const s = getComputedStyle(el);
        return [s.fontFamily, s.fontSize, s.fontWeight, s.lineHeight, s.letterSpacing];
    })''')


@pytest.mark.parametrize('width', [320, 390, 768, 1440])
def test_modal_focus_geometry_and_frozen_presentation(page, width):
    page.set_viewport_size({'width': width, 'height': 844})
    page.emulate_media(reduced_motion='reduce')
    baseline = subprocess.check_output(['git', 'show', 'HEAD:frontend/account.css']).decode('utf-8')
    page.route('**/ui/account.css', lambda r: r.fulfill(body=baseline, content_type='text/css'))
    page.reload()
    page.wait_for_function("Account.status === 'anonymous'")
    page.evaluate('document.fonts.ready')
    original_home = presentation(page)
    open_auth(page)
    original_type = typography(page)
    page.keyboard.press('Escape')
    page.unroute('**/ui/account.css')
    page.reload()
    page.wait_for_function("Account.status === 'anonymous'")
    page.evaluate('document.fonts.ready')
    assert presentation(page) == original_home
    open_auth(page)
    assert typography(page) == original_type
    expect(page.locator('#account-email')).to_be_focused()
    assert page.locator('#account-dialog').evaluate('el => getComputedStyle(el).direction') == 'rtl'
    assert page.locator('#account-dialog').evaluate('el => el.scrollWidth <= el.clientWidth')
    box = page.locator('#account-dialog').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= width
    for selector in ['#account-email', '#account-password', '#account-submit', '#account-close', '#account-login-mode', '#account-register-mode']:
        control = page.locator(selector)
        page.keyboard.press('Tab')
        control.focus()
        assert control.bounding_box()['height'] >= 44
        style = control.evaluate('el => {const s = getComputedStyle(el); return [s.outlineStyle,s.outlineWidth,s.outlineOffset,s.boxShadow]}')
        assert style == ['solid', '2px', '2px', 'none']
    page.keyboard.press('Space')
    expect(page.locator('#account-register-mode')).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('#account-password')).to_have_attribute('autocomplete', 'new-password')
    page.locator('#account-submit').click()
    expect(page.locator('#account-email')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#account-status')).to_be_visible()
    expect(page.locator('#account-status')).to_have_attribute('role', 'status')
    expect(page.locator('#account-status')).to_contain_text('ایمیل معتبر')
    for key in ['Tab', 'Shift+Tab']:
        for _ in range(8):
            page.keyboard.press(key)
            assert page.evaluate("document.getElementById('account-dialog').contains(document.activeElement)")
    page.locator('#account-close').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('#landing-auth')).to_be_focused()
    open_auth(page)
    page.keyboard.press('Escape')
    expect(page.locator('#account-dialog')).not_to_be_visible()
