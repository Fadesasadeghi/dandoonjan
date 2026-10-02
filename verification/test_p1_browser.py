"""Real Chromium + local FastAPI/SQLite/Mock; only failure tests intercept transport.
Run explicitly: python -m pytest verification/test_p1_browser.py -q --tb=short
Optional P1_SCREENSHOTS directory writes review artifacts. No external services.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PLAN = {"name": "plan.txt", "mimeType": "text/plain", "buffer": b"Treatment Plan\nTooth 46: RCT recommended"}
BAD = {"name": "rejected.exe", "mimeType": "application/octet-stream", "buffer": b"MZ"}


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    folder = tmp_path_factory.mktemp("p1-browser")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "DJ_DATABASE_URL": f"sqlite:///{(folder / 'demo.db').as_posix()}",
        "DJ_ARTIFACT_STORAGE_DIR": str(folder / "store"), "DJ_AI_PROVIDER": "mock",
        "DJ_ENVIRONMENT": "development", "DJ_LIVE_PROVIDER_ENABLED": "false",
        "DJ_OPENROUTER_API_KEY": "", "DJ_OPENAI_API_KEY": "",
        "DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK": "false"}
    with (folder / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url + "/health", timeout=1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError((folder / "server.log").read_text())
            yield url
        finally:
            process.terminate()
            process.wait(timeout=15)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(channel="chrome", headless=True)
        yield instance
        instance.close()


@pytest.fixture()
def page(browser, server):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    page.goto(server)
    yield page
    context.close()


def start(page, files=None, question="آیا این پیشنهاد پشتیبانی دارد؟"):
    page.locator("#start-case").click()
    page.locator("#question").fill(question)
    page.locator("#dentist").fill("RCT recommended for tooth 46")
    if page.locator("#process-case").count():
        page.locator("#submit-case").click()
        expect(page.locator("#evidence-panel")).to_be_visible()
        if files:
            page.locator("#files").set_input_files(files)
        page.locator("#process-case").click()
    else:
        if files:
            page.locator("#files").set_input_files(files)
        page.locator("#submit-case").click()


def test_rejected_file_does_not_abandon_accepted_file(page):
    start(page, [BAD, PLAN])
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator('#report-files [data-upload-state="rejected"]')).to_have_count(1)
    expect(page.locator('#report-files [data-upload-state="uploaded"]')).to_have_count(1)
    expect(page.locator("#report-files")).to_contain_text("این نوع فایل پشتیبانی نمی‌شود.")


def test_file_selection_is_additive(page):
    page.locator("#start-case").click()
    page.locator("#question").fill("پرسش نمونه")
    if page.locator("#process-case").count():
        page.locator("#submit-case").click()
        expect(page.locator("#evidence-panel")).to_be_visible()
    page.locator("#files").set_input_files(PLAN)
    page.locator("#files").set_input_files(BAD)
    expect(page.locator("#file-list li")).to_have_count(2)


def capture(page, name):
    if os.environ.get("P1_SCREENSHOTS"):
        folder = Path(os.environ["P1_SCREENSHOTS"])
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / f"{name}.png"), full_page=True)


def assert_no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.body.scrollWidth <= window.innerWidth")


def case_id(page):
    return page.evaluate("JSON.parse(sessionStorage.getItem('dandoonjan_active_case')).id")


@pytest.mark.parametrize("width", [1440, 768, 390])
def test_real_sample_responsive_and_print(page, width):
    page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    expect(page.locator("#view-home h1")).to_have_text("همراه هوشمند سلامت دندان شما")
    expect(page.locator("#start-case")).to_have_text("ساخت پرونده جدید")
    expect(page.locator("#start-sample")).to_have_text("مشاهده پرونده نمونه")
    assert_no_overflow(page)
    capture(page, f"home-{width}")
    page.locator("#start-case").click()
    assert_no_overflow(page)
    capture(page, f"create-{width}")
    page.locator("#back-home").click()
    page.locator("#start-sample").click()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator("#report-content")).to_contain_text("کاملاً ساختگی")
    expect(page.locator("#report-content")).to_contain_text("پشتوانه و منبع هر ادعا")
    expect(page.locator("#report-content")).to_contain_text("اثبات ضرورت")
    text = page.locator("#report-content").inner_text()
    # New report intentionally exposes the safe run identifier for audit.
    leaked_tokens = [token for token in ("ROOT_CANAL", "TOOTH_", "CLM-", "FND-") if token in text]
    assert not leaked_tokens, leaked_tokens
    assert_no_overflow(page)
    capture(page, f"report-{width}")
    expect(page.locator("#print-report")).to_have_text("چاپ / ذخیره PDF")
    page.evaluate("() => { window.printCalled = false; window.print = () => { window.printCalled = true; }; }")
    page.locator("#print-report").click()
    page.wait_for_function("window.printCalled === true")
    page.emulate_media(media="print")
    expect(page.locator(".site-header")).not_to_be_visible()
    expect(page.locator("#print-report")).not_to_be_visible()
    expect(page.locator("#report-content")).to_be_visible()
    if width == 1440 and os.environ.get("P1_SCREENSHOTS"):
        capture(page, "print-layout")
        pdf = page.pdf(path=str(Path(os.environ["P1_SCREENSHOTS"]) / "sample-report.pdf"), prefer_css_page_size=True)
        import pymupdf
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            assert 1 <= len(doc) <= 12
            for sheet in doc:
                assert sheet.get_text().strip()
                for block in sheet.get_text("blocks"):
                    assert block[0] >= 0 and block[2] <= sheet.rect.width + 1
                    assert block[1] >= 0 and block[3] <= sheet.rect.height + 1
            doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(str(Path(os.environ["P1_SCREENSHOTS"]) / "pdf-page-1.png"))
    assert not errors


def test_existing_case_add_evidence_reprocess_edit_and_resume(page):
    start(page)
    expect(page.locator("#outcome-title")).to_have_text("شواهد بیشتری لازم است")
    original = case_id(page)
    page.locator("#files").set_input_files(PLAN)
    page.locator("#process-case").click()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    assert case_id(page) == original
    page.locator("#add-evidence").click()
    page.locator("#edit-case").click()
    page.locator("#question").fill("سؤال ویرایش‌شده دربارهٔ پیشنهاد دندان ۴۶")
    page.locator("#submit-case").click()
    expect(page.locator("#evidence-panel")).to_be_visible()
    page.locator("#process-case").click()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator("#report-content")).to_contain_text("سؤال ویرایش‌شده")
    assert case_id(page) == original
    page.reload()
    expect(page.locator("#view-home")).to_be_visible()
    page.locator("#resume-case").click()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    assert case_id(page) == original


def test_duplicate_and_image_attention(page):
    import io
    from PIL import Image
    data = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(data, format="PNG")
    image = {"name": "radiograph.png", "mimeType": "image/png", "buffer": data.getvalue()}
    start(page, [PLAN, PLAN, image])
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator('#report-files [data-upload-state="duplicate"]')).to_have_count(1)
    expect(page.locator("#report-content")).to_contain_text("تحلیل بالینی تصویر غیرفعال است")
    expect(page.locator('#report-files [data-upload-state="attention"]')).to_have_count(1)
    assert_no_overflow(page)


def test_processing_failure_retries_same_case(page):
    requests = []
    page.on("request", lambda r: requests.append((r.method, r.url)))
    page.route("**/api/cases/*/process", lambda route: route.abort(), times=1)
    start(page, [PLAN])
    expect(page.locator("#outcome-title")).to_have_text("پردازش کامل نشد")
    original = case_id(page)
    page.locator("#retry-process").click()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    assert case_id(page) == original
    assert sum(method == "POST" and url.endswith("/api/cases") for method, url in requests) == 1


def test_urgent_report_and_blocked_revision_never_show_old_report(page):
    start(page, question="facial swelling")
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator("#report-badge")).to_have_text("نیازمند ارزیابی فوری")
    expect(page.locator("#report-content .claim")).to_have_count(0)
    capture(page, "urgent-report-1440")
    original = case_id(page)
    page.locator("#add-evidence").click()
    page.locator("#edit-case").click()
    page.locator("#question").fill("prescribe me")
    page.locator("#submit-case").click()
    expect(page.locator("#evidence-panel")).to_be_visible()
    page.locator("#process-case").click()
    expect(page.locator("#outcome-title")).to_have_text("تولید گزارش به دلایل ایمنی متوقف شد")
    expect(page.locator("#view-report")).not_to_be_visible()
    expect(page.locator("#report-content")).to_be_empty()
    assert case_id(page) == original


def test_print_refuses_stale_report(page):
    start(page, [PLAN])
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    original = case_id(page)
    changed = page.request.patch(f"{page.url.rstrip('/')}/api/cases/{original}", form={"question": "changed input"})
    assert changed.status == 200 and changed.json()["changed"]
    page.evaluate("() => { window.printCalled = false; window.print = () => { window.printCalled = true; }; }")
    page.locator("#print-report").click()
    expect(page.locator("#workspace-error")).to_be_visible()
    assert page.evaluate("window.printCalled !== true")
    expect(page.locator("#view-report")).not_to_be_visible()


def test_creation_lost_response_does_not_auto_create_duplicate(page):
    creates = []
    def lose_response(route):
        response = route.fetch()
        creates.append(response.status)
        route.abort()
    page.route("**/api/cases", lose_response)
    page.locator("#start-case").click()
    page.locator("#question").fill("پرسش ساختگی")
    page.locator("#submit-case").click()
    expect(page.locator("#workspace-error")).to_contain_text("پروندهٔ تکراری")
    expect(page.locator("#submit-case")).to_be_disabled()
    assert creates == [201]


def test_keyboard_and_reduced_motion(page):
    page.emulate_media(reduced_motion="reduce")
    page.locator("#start-case").focus()
    assert page.locator("#start-case").evaluate("e => getComputedStyle(e).outlineStyle") != "none"
    page.keyboard.press("Enter")
    expect(page.locator("#question")).to_be_focused()
    assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"
    page.locator("#question").fill("پرسش نمونه")
    page.locator("#submit-case").click()
    expect(page.locator("#evidence-panel")).to_be_visible()
    page.set_viewport_size({"width":390, "height":844})
    assert_no_overflow(page)
    capture(page, "evidence-390")


def test_upload_waiting_rows_and_retry(page):
    held = []
    page.route("**/api/cases/*/artifacts", lambda route: held.append(route), times=1)
    start(page, [PLAN])
    expect(page.locator('#file-list [data-upload-state="uploading"]')).to_have_count(1)
    expect(page.locator("#activity")).to_have_text("در حال آپلود فایل‌ها…")
    expect(page.locator("#process-case")).to_be_disabled()
    held[0].abort()
    expect(page.locator("#outcome-title")).to_have_text("شواهد بیشتری لازم است")
    expect(page.locator('#file-list [data-upload-state="attention"]')).to_have_count(1)
    original = case_id(page)
    page.locator("#file-list .retry-file").click()
    page.locator("#process-case").click()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    assert case_id(page) == original


def test_long_untrusted_text_remains_text_without_overflow(page):
    page.set_viewport_size({"width":390, "height":844})
    filename = "<img src=x onerror=alert(1)>" + "x" * 180 + ".txt"
    plan = {**PLAN, "name": filename}
    start(page, [plan, PLAN], question="<script>window.untrustedExecuted=true</script>")
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    assert page.evaluate("window.untrustedExecuted !== true")
    expect(page.locator("#report-content script, #report-content img")).to_have_count(0)
    assert_no_overflow(page)


def test_review_pending_rendering_fixture_preserves_restriction(page):
    # UI fixture only: the real low-confidence backend policy is separately
    # exercised by test_report_presentation.py::test_review_pending_has_no_claims.
    page.route("**/api/cases/*/report", lambda route: route.fulfill(json={
        "report_kind": "REVIEW_PENDING", "safety_state": "MANUAL_REVIEW",
        "sections": [{"section": "review_pending", "text": "گزارش ارزیابی شواهد تا تکمیل بررسی در دسترس نیست."},
                     {"section": "evidence_status", "text": "must not render"}],
        "presentation": {"claims": [{"label": "must not render"}]}}))
    start(page, [PLAN])
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator("#report-badge")).to_have_text("گزارش ارزیابی شواهد آماده نیست")
    expect(page.locator("#report-content")).to_contain_text("این نسخه امکان ارجاع به بازبین را ندارد")
    expect(page.locator("#report-content")).not_to_contain_text("تا تکمیل بررسی در دسترس نیست")
    expect(page.locator("#report-content")).not_to_contain_text("must not render")
    expect(page.locator("#report-content .claim")).to_have_count(0)


def test_structured_report_source_hierarchy_and_print_audience(page):
    """The structured report must foreground gaps and readable sources."""
    source_ref = "ART-SYNTHETIC:page:1"
    intake_ref = "CASE-SYNTHETIC:v2:main_question"
    report = {
        "report_kind": "STANDARD", "safety_state": "CAUTION",
        "snapshot_id": "SNP-SYNTHETIC", "sections": [
            {"section": "your_question", "text": "Synthetic question context"},
            {"section": "missing_evidence", "text": "Synthetic missing examination"},
            {"section": "questions_to_ask", "text": "Ask about examination findings"}],
        "presentation": {"claims": [{"label": "Synthetic distinct claim"}], "materials": [
            {"filename": "long synthetic plan <notes>.pdf", "image_analysis_disabled": False}]},
        "review": {
            "patient_summary": [{"text": "Synthetic patient summary", "source_refs": [source_ref], "insufficient_support": False}],
            "professional_report": [{"text": "Synthetic professional detail", "source_refs": [source_ref], "insufficient_support": False}],
            "diagnostic_hypotheses": [{"label": "Synthetic hypothesis", "confidence_label": "LOW",
                "supporting_evidence_refs": [], "contradicting_evidence_refs": [], "insufficient_support": True,
                "missing_information": [{"text": "Synthetic missing examination", "source_refs": [], "insufficient_support": True}],
                "recommended_checks": [{"text": "Ask about examination findings", "source_refs": [], "insufficient_support": True}]}],
            "safety_red_flags": [],
            "limitations": [{"text": "Synthetic limitation", "source_refs": [], "insufficient_support": True}],
            "source_index": [
                {"source_ref": intake_ref, "kind": "PATIENT_REPORTED", "label": "سؤال اصلی",
                    "artifact_id": None, "page": None, "sha256": "a" * 64},
                {"source_ref": source_ref, "kind": "DOCUMENT_EXTRACTED", "label": "document-1",
                    "artifact_id": "ART-SYNTHETIC", "document_role": "treatment_plan", "page": 1, "sha256": "b" * 64}],
            "run": {"mode": "MOCK", "provider": "mock", "model": "mock-review-v1", "runtime_ms": 1,
                "created_at": "2026-01-01T00:00:00", "run_id": "MRUN-SYNTHETIC"}},
    }
    page.route("**/api/cases/*/report", lambda route: route.fulfill(json=report))
    start(page, [PLAN])
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
    expect(page.locator("#report-content")).to_contain_text("سؤال اصلی")
    expect(page.locator(".report-gaps")).to_be_visible()
    expect(page.locator(".report-gaps")).to_contain_text("Synthetic missing examination")
    expect(page.locator(".report-gaps")).to_contain_text("پشتوانهٔ کافی")
    expect(page.locator("#report-content")).to_contain_text("long synthetic plan <notes>.pdf")
    expect(page.locator("#report-content")).to_contain_text("طرح درمان")
    expect(page.locator("#report-content")).to_contain_text("صفحهٔ 1")
    expect(page.locator('[data-technical="true"]')).not_to_have_attribute("open", "")
    expect(page.locator('[data-technical="true"]')).to_contain_text("ART-SYNTHETIC:page:1")
    expect(page.locator("#report-content")).to_contain_text("تفسیر بالینی تصویر انجام نشده")
    page.locator("#professional-view").click()
    expect(page.locator("[data-audience=professional]")).to_be_visible()
    page.evaluate("() => { window.printCalled = false; window.print = () => { window.printCalled = true; }; }")
    page.locator("#print-report").click()
    page.wait_for_function("window.printCalled === true")
    expect(page.locator("#professional-view")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("[data-audience=professional]")).to_be_visible()


def test_real_coarse_processing_and_result_stages(page):
    processing, reports = [], []
    page.route("**/api/cases/*/process", lambda route: processing.append(route), times=1)
    page.route("**/api/cases/*/report", lambda route: reports.append(route), times=1)
    start(page, [PLAN])
    expect(page.locator("#activity")).to_have_text("در حال پردازش در سرور؛ لطفاً منتظر بمانید…")
    assert processing
    processing[0].continue_()
    expect(page.locator("#activity")).to_have_text("در حال آماده‌سازی نتیجه…")
    assert reports
    reports[0].continue_()
    expect(page.locator("#view-report")).to_be_visible(timeout=20000)
