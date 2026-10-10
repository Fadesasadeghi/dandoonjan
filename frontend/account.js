"use strict";
// Cookies are exclusively browser/server-managed. Only independent CSRF channels
// and safe account metadata live here; no credentials enter browser persistence.
window.Account = (() => {
  const el = id => document.getElementById(id);
  class RequestError extends Error {
    constructor(message, status = 0, code = '', retryAfter = null) {
      super(message); Object.assign(this, {status, code, retryAfter});
    }
  }
  class StaleRequest extends Error { constructor() { super('STALE_REQUEST'); this.stale = true; } }
  let user = null, status = 'restoring', preauthCSRF = null, accountCSRF = null;
  let passiveAuthUnavailable = false;
  let epoch = 0, refreshPromise = null, hooks = null, uiInitialized = false, mode = 'login', pending = false;
  let opener = null, intent = null, ready = Promise.resolve(), preauthIssued = 0;
  const controllers = new Set();
  const limits = new Map();
  const dialog = el('account-dialog');
  let channel = null;
  try { channel = new BroadcastChannel('dandoonjan-account-session'); } catch (_) { /* Revalidate on page return. */ }

  function announce(message = '') {
    if (message) passiveAuthUnavailable = false;
    el('account-global-status').textContent = message;
  }
  function render() {
    el('account-panel').classList.toggle('hidden', !user && status !== 'logout-uncertain');
    el('account-identity').textContent = user?.email || 'خروج در انتظار تأیید';
    el('landing-auth').textContent = user ? 'حساب شما' : 'ورود / ثبت‌نام';
    el('account-logout').disabled = status === 'logging-out';
    el('account-revalidate').classList.toggle('hidden', !['unavailable','logout-uncertain'].includes(status) ||
      (status === 'unavailable' && passiveAuthUnavailable));
    const authenticated = !!user && status === 'authenticated';
    el('account-signed-in').classList.toggle('hidden', !authenticated);
    el('account-dialog-identity').textContent = authenticated ? user.email : '';
    el('account-form').classList.toggle('hidden', authenticated);
    el('account-modes').classList.toggle('hidden', authenticated);
    if (authenticated) el('account-title').textContent = 'حساب شما';
  }
  function invalidate() {
    epoch++;
    controllers.forEach(c => c.abort()); controllers.clear();
    refreshPromise = null; preauthCSRF = null; accountCSRF = null;
  }
  async function request(path, options = {}) {
    const generation = epoch, controller = new AbortController();
    controllers.add(controller);
    try {
      let response;
      try { response = await fetch(path, {...options, credentials:'same-origin', cache:'no-store', signal:controller.signal}); }
      catch (_) {
        if (generation !== epoch) throw new StaleRequest();
        throw new RequestError('ارتباط قطع شد؛ نتیجهٔ درخواست مشخص نیست. دوباره وضعیت را بررسی کنید.');
      }
      if (generation !== epoch) throw new StaleRequest();
      if (response.status === 204) return null;
      let payload;
      try { payload = await response.json(); }
      catch (_) { throw new RequestError('پاسخ سرویس قابل خواندن نیست؛ دوباره وضعیت را بررسی کنید.', response.status); }
      if (generation !== epoch) throw new StaleRequest();
      if (!response.ok) {
        const detail = payload.detail;
        const seconds = Number(response.headers.get('Retry-After'));
        throw new RequestError(detail?.message_fa || payload.message_fa || 'درخواست کامل نشد. لطفاً دوباره تلاش کنید.', response.status,
          typeof detail === 'string' ? detail : detail?.code || '',
          response.headers.has('Retry-After') && Number.isFinite(seconds) ? Math.max(0, Math.min(seconds, 86400)) : null);
      }
      return payload;
    } finally { controllers.delete(controller); }
  }
  function refreshCSRF() {
    if (!refreshPromise) {
      const generation = epoch;
      const promise = request('/api/auth/csrf').then(data => {
        if (generation !== epoch) throw new StaleRequest();
        preauthCSRF = data.csrf_token; preauthIssued = Date.now();
        if (user) accountCSRF = data.csrf_token;
        return data.csrf_token;
      }).finally(() => { if (refreshPromise === promise) refreshPromise = null; });
      refreshPromise = promise;
    }
    return refreshPromise;
  }
  function knownContinuity() {
    try { const record = JSON.parse(sessionStorage.getItem('dandoonjan_active_case')); return record?.version === 2 && record.namespace === 'ACCOUNT'; }
    catch (_) { return false; }
  }
  function ended() {
    const known = !!user || knownContinuity();
    invalidate(); user = null; status = 'anonymous';
    hooks.clear({accountOnly:true}); render();
    if (known) announce('نشست شما پایان یافته است؛ دوباره وارد شوید.');
  }
  async function restore({external = false} = {}) {
    if (pending || status === 'logging-out' || status === 'logout-uncertain') return;
    const known = !!user || knownContinuity();
    const meaningfulFailure = known || external || (status === 'unavailable' && !passiveAuthUnavailable);
    passiveAuthUnavailable = false;
    invalidate(); const generation = epoch;
    status = 'restoring';
    hooks.clear({preserveResume:true, accountOnly:true}); render();
    try {
      const found = await request('/api/auth/me');
      if (generation !== epoch) return;
      user = found;
      await refreshCSRF();
      if (generation !== epoch) return;
      status = 'authenticated';
      await hooks.continuity();
      if (generation !== epoch) return;
      render(); announce(external ? 'وضعیت نشست دوباره بررسی شد.' : '');
    } catch (error) {
      if (generation !== epoch || error.stale) return;
      if (error.code === 'AUTH_REQUIRED') {
        user = null; accountCSRF = null; status = 'anonymous';
        hooks.clear({accountOnly:true});
        announce(known || external ? 'نشست شما پایان یافته است؛ دوباره وارد شوید.' : '');
      } else {
        status = 'unavailable'; accountCSRF = null;
        const authUnavailable = ['AUTH_NOT_ENABLED','AUTH_CONFIGURATION_INVALID'].includes(error.code);
        // Presentation only: a fresh visitor's passive capability failure is
        // still unavailable, and explicit account interaction exposes it below.
        passiveAuthUnavailable = authUnavailable && !meaningfulFailure;
        announce(passiveAuthUnavailable ? '' : authUnavailable
          ? 'ورود به حساب در دسترس نیست؛ پروندهٔ نمونه همچنان مستقل است.'
          : 'وضعیت نشست مشخص نیست؛ برای بررسی دوباره تلاش کنید.');
      }
      render();
    }
  }
  function setMode(next, message = '') {
    mode = next;
    el('account-password').value = '';
    setPasswordVisibility(false);
    el('account-password').autocomplete = mode === 'login' ? 'current-password' : 'new-password';
    el('account-title').textContent = mode === 'login' ? 'ورود به حساب' : 'ساخت حساب';
    el('account-submit').textContent = mode === 'login' ? 'ورود' : 'ثبت‌نام';
    el('account-login-mode').setAttribute('aria-pressed', String(mode === 'login'));
    el('account-register-mode').setAttribute('aria-pressed', String(mode === 'register'));
    for (const id of ['account-email','account-password']) el(id).removeAttribute('aria-invalid');
    el('account-status').textContent = message;
  }
  function formBusy(value) {
    pending = value;
    el('account-form').setAttribute('aria-busy', String(value));
    for (const id of ['account-submit','account-email','account-password','account-password-visibility','account-login-mode','account-register-mode']) el(id).disabled = value;
  }
  function setPasswordVisibility(visible) {
    el('account-password').type = visible ? 'text' : 'password';
    el('account-password-visibility').setAttribute('aria-pressed', String(visible));
    el('account-password-visibility').setAttribute('aria-label', visible ? 'پنهان کردن گذرواژه' : 'نمایش گذرواژه');
  }
  function close() {
    el('account-password').value = ''; intent = null;
    setPasswordVisibility(false);
    dialog.close();
    if (opener?.isConnected) opener.focus();
  }
  async function open(nextIntent = null) {
    intent = nextIntent; opener = document.activeElement;
    if (!pending) setMode('login');
    render();
    if (!dialog.open) dialog.showModal();
    el(user && status === 'authenticated' ? 'account-dialog-logout' : 'account-email').focus();
    await ready;
    if (!dialog.open || pending) return;
    if (user && status === 'authenticated') {
      el('account-status').textContent = 'شما وارد حساب شده‌اید؛ خروج از کنترل حساب در دسترس است.';
      return;
    }
    if (passiveAuthUnavailable) el('account-status').textContent = 'ورود به حساب در دسترس نیست؛ دوباره نشست را بررسی کنید.';
    try { await refreshCSRF(); }
    catch (error) { if (!error.stale && dialog.open) el('account-status').textContent = 'ورود به حساب در دسترس نیست؛ دوباره نشست را بررسی کنید.'; }
  }
  function signal(phase = 'confirmed') { channel?.postMessage({type:'session-changed', phase}); }
  async function submit(event) {
    event.preventDefault();
    if (pending || status === 'restoring') return;
    if (user) { el('account-status').textContent = 'برای ورود به حساب دیگر، ابتدا از حساب خارج شوید.'; return; }
    const address = el('account-email').value.trim();
    const length = [...el('account-password').value].length;
    const invalidEmail = !address || !el('account-email').validity.valid;
    const invalidPassword = length < 15 || length > 128;
    el('account-email').setAttribute('aria-invalid', String(invalidEmail));
    el('account-password').setAttribute('aria-invalid', String(invalidPassword));
    if (invalidEmail || invalidPassword) {
      el('account-status').textContent = invalidEmail ? 'ایمیل معتبر وارد کنید.' : 'گذرواژه باید ۱۵ تا ۱۲۸ نویسه باشد.';
      el(invalidEmail ? 'account-email' : 'account-password').focus(); return;
    }
    const action = mode, key = action + ':' + address.toLowerCase();
    if ((limits.get(key) || 0) > Date.now()) { el('account-status').textContent = 'کمی بعد دوباره تلاش کنید؛ زمان انتظار هنوز پایان نیافته است.'; return; }
    if (!hooks.confirmTransition()) return;
    const generation = epoch, workflow = hooks.generation(), nextIntent = intent;
    let reconcile = false;
    let body = JSON.stringify({email:address, password:el('account-password').value});
    formBusy(true); el('account-status').textContent = action === 'login' ? 'در حال ورود…' : 'در حال ساخت حساب…';
    try {
      if (!preauthCSRF || Date.now() - preauthIssued >= 9 * 60 * 1000) await refreshCSRF();
      if (generation !== epoch) throw new StaleRequest();
      const data = await request('/api/auth/' + action, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':preauthCSRF}, body});
      body = null; el('account-password').value = ''; preauthCSRF = null;
      if (workflow !== hooks.generation()) {
        // A closed dialog may have been followed by a new Demo workflow. Never
        // adopt this old completion into it. A fresh /me reconciles any cookie
        // committed by the server, without touching the Demo presentation.
        reconcile = action === 'login';
        if (reconcile) signal();
        return;
      }
      if (action === 'register') {
        if (dialog.open) setMode('login', 'حساب شما ساخته شد؛ اکنون وارد شوید.');
        await refreshCSRF();
      } else {
        hooks.clear(); user = data.user; accountCSRF = data.csrf_token; status = 'authenticated';
        render(); announce('با موفقیت وارد حساب شدید.'); signal();
        const continueIntent = dialog.open ? nextIntent : null;
        close();
        if (continueIntent) hooks.startAccount();
      }
    } catch (error) {
      if (error.stale || generation !== epoch) return;
      let message = error.message;
      if (error.code === 'AUTH_RATE_LIMITED') {
        const seconds = error.retryAfter ?? 900;
        limits.set(key, Date.now() + seconds * 1000);
        message += ` حدود ${Math.ceil(seconds / 60).toLocaleString('fa-IR')} دقیقه بعد دوباره تلاش کنید.`;
      }
      if (error.code === 'CSRF_FAILED') {
        preauthCSRF = null;
        try { await refreshCSRF(); message += ' درخواست را دوباره ارسال کنید.'; }
        catch (_) { message = 'درخواست معتبر نیست؛ ابتدا نشست را دوباره بررسی کنید.'; }
      }
      if (dialog.open) el('account-status').textContent = message;
      if (!error.status || error.status >= 500) {
        // Login might have committed despite a lost response. Never replay it.
        status = 'unavailable'; announce('نتیجهٔ درخواست مشخص نیست؛ نشست را دوباره بررسی کنید.'); render();
      }
    } finally {
      body = null;
      formBusy(false);
      if (!dialog.open) el('account-password').value = '';
      if (reconcile) ready = restore();
    }
  }
  async function logout() {
    if (pending || status === 'logging-out') return;
    const token = accountCSRF;
    if (dialog.open) close();
    invalidate(); status = 'logging-out';
    hooks.clear({accountOnly:true}); el('account-password').value = ''; render();
    signal('started'); // Other tabs lock before revocation can finish.
    try {
      const csrf = token || await refreshCSRF();
      await request('/api/auth/logout', {method:'POST', headers:{'X-CSRF-Token':csrf}});
      user = null; status = 'anonymous'; accountCSRF = null; preauthCSRF = null;
      announce('از حساب خارج شدید.'); signal();
    } catch (error) {
      if (error.stale) return;
      status = 'logout-uncertain';
      announce('خروج تأیید نشد؛ اطلاعات حساب پنهان است. دوباره خروج یا بررسی نشست را انتخاب کنید.');
      if (error.code === 'CSRF_FAILED') {
        try { await refreshCSRF(); } catch (_) { /* Explicit retry only. */ }
      }
    }
    render();
  }
  function initialize(callbacks) {
    const candidate = callbacks === undefined ? hooks : callbacks;
    const requiredHooks = ['generation','clear','confirmTransition','startAccount','continuity'];
    if (!candidate || requiredHooks.some(name => typeof candidate[name] !== 'function')) {
      throw new TypeError('Account.initialize requires application hooks');
    }
    hooks = candidate;
    if (!uiInitialized) {
      el('landing-auth').onclick = () => { void open(); };
      el('account-close').onclick = close;
      dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
      dialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const items = [...dialog.querySelectorAll('button,input')].filter(item => !item.disabled && item.getClientRects().length);
        const first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      });
      el('account-login-mode').onclick = () => setMode('login');
      el('account-register-mode').onclick = () => setMode('register');
      el('account-password-visibility').onclick = () => setPasswordVisibility(el('account-password').type === 'password');
      el('account-form').onsubmit = submit;
      el('account-logout').onclick = () => { void logout(); };
      el('account-dialog-logout').onclick = () => { void logout(); };
      el('account-revalidate').onclick = () => { status = 'unavailable'; ready = restore(); };
      if (channel) channel.onmessage = event => {
        if (event.data?.type !== 'session-changed') return;
        // No account identity/credentials/clinical data are sent through this signal.
        announce('نشست در پنجرهٔ دیگری تغییر کرده است؛ دوباره بررسی می‌شود.');
        if (event.data.phase === 'started') {
          invalidate(); status = 'unavailable';
          hooks.clear({accountOnly:true}); el('account-password').value = ''; render();
          return;
        }
        ready = restore({external:true});
      };
      window.addEventListener('pageshow', event => { if (event.persisted) ready = restore(); });
      window.addEventListener('pagehide', () => {
        el('account-password').value = '';
        hooks.clear({preserveResume:true, accountOnly:true});
      });
      uiInitialized = true;
    }
    ready = restore();
    return ready;
  }
  return {initialize, open, request, refreshCSRF, ended, RequestError, StaleRequest,
    get ready() { return ready; }, get user() { return user; }, get status() { return status; },
    get csrf() { return accountCSRF; }};
})();
