"""Tests first: ACCOUNT UI, session and browser boundaries; synthetic/offline only."""
import json
import sqlite3

import pytest
from playwright.sync_api import expect
from verification.auth_gate3_support import (
    server, browser, page, PASSWORD, PLAN, email, open_auth, register, login,
    signed_in, create, report, assert_cleared,
)


def test_entry_modes_registration_requires_explicit_login(page, server):
    address = register(page)
    assert page.request.get(server['url'] + '/api/auth/me').status == 401
    expect(page.locator('#account-title')).to_have_text('ورود به حساب')
    expect(page.locator('#account-password')).to_have_attribute('autocomplete', 'current-password')
    page.locator('#account-register-mode').click()
    expect(page.locator('#account-password')).to_have_attribute('autocomplete', 'new-password')
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-login-mode').click()
    expect(page.locator('#account-password')).to_have_value('')
    login(page, address)


@pytest.mark.parametrize('code,status,message', [
    ('REGISTRATION_FAILED',400,'ثبت‌نام انجام نشد؛ اطلاعات را بررسی کنید.'),
    ('INVALID_CREDENTIAL_INPUT',422,'اطلاعات واردشده معتبر نیست.'),
    ('AUTH_RATE_LIMITED',429,'کمی بعد دوباره تلاش کنید.'),
])
def test_registration_error_contract(page, code, status, message):
    open_auth(page)
    page.locator('#account-register-mode').click()
    requests = []
    page.on('request', lambda r: requests.append(r) if r.url.endswith('/auth/register') else None)
    page.route('**/api/auth/register', lambda r: r.fulfill(status=status,
        headers={'Retry-After':'900'} if status == 429 else {},
        json={'detail':{'code':code,'message_fa':message}}))
    page.locator('#account-email').fill(email())
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    expect(page.locator('#account-status')).to_contain_text(message)
    assert len(requests) == 1
    if status == 429:
        expect(page.locator('#account-status')).to_contain_text('۱۵')
    assert page.evaluate('Account.user') is None


def test_real_duplicate_and_invalid_input(page):
    address = register(page)
    page.locator('#account-register-mode').click()
    page.locator('#account-password').fill('short')
    page.locator('#account-submit').click()
    expect(page.locator('#account-password')).to_have_attribute('aria-invalid','true')
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    expect(page.locator('#account-status')).to_contain_text('ثبت‌نام انجام نشد')
    assert page.locator('#account-email').input_value() == address


@pytest.mark.parametrize('reason', ['wrong','unknown','disabled'])
def test_login_generic_failure(page, server, reason):
    address = register(page)
    if reason == 'disabled':
        with sqlite3.connect(server['database']) as db:
            db.execute("UPDATE users SET status='DISABLED' WHERE email=?", (address,))
    page.locator('#account-email').fill(email() if reason == 'unknown' else address)
    page.locator('#account-password').fill(PASSWORD if reason != 'wrong' else 'Wrong synthetic passphrase 123')
    page.locator('#account-submit').click()
    expect(page.locator('#account-status')).to_have_text('اطلاعات ورود معتبر نیست.')
    assert page.evaluate('Account.user') is None


def test_ui_login_normal_mutations_and_namespace_csrf(page, server):
    signed_in(page)
    sent = []
    page.on('request', lambda r: sent.append((r.method,r.url,r.headers.get('x-csrf-token')))
            if r.method in ('POST','PUT','PATCH') and '/cases' in r.url else None)
    report(page)
    normal = [row for row in sent if '/api/cases' in row[1]]
    assert {row[1].split('/api/cases')[1].split('/')[-1] for row in normal} >= {'','dossier','artifacts','process'}
    assert {'POST','PATCH','PUT'} <= {row[0] for row in normal}
    assert all(row[2] and len(row[2]) == 64 for row in normal)
    account_token = normal[0][2]
    account = page.request.get(server['url']+'/api/auth/me').json()['public_id']
    stored = page.evaluate("JSON.parse(sessionStorage.getItem('dandoonjan_active_case'))")
    assert stored['version'] == 2 and stored['namespace'] == 'ACCOUNT' and stored['accountId'] == account
    page.locator('.brand').click()
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    demo = [row for row in sent if '/api/demo/cases' in row[1]]
    assert demo and all(row[2] and row[2] != account_token for row in demo)
    assert page.request.get(server['url']+'/api/auth/me').status == 200
    page.locator('.brand').click()
    page.locator('#start-case').click()
    assert page.evaluate('state.sample') is False
    assert page.evaluate('state.caseId') is None
    assert page.locator('#question').input_value() == ''
    assert page.locator('#report-export').inner_text() == ''


