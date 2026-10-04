"""Disposable SQLite/Mock browser verification with no injected auth transport."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

import pytest
from playwright.sync_api import expect
from verification.test_p1_browser import browser, PLAN

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'Synthetic Gate 3 passphrase 12345'


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    folder = tmp_path_factory.mktemp('auth-gate3-browser')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    database = folder / 'synthetic.db'
    env = {**os.environ, 'DJ_DATABASE_URL': f'sqlite:///{database.as_posix()}',
           'DJ_ARTIFACT_STORAGE_DIR': str(folder / 'storage'), 'DJ_AI_PROVIDER': 'mock',
           'DJ_AI_MODEL_NAME': 'mock-evidence-v1', 'DJ_ENVIRONMENT': 'test',
           'DJ_LIVE_PROVIDER_ENABLED': 'false', 'DJ_OPENAI_API_KEY': '', 'DJ_OPENROUTER_API_KEY': '',
           'DJ_LOCAL_SYNTHETIC_ACCEPTANCE_ENABLED': 'false', 'DJ_AUTH_FOUNDATION_ENABLED': 'true',
           'DJ_AUTH_ALLOWED_ORIGINS': f'["{url}"]',
           'DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK': 'false'}
    # Install construction AND dispatch tripwires in the server process itself.
    script = '''
import app.ai.gateway as gateway
import app.ai.providers as providers
def forbidden(*args, **kwargs):
    raise AssertionError('GATE3_LIVE_PROVIDER_TRIPWIRE')
for name in ('OpenRouterProvider', 'OpenAIProvider'):
    provider = getattr(providers, name, None)
    if provider:
        for method in ('__init__', 'run', '_request', 'generate', 'extract', 'review'):
            if hasattr(provider, method): setattr(provider, method, forbidden)
    if hasattr(gateway, name): setattr(gateway, name, forbidden)
import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=PORT)
'''.replace('PORT', str(port))
    with (folder / 'server.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-c', script], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url + '/health', timeout=1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError((folder / 'server.log').read_text(encoding='utf-8'))
            yield {'url': url, 'database': database, 'log': folder / 'server.log'}
        finally:
            process.terminate()
            process.wait(timeout=15)
    recorded = (folder / 'server.log').read_text(encoding='utf-8')
    assert 'GATE3_LIVE_PROVIDER_TRIPWIRE' not in recorded
    assert PASSWORD not in recorded


@pytest.fixture()
def page(browser, server):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    tab = context.new_page()
    tab.set_default_timeout(3000)
    tab.goto(server['url'])
    yield tab
    context.close()


def email():
    return f'gate3-{uuid.uuid4().hex}@example.com'


def open_auth(page):
    page.locator('#landing-auth').click()
    expect(page.locator('#account-dialog')).to_be_visible()


def register(page, address=None):
    address = address or email()
    open_auth(page)
    page.locator('#account-register-mode').click()
    page.locator('#account-email').fill(address)
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    expect(page.locator('#account-status')).to_contain_text('حساب شما ساخته شد')
    expect(page.locator('#account-password')).to_have_value('')
    return address


def login(page, address):
    if not page.locator('#account-dialog').is_visible():
        open_auth(page)
    page.locator('#account-login-mode').click()
    page.locator('#account-email').fill(address)
    page.locator('#account-password').fill(PASSWORD)
    page.locator('#account-submit').click()
    expect(page.locator('#account-dialog')).not_to_be_visible()
    expect(page.locator('#account-identity')).to_have_text(address)


def signed_in(page):
    address = register(page)
    login(page, address)
    return address


def create(page):
    page.locator('#start-case').click()
    page.locator('#question').fill('Synthetic Gate 3 tooth 46 question')
    page.locator('#dentist').fill('RCT recommended for tooth 46')
    page.locator('#submit-case').click()
    expect(page.locator('#evidence-panel')).to_be_visible()
    page.wait_for_function('!state.busy')
    return page.evaluate('state.caseId')


def report(page):
    create(page)
    page.locator('#files').set_input_files(PLAN)
    page.locator('#process-case').click()
    expect(page.locator('#view-report')).to_be_visible(timeout=30000)
    page.wait_for_function('!state.busy')


def assert_cleared(page):
    assert page.evaluate('state.caseId === null && state.report === null && state.files.length === 0')
    assert page.evaluate('navigation.operations.size') == 0
    assert page.locator('#question').input_value() == ''
    assert page.locator('#dentist').input_value() == ''
    assert page.locator('#symptoms').input_value() == ''
    assert page.locator('#report-content').inner_text() == ''
    assert page.locator('#report-export').inner_text() == ''
    assert page.locator('#file-list li').count() == 0
    assert page.locator('#report-files li').count() == 0
    assert page.evaluate("sessionStorage.getItem('dandoonjan_active_case')") is None
    assert not page.evaluate("document.body.classList.contains('print-ready') || document.body.classList.contains('export-prepared')")