def test_logout_204_clears_all_material_and_a_to_b(page, server):
    a = signed_in(page)
    report(page)
    page.evaluate("ReportExport.prepare(state.report, 'professional'); sessionStorage.setItem('unrelated','keep'); localStorage.setItem('unrelated','keep')")
    old_session = page.evaluate('navigation.session')
    page.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('از حساب خارج شدید')
    assert page.request.get(server['url']+'/api/auth/me').status == 401
    assert_cleared(page)
    assert page.evaluate('navigation.session') != old_session
    assert page.evaluate("sessionStorage.getItem('unrelated')") == 'keep'
    assert page.evaluate("localStorage.getItem('unrelated')") == 'keep'
    b = signed_in(page)
    assert a != b
    assert_cleared(page)


@pytest.mark.parametrize('change', ['expired','revoked','disabled'])
def test_ended_session_clears_work(page, server, change):
    address = signed_in(page)
    create(page)
    page.locator('#files').set_input_files(PLAN)
    with sqlite3.connect(server['database']) as db:
        if change == 'disabled': db.execute("UPDATE users SET status='DISABLED' WHERE email=?", (address,))
        else:
            field = 'expires_at' if change == 'expired' else 'revoked_at'
            db.execute(f"UPDATE auth_sessions SET {field}='2000-01-01 00:00:00' WHERE user_id=(SELECT id FROM users WHERE email=?)", (address,))
    page.locator('#process-case').click()
    expect(page.locator('#account-global-status')).to_contain_text('نشست شما پایان یافته')
    assert_cleared(page)
    expect(page.locator('#view-home')).to_be_visible()


def test_refresh_requires_identity_then_owned_case(page):
    address = signed_in(page)
    cid = create(page)
    requests = []
    page.on('request', lambda r: requests.append(r.url))
    page.reload()
    expect(page.locator('#account-identity')).to_have_text(address)
    page.locator('#resume-case').click()
    expect(page.locator('#question')).to_have_value('Synthetic Gate 3 tooth 46 question')
    assert page.evaluate('state.caseId') == cid
    assert next(i for i,u in enumerate(requests) if u.endswith('/auth/me')) < next(i for i,u in enumerate(requests) if u.endswith('/api/cases/'+cid))


@pytest.mark.parametrize('record', ['unbound','other-account'])
def test_resume_rejects_unbound_or_foreign_identity(page, record):
    signed_in(page)
    cid = create(page)
    page.evaluate("""kind => {
        const value = JSON.parse(sessionStorage.getItem('dandoonjan_active_case'));
        sessionStorage.setItem('dandoonjan_active_case', JSON.stringify(kind === 'unbound' ? {id:value.id,sample:false} : {...value, accountId:'USR-other'}));
    }""", record)
    requests = []
    page.on('request', lambda r: requests.append(r.url))
    page.reload()
    page.wait_for_function("Account.status === 'authenticated'")
    expect(page.locator('#resume-case')).not_to_be_visible()
    assert not any('/api/cases/'+cid in u for u in requests)


def test_restore_network_failure_is_not_logout(page):
    signed_in(page)
    create(page)
    saved = page.evaluate("sessionStorage.getItem('dandoonjan_active_case')")
    page.route('**/api/auth/me', lambda r: r.fulfill(status=503,json={'detail':'temporary'}))
    page.reload()
    expect(page.locator('#account-global-status')).to_contain_text('وضعیت نشست مشخص نیست')
    assert page.evaluate("sessionStorage.getItem('dandoonjan_active_case')") == saved
    assert page.evaluate('state.caseId') is None
    page.locator('#start-case').click()
    expect(page.locator('#account-dialog')).to_be_visible()


@pytest.mark.parametrize('code,status', [('AUTH_NOT_ENABLED',404),('AUTH_CONFIGURATION_INVALID',503)])
def test_auth_unavailable_fails_closed_demo_available(page, code, status):
    page.route('**/api/auth/me', lambda r: r.fulfill(status=status,json={'detail':{'code':code}}))
    page.reload()
    page.wait_for_function("Account.status === 'unavailable'")
    expect(page.locator('#account-global-status')).to_have_text('')
    expect(page.locator('#account-revalidate')).not_to_be_visible()
    assert page.evaluate('Account.user') is None
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)


@pytest.mark.parametrize('code,status', [('AUTH_NOT_ENABLED',404),('AUTH_CONFIGURATION_INVALID',503)])
def test_auth_unavailable_explicit_account_flow(page, code, status):
    page.route('**/api/auth/*', lambda r: r.fulfill(status=status,json={'detail':{'code':code}}))
    page.reload()
    page.wait_for_function("Account.status === 'unavailable'")
    open_auth(page)
    expect(page.locator('#account-status')).to_contain_text('ورود به حساب در دسترس نیست')
    page.locator('#account-email').fill(email())
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    page.wait_for_function("!document.getElementById('account-submit').disabled")
    expect(page.locator('#account-status')).not_to_have_text('')
    assert page.evaluate('Account.status') == 'unavailable'
    assert page.evaluate('Account.user') is None
    if status >= 500:
        expect(page.locator('#account-global-status')).to_contain_text('نتیجهٔ درخواست مشخص نیست')
        assert not page.locator('#account-revalidate').evaluate("el => el.classList.contains('hidden')")
    page.keyboard.press('Escape')
    page.unroute('**/api/auth/*')
    signed_in(page)
    expect(page.locator('#account-global-status')).to_contain_text('با موفقیت وارد حساب شدید')


@pytest.mark.parametrize('code,status', [('AUTH_NOT_ENABLED',404),('AUTH_CONFIGURATION_INVALID',503)])
@pytest.mark.parametrize('continuity', [False, True])
def test_known_account_unavailable_retry_and_recovery(page, code, status, continuity):
    address = signed_in(page)
    if continuity:
        create(page)
    page.route('**/api/auth/me', lambda r: r.fulfill(status=status,json={'detail':{'code':code}}))
    if continuity:
        saved = page.evaluate("sessionStorage.getItem('dandoonjan_active_case')")
        page.reload()
    else:
        page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
    expect(page.locator('#account-global-status')).to_contain_text('ورود به حساب در دسترس نیست')
    expect(page.locator('#account-revalidate')).to_be_visible()
    assert page.evaluate('Account.status') == 'unavailable'
    if continuity:
        assert page.evaluate("sessionStorage.getItem('dandoonjan_active_case')") == saved
    page.locator('#account-revalidate').click()
    page.wait_for_function("Account.status === 'unavailable'")
    expect(page.locator('#account-global-status')).to_contain_text('ورود به حساب در دسترس نیست')
    page.unroute('**/api/auth/me')
    page.locator('#account-revalidate').click()
    page.wait_for_function("Account.status === 'authenticated'")
    expect(page.locator('#account-identity')).to_have_text(address)
    expect(page.locator('#account-global-status')).to_have_text('')
    expect(page.locator('#account-revalidate')).not_to_be_visible()


def test_fresh_auth_required_is_anonymous(page):
    page.wait_for_function("Account.status === 'anonymous'")
    assert page.evaluate('Account.user') is None
    expect(page.locator('#account-global-status')).to_have_text('')
    expect(page.locator('#account-revalidate')).not_to_be_visible()


def test_fresh_network_failure_remains_visible_and_recovers(page):
    page.route('**/api/auth/me', lambda r: r.abort(), times=1)
    page.reload()
    expect(page.locator('#account-global-status')).to_contain_text('وضعیت نشست مشخص نیست')
    expect(page.locator('#account-revalidate')).to_be_visible()
    assert page.evaluate('Account.status') == 'unavailable'
    page.locator('#account-revalidate').click()
    page.wait_for_function("Account.status === 'anonymous'")
    expect(page.locator('#account-global-status')).to_have_text('')
    expect(page.locator('#account-revalidate')).not_to_be_visible()


def test_csrf_failure_refresh_requires_explicit_resubmit(page):
    signed_in(page)
    page.locator('#start-case').click()
    page.locator('#question').fill('synthetic')
    posts = []
    page.on('request', lambda r: posts.append(r) if r.method=='POST' and r.url.endswith('/api/cases') else None)
    page.route('**/api/cases', lambda r: r.fulfill(status=403,json={'detail':{'code':'CSRF_FAILED','message_fa':'درخواست معتبر نیست؛ دوباره تلاش کنید.'}}), times=1)
    page.locator('#submit-case').click()
    expect(page.locator('#workspace-error')).to_contain_text('دوباره')
    page.wait_for_function('!state.busy')
    assert len(posts)==1 and page.evaluate('state.caseId') is None
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    assert len(posts)==2


def test_logout_uncertain_keeps_material_locked_then_explicit_retry(page):
    signed_in(page)
    create(page)
    page.route('**/api/auth/logout', lambda r:r.fulfill(status=503,json={'detail':'temporary'}), times=1)
    page.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('خروج تأیید نشد')
    assert_cleared(page)
    page.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('از حساب خارج شدید')


@pytest.mark.parametrize('operation', ['create','process','report','export','upload'])
def test_stale_completion_after_logout(page, operation):
    signed_in(page)
    # Deliberately ignore AbortSignal: generation rejection must work even when
    # the server/browser cannot cancel an already-admitted request.
    page.evaluate("""() => {
        const original = fetch.bind(window);
        window.fetch = (path, options = {}) => { const {signal, ...rest} = options; return original(path, rest); };
    }""")
    held = []
    if operation == 'create':
        page.locator('#start-case').click()
        page.locator('#question').fill('synthetic')
        path, control = '**/api/cases', '#submit-case'
    elif operation in ('report','export'):
        report(page)
        path, control = '**/api/cases/*/report', '#print-report'
        if operation == 'report':
            page.reload()
            page.wait_for_function("Account.status === 'authenticated'")
            control = '#resume-case'
    else:
        create(page)
        page.locator('#files').set_input_files(PLAN)
        path, control = ('**/api/cases/*/artifacts' if operation=='upload' else '**/api/cases/*/process'), '#process-case'
    page.route(path, lambda r:held.append(r), times=1)
    page.locator(control).click()
    page.wait_for_function('state.busy')
    expect(page.locator('#account-logout')).to_be_enabled()
    # Drain browser events until the deliberately held operation has arrived.
    page.wait_for_timeout(300)
    assert len(held)==1
    page.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('از حساب خارج شدید')
    try:
        held[0].fulfill(status=200,json={'case_id':'CASE-stale','report':True,'artifact_id':'ART-stale'})
    except Exception as exc:
        assert 'Invalid' in str(exc) or 'closed' in str(exc) or 'handled' in str(exc)
    assert_cleared(page)
    expect(page.locator('#view-home')).to_be_visible()


def test_workspace_transition_clears_hidden_old_presentation(page):
    signed_in(page)
    report(page)
    assert page.locator('#completeness').inner_text()
    page.evaluate("document.getElementById('outcome-text').textContent = 'old-boundary-material'")
    page.locator('.brand').click()
    page.locator('#start-case').click()
    assert_cleared(page)
    assert page.locator('#completeness').inner_text() == ''
    assert page.locator('#outcome-text').inner_text() == ''
    assert page.locator('#report-badge').inner_text() == ''


def test_login_csrf_refresh_no_automatic_replay(page):
    address = register(page)
    calls=[]
    page.on('request',lambda r:calls.append(r.url) if '/api/auth/' in r.url else None)
    page.route('**/api/auth/login',lambda r:r.fulfill(status=403,json={'detail':{'code':'CSRF_FAILED','message_fa':'درخواست معتبر نیست؛ دوباره تلاش کنید.'}}),times=1)
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    expect(page.locator('#account-status')).to_contain_text('درخواست را دوباره ارسال کنید')
    assert sum(u.endswith('/login') for u in calls)==1
    assert sum(u.endswith('/csrf') for u in calls)==1
    login(page,address)


def test_refresh_owned_lookup_denial_does_not_offer_resume(page):
    signed_in(page)
    create(page)
    page.evaluate("""() => {
        const record=JSON.parse(sessionStorage.getItem('dandoonjan_active_case'));
        record.id='CASE-foreign'; sessionStorage.setItem('dandoonjan_active_case',JSON.stringify(record));
    }""")
    page.reload()
    page.wait_for_function("Account.status === 'authenticated'")
    expect(page.locator('#resume-case')).not_to_be_visible()
    assert page.evaluate("sessionStorage.getItem('dandoonjan_active_case')") is None


def test_refresh_expired_known_continuity(page,server):
    address=signed_in(page)
    create(page)
    with sqlite3.connect(server['database']) as db:
        db.execute("UPDATE auth_sessions SET revoked_at='2000-01-01' WHERE user_id=(SELECT id FROM users WHERE email=?)",(address,))
    page.reload()
    expect(page.locator('#account-global-status')).to_contain_text('نشست شما پایان یافته')
    assert_cleared(page)


def test_back_forward_and_bfcache_after_logout(page,server):
    signed_in(page)
    report(page)
    page.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('از حساب خارج شدید')
    page.go_back()
    page.go_forward()
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
    page.wait_for_function("Account.status === 'anonymous'")
    assert_cleared(page)
    expect(page.locator('#view-home')).to_be_visible()
    page.goto(server['url']+'/health')
    page.go_back()
    page.wait_for_function("Account.status === 'anonymous'")
    assert_cleared(page)


def test_explicit_workspace_discard_warning(page):
    signed_in(page)
    create(page)
    page.locator('#files').set_input_files(PLAN)
    page.locator('.brand').click()
    warnings=[]
    page.once('dialog', lambda d:(warnings.append(d.message),d.dismiss()))
    page.locator('#start-sample').click()
    assert warnings and 'ذخیره' in warnings[0]
    assert page.evaluate('state.sample') is False
    assert page.evaluate('state.files.length') == 1
    page.once('dialog',lambda d:d.accept())
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)


@pytest.mark.parametrize('width',[390,768,1440])
def test_responsive_keyboard_labels_escape_focus_password_secrecy(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':844})
    page.emulate_media(reduced_motion='reduce')
    logs=[]
    page.on('console',lambda m:logs.append(m.text))
    open_auth(page)
    expect(page.locator('#account-email')).to_be_focused()
    assert page.locator('#account-email').get_attribute('aria-describedby')
    assert page.locator('label[for="account-password"]').inner_text()
    assert page.locator('#account-status').get_attribute('role')=='status'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    box=page.locator('#account-dialog').bounding_box()
    assert box['x']>=0 and box['x']+box['width']<=width
    page.screenshot(path=str(tmp_path/f'account-{width}.png'))
    for key in ('Tab','Shift+Tab'):
        for _ in range(12):
            page.keyboard.press(key)
            assert page.evaluate("document.getElementById('account-dialog').contains(document.activeElement)")
    page.locator('#account-password').fill(PASSWORD)
    persisted=page.evaluate("JSON.stringify({session:{...sessionStorage},local:{...localStorage},history:history.state,url:location.href})")
    assert PASSWORD not in persisted+''.join(logs)
    page.keyboard.press('Escape')
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('#landing-auth')).to_be_focused()
    expect(page.locator('#account-password')).to_have_value('')


def test_other_tab_logout_signal_clears_presentation(page,server):
    signed_in(page)
    create(page)
    other=page.context.new_page()
    other.goto(server['url'])
    expect(other.locator('#account-logout')).to_be_visible()
    other.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('نشست')
    assert_cleared(page)
    other.close()


def test_other_tab_logout_initiation_locks_before_response(page,server):
    signed_in(page)
    create(page)
    other=page.context.new_page()
    other.goto(server['url'])
    expect(other.locator('#account-logout')).to_be_visible()
    held=[]
    other.route('**/api/auth/logout',lambda r:held.append(r))
    other.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('پنجرهٔ دیگری')
    assert_cleared(page)
    assert page.evaluate('Account.status') != 'authenticated'
    assert held
    held[0].fulfill(response=held[0].fetch())
    expect(page.locator('#account-global-status')).to_contain_text('نشست شما پایان یافته')
    other.close()


def test_authenticated_entry_is_account_view_and_dialog_logout(page):
    address=signed_in(page)
    open_auth(page)
    expect(page.locator('#account-title')).to_have_text('حساب شما')
    expect(page.locator('#account-dialog-identity')).to_have_text(address)
    expect(page.locator('#account-form')).not_to_be_visible()
    expect(page.locator('#account-modes')).not_to_be_visible()
    page.locator('#account-dialog-logout').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('#account-global-status')).to_contain_text('از حساب خارج شدید')


def test_keyboard_only_registration_and_login(page):
    open_auth(page)
    page.locator('#account-register-mode').focus()
    page.keyboard.press('Space')
    page.keyboard.press('Tab')
    expect(page.locator('#account-email')).to_be_focused()
    page.keyboard.type(email())
    page.keyboard.press('Tab')
    expect(page.locator('#account-password')).to_be_focused()
    page.keyboard.type(PASSWORD)
    page.keyboard.press('Enter')
    expect(page.locator('#account-status')).to_contain_text('حساب شما ساخته شد')
    page.wait_for_function("!document.getElementById('account-submit').disabled")
    page.locator('#account-password').focus()
    page.keyboard.type(PASSWORD)
    page.keyboard.press('Enter')
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('#account-logout')).to_be_visible()


def test_audience_selection_cleared_on_logout(page):
    signed_in(page)
    report(page)
    page.locator('#professional-view').click()
    page.locator('#account-logout').click()
    expect(page.locator('#account-global-status')).to_contain_text('از حساب خارج شدید')
    expect(page.locator('#patient-view')).to_have_attribute('aria-pressed','true')
    expect(page.locator('#professional-view')).to_have_attribute('aria-pressed','false')


def test_closed_pending_login_cannot_replace_new_demo_workspace(page):
    address=register(page)
    held=[]
    page.route('**/api/auth/login',lambda r:held.append(r),times=1)
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    page.wait_for_timeout(200)
    assert held
    page.keyboard.press('Escape')
    expect(page.locator('#account-password')).to_have_value('')
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    cid=page.evaluate('state.caseId')
    report_text=page.locator('#report-content').inner_text()
    held[0].fulfill(response=held[0].fetch())
    expect(page.locator('#account-identity')).to_have_text(address)
    assert page.evaluate('state.caseId')==cid
    assert page.evaluate('state.sample') is True
    assert page.locator('#report-content').inner_text()==report_text


def test_account_surfaces_have_scoped_aqua_colors(page):
    open_auth(page)
    assert page.locator('#account-dialog').evaluate('el => getComputedStyle(el).backgroundColor')=='rgb(247, 250, 251)'
    assert page.locator('#account-submit').evaluate('el => getComputedStyle(el).backgroundColor')=='rgb(16, 63, 80)'
    assert page.locator('#account-submit').evaluate('el => getComputedStyle(el).color')=='rgb(247, 250, 251)'
    page.keyboard.press('Escape')
    signed_in(page)
    assert page.locator('#account-panel').evaluate('el => getComputedStyle(el).backgroundColor')=='rgb(247, 250, 251)'


@pytest.mark.parametrize('stage',['me','csrf','owned'])
def test_restoration_late_response_cannot_adopt_new_boundary(page,stage):
    signed_in(page)
    create(page)
    held=[]
    path={'me':'**/api/auth/me','csrf':'**/api/auth/csrf','owned':'**/api/cases/*'}[stage]
    page.route(path,lambda r:held.append(r),times=1)
    page.reload()
    page.wait_for_timeout(300)
    assert held
    page.locator('#start-sample').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    demo_id=page.evaluate('state.caseId')
    held[0].fulfill(response=held[0].fetch())
    page.wait_for_timeout(200)
    assert page.evaluate('state.caseId')==demo_id
    assert page.evaluate('state.sample') is True
