"use strict";
const $ = id => document.getElementById(id);
const state = {caseId: null, files: [], busy: false, sample: false, report: null, createUncertain: false};
let demoCSRF = null;
const SAMPLE_FILES = ['طرح-درمان-نمونه.txt', 'synthetic-pattern-not-radiograph.png', 'synthetic-plan.pdf', 'synthetic-prior-report.txt'];
const DOSSIER = {symptoms:"علائم", duration:"مدت علائم", medical_history:"سابقه پزشکی", medications:"داروها", allergies:"حساسیت‌ها", treatment_plan:"طرح درمان", previous_reports:"گزارش قبلی", previous_treatments:"درمان‌های قبلی", dental_images:"تصویر دندان", main_question:"سؤال اصلی"};
const dossierFields = Object.keys(DOSSIER).filter(id => $(id));
function showCompleteness(data) { $("completeness").textContent = data.missing_information.length ? "برای پروندهٔ کامل‌تر: " + data.missing_information.map(k => DOSSIER[k] || k).join("، ") : "بخش‌های اطلاعاتی ثبت شده‌اند؛ این به معنی کافی بودن شواهد بالینی نیست."; }
const STATUS = {pending: "در انتظار ارسال", uploading: "در حال آپلود", uploaded: "آپلود شد", rejected: "رد شد", duplicate: "تکراری", retryable: "خطای ارسال؛ قابل تلاش دوباره"};
const TREATMENTS = {ROOT_CANAL: "عصب‌کشی", EXTRACTION: "کشیدن دندان", CROWN: "روکش", FILLING: "ترمیم", SCALING: "جرم‌گیری", IMPLANT: "ایمپلنت", BRIDGE: "بریج", DENTURE: "دندان مصنوعی", ORTHODONTICS: "ارتودنسی", UNKNOWN: "نامشخص"};
const SECTIONS = {your_question: "سؤال شما", dentist_recommendation: "درمان پیشنهادی به روایت شما", found_in_documents: "آنچه می‌دانیم", evidence_status: "وضعیت شواهد", still_unclear: "آنچه هنوز نمی‌دانیم", missing_evidence: "شواهد تکمیلی", topics_to_discuss: "نکات نیازمند بررسی", questions_to_ask: "پیش از تصمیم بپرسید", confidence: "محدودیت اطمینان", safety_note: "محدودیت‌های ایمنی", review_pending: "نیازمند بررسی دستی"};
const SOURCE_KINDS = {PATIENT_REPORTED:"گفتهٔ شما", CLINICIAN_REPORTED:"گفتهٔ دندان‌پزشک به روایت شما", DOCUMENT_EXTRACTED:"محتوای سند", MODEL_INFERRED:"برداشت مدل؛ نیازمند تأیید"};
const DOCUMENT_ROLES = {unspecified:"سایر مدارک", treatment_plan:"طرح درمان", prescription:"نسخه", dental_image:"تصویر دندان", previous_report:"گزارش قبلی"};
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function humanText(text) {
  if (["موردی باقی نمانده است.", "شواهد کاملی ثبت شده است."].includes(text)) return "در محدودهٔ این بررسی، مورد تکمیلی ثبت نشده است؛ این به معنی کامل بودن ارزیابی بالینی نیست.";
  return String(text).replace(/\b(ROOT_CANAL|EXTRACTION|CROWN|FILLING|SCALING|IMPLANT|BRIDGE|DENTURE|ORTHODONTICS|UNKNOWN)\b/g, key => TREATMENTS[key]);
}
class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; }
}
async function api(path, options = {}) {
  // Browser sample state selects transport only; the server authorizes its cookie.
  if (state.sample && /^\/api\/cases(?:\/|$)/.test(path)) {
    path = path.replace('/api/cases', '/api/demo/cases');
    if (!demoCSRF) {
      const session = await api('/api/demo/session');
      demoCSRF = session.csrf_token;
    }
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method)) {
      options = {...options, headers: {...options.headers, 'X-CSRF-Token': demoCSRF}};
    }
  }
  let response;
  try { response = await fetch(path, options); }
  catch (_) { throw new ApiError("ارتباط قطع شد؛ نتیجهٔ این درخواست مشخص نیست. پروندهٔ موجود را نگه داشته‌ایم."); }
  let payload;
  try { payload = await response.json(); }
  catch (_) { throw new ApiError("پاسخ سرویس قابل خواندن نیست؛ دوباره وضعیت همین پرونده را بررسی کنید.", response.status); }
  if (!response.ok) {
    if (state.sample && response.status === 401) {
      demoCSRF = null;
      clearReport();
    }
    throw new ApiError(payload.detail?.message_fa || payload.message_fa || (response.status === 404 ? "گزارش فعلی در دسترس نیست؛ همین پرونده را دوباره بررسی کنید." : "درخواست کامل نشد. لطفاً دوباره تلاش کنید."), response.status);
  }
  return payload;
}
function saveCase() {
  try { sessionStorage.setItem("dandoonjan_active_case", JSON.stringify({id: state.caseId, sample: state.sample})); } catch (_) { /* Storage is optional; in-page retry still works. */ }
  $("resume-case").classList.toggle("hidden", navigation.draft || !state.caseId);
}
function showView(name) {
  ReportExport.discard();
  ["home", "workspace", "report"].forEach(v => $("view-" + v).classList.toggle("active", v === name));
  document.body.classList.toggle("print-ready", name === "report" && !!state.report);
  window.scrollTo({top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
}
// History contains presentation identity only; drafts and File objects stay in memory.
function navigationId() { return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`; }
const navigation = {session: navigationId(), current: null, revision: 0, draft: false, lastWork: 'intake', operations: new Map()};
// Install this optional enhancement only when there is work to return to.
const draftReturnControl = $('return-draft');
const draftReturnParent = draftReturnControl?.parentElement;
draftReturnControl?.remove();
function route(view, extra = {}) {
  return {app: 'dandoonjan', session: navigation.session, view, caseId: state.caseId, ...extra};
}
function reportIdentity(report) {
  return {caseId: report.case_id, reportId: report.report_id, snapshotId: report.snapshot_id, runId: report.review?.run?.run_id || null};
}
function sameReport(entry, report) {
  const identity = reportIdentity(report);
  return !!entry.reportId && !!entry.snapshotId && Object.keys(identity).every(key => entry[key] === identity[key]);
}
function present(entry) {
  navigation.current = entry;
  navigation.revision++;
  if (['intake', 'evidence'].includes(entry.view)) navigation.lastWork = entry.view;
  if (navigation.draft && draftReturnControl && !draftReturnControl.isConnected) draftReturnParent.append(draftReturnControl);
  draftReturnControl?.classList.toggle('hidden', !navigation.draft);
  $('resume-case').classList.toggle('hidden', navigation.draft || !sessionCaseAvailable());
  $('view-workspace').classList.toggle('analyzing', entry.view === 'processing');
  $('analysis-scene').classList.toggle('hidden', entry.view !== 'processing');
  $('report-unavailable')?.classList.add('hidden');
  if (entry.view === 'home') showView('home');
  else if (entry.view === 'report') showView('report');
  else {
    showView('workspace');
    $('intake-panel').classList.remove('hidden');
    $('evidence-panel').classList.toggle('hidden', entry.view === 'intake');
    $('case-question').textContent = $('question').value;
    $('sample-notice').classList.toggle('hidden', !state.sample);
  }
}
function sessionCaseAvailable() {
  try { return !!JSON.parse(sessionStorage.getItem('dandoonjan_active_case') || 'null')?.id; }
  catch (_) { return false; }
}
function navigate(view, extra = {}, replace = false) {
  const entry = route(view, extra);
  const same = JSON.stringify(entry) === JSON.stringify(navigation.current);
  if (!same || replace) history[replace ? 'replaceState' : 'pushState'](entry, '');
  present(entry);
}
function unavailableReport() {
  clearReport();
  $('report-badge').textContent = 'نتیجهٔ قبلی در دسترس نیست';
  $('audience-controls').classList.add('hidden');
  $('print-report').disabled = true;
  $('report-unavailable')?.classList.remove('hidden');
}
async function restoreNavigation(entry) {
  if (!entry || entry.app !== 'dandoonjan' || entry.session !== navigation.session ||
      !['home', 'intake', 'evidence', 'processing', 'report'].includes(entry.view) ||
      (entry.caseId && entry.caseId !== state.caseId)) {
    navigate('home', {}, true); return;
  }
  if (entry.view === 'processing') {
    const operation = navigation.operations.get(entry.operationId);
    if (!operation) { navigate(state.caseId ? 'evidence' : 'intake', {}, true); return; }
    if (operation.done) {
      if (operation.report) {
        entry = route('report', reportIdentity(operation.report));
        history.replaceState(entry, '');
      } else { navigate('evidence', {}, true); return; }
    }
  }
  present(entry);
  if (entry.view !== 'report') return;
  // Never expose cached content while the authoritative GET is pending.
  clearReport(); $('print-report').disabled = true;
  const revision = navigation.revision;
  try {
    const report = await api(`/api/cases/${entry.caseId}/report`);
    if (revision !== navigation.revision) return;
    if (!sameReport(entry, report)) { unavailableReport(); return; }
    renderReport(report, false);
    setBusy(state.busy, $('activity').textContent);
  } catch (_) { if (revision === navigation.revision) unavailableReport(); }
}
window.addEventListener('popstate', event => {
  // Native fragment entries do not represent a workflow transition.
  const entry = event.state || navigation.current;
  if (!event.state) history.replaceState(entry, '');
  void restoreNavigation(entry);
});
function homeNavigation() { navigate('home'); }
document.querySelector('.brand').addEventListener('click', event => {
  event.preventDefault(); homeNavigation();
});
if (draftReturnControl) draftReturnControl.onclick = () => {
  const operation = [...navigation.operations.values()].find(op => !op.done);
  if (operation) navigate('processing', {operationId: operation.id});
  else navigate(navigation.lastWork);
};
if ($('return-evidence')) $('return-evidence').onclick = () => navigate(state.caseId ? 'evidence' : 'intake');
function setBusy(busy, message = "") {
  state.busy = busy;
  document.querySelectorAll("button, textarea, input").forEach(el => { el.disabled = busy; });
  document.querySelectorAll('select').forEach(el => { el.disabled = busy; });
  ['back-home', 'home-from-report'].forEach(id => $(id).disabled = false);
  ['return-draft', 'return-evidence'].forEach(id => { if ($(id)) $(id).disabled = false; });
  if (navigation.current?.view === 'report' && !state.report) $('print-report').disabled = true;
  if (state.createUncertain) $("submit-case").disabled = true;
  $("activity").textContent = message;
  $("view-workspace").setAttribute("aria-busy", String(busy));
}
function error(message) {
  $("workspace-error").textContent = message;
  $("workspace-error").classList.remove("hidden");
}
function clearError() { $("workspace-error").classList.add("hidden"); }
function clearReport() { ReportExport.discard(); state.report = null; $("report-content").replaceChildren(); document.body.classList.remove("print-ready"); }
let nextLocalRowId = 0;
function localRow(values) {
  return {localId: ++nextLocalRowId, uploadState: 'pending', processingState: 'unknown', message: '', ...values};
}
function renderFiles() {
  const html = state.files.map(row => {
    const editable = !!row.file && ['pending', 'rejected'].includes(row.uploadState) && !row.persistenceUncertain;
    const controls = editable ? `<select class="file-role" aria-label="نوع این مدرک" data-id="${row.localId}" ${state.busy ? 'disabled' : ''}>${Object.entries(DOCUMENT_ROLES).map(([value,label]) => `<option value="${value}" ${row.role === value ? 'selected' : ''}>${label}</option>`).join('')}</select><button type="button" class="btn text remove-file" data-id="${row.localId}" ${state.busy ? 'disabled' : ''}>حذف از صف محلی</button>` : '';
    return `<li data-upload-state="${row.uploadState}" data-processing-state="${row.processingState}"><bdi class="filename">${escapeHtml(row.name)}</bdi><span class="file-status">${STATUS[row.uploadState]}</span>${row.sampleMessage ? `<span class="file-message">${escapeHtml(row.sampleMessage)}</span>` : ''}${row.message ? `<span class="file-message">${escapeHtml(row.message)}</span>` : ''}${row.processingMessage ? `<span class="file-message">${escapeHtml(row.processingMessage)}</span>` : ''}${controls}${row.retry ? `<button type="button" class="btn text retry-file" data-id="${row.localId}" ${state.busy ? 'disabled' : ''}>تلاش دوباره برای این فایل</button>` : ''}</li>`;
  }).join('');
  $('file-list').innerHTML = html;
  $('report-files').innerHTML = html;
  $('upload-summary').classList.toggle('hidden', !state.files.length);
  document.querySelectorAll('.retry-file, .remove-file, .file-role').forEach(control => {
    const row = state.files.find(r => r.localId === Number(control.dataset.id));
    if (control.classList.contains('file-role')) control.onchange = () => { if (!state.busy) row.role = control.value; };
    else control.onclick = () => {
      if (state.busy) return;
      if (control.classList.contains('remove-file')) state.files = state.files.filter(r => r.localId !== row.localId);
      else { row.uploadState = 'pending'; row.retry = false; row.message = ''; }
      evidenceView(); renderFiles();
    };
  });
}
function addFiles(files) {
  if (state.busy) return;
  for (const file of files) {
    const row = localRow({file, name:file.name, role:$('document-role').value});
    if (!/\.(pdf|txt|png|jpe?g)$/i.test(file.name)) { row.uploadState = 'rejected'; row.message = 'این نوع فایل پشتیبانی نمی‌شود.'; }
    else if (!file.size) { row.uploadState = 'rejected'; row.message = 'فایل خالی است.'; }
    else if (file.size > 25*1024*1024) { row.uploadState = 'rejected'; row.message = 'حجم فایل بیش از حد مجاز ۲۵ مگابایت (MiB) است.'; }
    state.files.push(row);
  }
  $('files').value = '';
  renderFiles();
}
function evidenceView(replace = false) { navigate('evidence', {}, replace); }
function startNewCase() {
  if (state.busy) return;
  navigation.session = navigationId(); navigation.draft = true; navigation.operations.clear();
  Object.assign(state, {caseId: null, files: [], sample: false, report: null, createUncertain: false});
  // Keep Home in the new session; earlier work entries cannot bind to this draft.
  try { sessionStorage.removeItem('dandoonjan_active_case'); } catch (_) {}
  navigate('home', {}, true);
  clearReport(); clearError();
  $("case-form").reset(); $("evidence-panel").classList.add("hidden");
  $("intake-panel").classList.remove("hidden"); $("sample-notice").classList.add("hidden");
  $("outcome").classList.add("hidden"); $("submit-case").textContent = "ساخت پرونده و افزودن مدارک";
  renderFiles(); setBusy(false); navigate("intake"); $("question").focus();
}
async function createOrUpdate(transition = true, replace = false) {
  const revision = navigation.revision;
  const data = new FormData();
  data.append("question", $("question").value.trim());
  data.append("dentist_recommendation", $("dentist").value.trim());
  clearReport();
  setBusy(true, state.caseId ? "در حال ذخیرهٔ تغییرات همین پرونده…" : "در حال ساخت پرونده…");
  if (state.caseId) await api(`/api/cases/${state.caseId}`, {method: "PATCH", body: data});
  else {
    try {
      const created = await api("/api/cases", {method: "POST", body: data});
      state.caseId = created.case_id;
      saveCase();
    } catch (e) {
      // A lost creation response must never trigger an automatic second POST.
      if (!e.status || e.status >= 500 || e.status === 201) state.createUncertain = true;
      throw e;
    }
  }
  const dossier = Object.fromEntries(dossierFields.map(id => [id, $(id).value]));
  showCompleteness(await api(`/api/cases/${state.caseId}/dossier`, {method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(dossier)}));
  $("submit-case").textContent = "ذخیرهٔ تغییرات همین پرونده";
  if (transition && revision === navigation.revision) evidenceView(replace);
}
async function submitForm(event) {
  event.preventDefault();
  if (state.busy || state.createUncertain || !$("case-form").reportValidity()) return;
  clearError();
  try { await createOrUpdate(); }
  catch (e) { error(e.message + (state.createUncertain ? " ساخت مجدد خودکار متوقف شد تا پروندهٔ تکراری ایجاد نشود." : "")); }
  finally { setBusy(false); }
}
async function uploadPending() {
  for (const row of state.files.filter(r => r.uploadState === "pending")) {
    row.uploadState = "uploading"; renderFiles();
    setBusy(true, "در حال آپلود فایل‌ها…");
    const data = new FormData(); data.append("file", row.file);
    data.append('document_role', row.role || 'unspecified');
    try {
      const result = await api(`/api/cases/${state.caseId}/artifacts`, {method: "POST", body: data});
      row.artifactId = result.artifact_id;
      row.persistenceUncertain = false;
      row.uploadState = result.duplicate_of ? "duplicate" : "uploaded";
      row.message = result.duplicate_of ? "این مدرک قبلاً در همین پرونده ثبت شده است؛ نام فایل و نوع مدرک ثبت‌شدهٔ قبلی معتبر می‌ماند و با نام یا نوع انتخابی جدید تغییر نمی‌کند." : "";
      if (!row.sampleMessage && /\.(png|jpe?g)$/i.test(row.name)) row.message += " تصویر ذخیره شد؛ نوع بررسی آن به حالت اجرای گزارش بستگی دارد.";
    } catch (e) {
      row.uploadState = e.status === 422 ? "rejected" : "retryable";
      row.message = e.message;
      if (row.uploadState === "retryable") row.persistenceUncertain = true;
      row.retry = row.uploadState === "retryable" || (state.sample && !!row.sampleMessage && row.uploadState === 'rejected');
    }
    renderFiles();
  }
}
function applyAttention(result) {
  const needs = new Set(result.needs_more_evidence || []);
  const rejected = new Set(result.rejected_artifacts || []);
  const limited = new Set(result.limitations || []);
  for (const row of state.files) {
    row.processingState = rejected.has(row.artifactId) ? 'rejected' : needs.has(row.artifactId) ? 'needs_more_evidence' : limited.has(row.artifactId) ? 'limited' : 'unknown';
    row.processingMessage = {unknown:'', limited:'آپلود شد؛ بررسی این مدرک محدودیت دارد.', needs_more_evidence:'آپلود شد؛ برای بررسی این مدرک شواهد تکمیلی لازم است.', rejected:'آپلود شد؛ این مدرک در مرحلهٔ پردازش قابل استفاده نبود.'}[row.processingState];
  }
  renderFiles();
}
function outcome(result) {
  const blocked = result.safety_state === "BLOCKED";
  const urgent = result.safety_state === "URGENT_EVALUATION";
  const manual = result.status === "MANUAL_REVIEW_REQUIRED" || result.safety_state === "MANUAL_REVIEW";
  let title = "شواهد بیشتری لازم است", text = "به همین پرونده مدرک اضافه کنید و دوباره بررسی را بزنید. سؤال و فایل‌های قبلی حفظ شده‌اند.";
  if (blocked) { title = "تولید گزارش به دلایل ایمنی متوقف شد"; text = "این درخواست در محدودهٔ ایمن این سرویس نیست. برای تصمیم درمانی با دندان‌پزشک گفت‌وگو کنید؛ گزارش قبلی به‌عنوان نتیجهٔ فعلی نمایش داده نمی‌شود."; }
  else if (urgent) { title = "نیازمند ارزیابی فوری"; text = "برای ارزیابی فوری به دندان‌پزشک یا خدمات اورژانس مراجعه کنید. منتظر تکمیل مدارک نمانید."; }
  else if (manual) { title = "نیازمند بررسی دستی"; text = "نتیجهٔ معمول قابل ارائه نیست. این نسخه امکان ارجاع به بازبین را ندارد؛ با دندان‌پزشک گفت‌وگو کنید."; }
  else if (result.status === "FAILED") { title = "پردازش کامل نشد"; text = "پرونده و فایل‌های ثبت‌شده حفظ شده‌اند. می‌توانید پردازش همین پرونده را دوباره اجرا کنید."; }
  else if (result.status !== "NEEDS_MORE_EVIDENCE") { title = "نتیجهٔ فعلی آماده نیست"; text = "وضعیت همین پرونده را دوباره بررسی کنید."; }
  $("outcome-title").textContent = title; $("outcome-text").textContent = text;
  $("outcome").classList.remove("hidden");
  $("retry-process").classList.toggle("hidden", blocked || manual || urgent);
  if (navigation.current?.view === "evidence") $("outcome-title").focus();
}
async function processCase({replaceHistory = false} = {}) {
  if (state.busy || !state.caseId) return;
  clearError(); clearReport(); $('outcome').classList.add('hidden'); evidenceView(replaceHistory);
  const operation = {id: navigationId(), caseId: state.caseId, done: false, report: null};
  navigation.operations.set(operation.id, operation);
  navigate('processing', {operationId: operation.id}, replaceHistory);
  try {
    await createOrUpdate(false);
    setBusy(true, 'در حال آپلود فایل‌ها…');
    await uploadPending();
    if (state.sample && !SAMPLE_FILES.every(name => state.files.some(row => row.name === name && row.artifactId && ['uploaded', 'duplicate'].includes(row.uploadState)))) {
      throw new ApiError('آماده‌سازی نمونه کامل نشده است؛ چهار مدرک ساختگی باید ثبت شوند. فایل ناموفق را دوباره ارسال و همین پرونده را بررسی کنید.');
    }
    setBusy(true, 'در حال پردازش در سرور؛ لطفاً منتظر بمانید…');
    const result = await api(`/api/cases/${operation.caseId}/process`, {method: 'POST'});
    applyAttention(result);
    if (result.report) {
      setBusy(true, 'در حال آماده‌سازی نتیجه…');
      operation.report = await api(`/api/cases/${operation.caseId}/report`);
    } else outcome(result);
  } catch (e) { error(e.message); outcome({status: 'FAILED'}); }
  finally {
    operation.done = true;
    if (navigation.current?.view === 'processing' && navigation.current.operationId === operation.id) {
      if (operation.report) renderReport(operation.report, true, true);
      else navigate('evidence', {}, true);
    }
    setBusy(false); renderFiles();
  }
}
async function startSample() {
  if (state.busy) return;
  startNewCase(); state.sample = true;
  $("sample-notice").classList.remove("hidden");
  $("question").value = "آیا پیشنهاد عصب‌کشی برای دندان ۴۶ پشتیبانی کافی دارد؟";
  $("dentist").value = "دندان‌پزشک عصب‌کشی و روکش را پیشنهاد کرده است.";
  Object.entries({symptoms:"حساسیت به سرما در دندان ۴۶ — نمونهٔ ساختگی", duration:"سه روز", medical_history:"سابقهٔ مهمی گزارش نشده؛ ساختگی", medications:"ندارد", allergies:"ندارد", treatment_plan:"SYNTHETIC Treatment Plan\nTooth 46: RCT recommended\nFor software testing only; not clinical evidence.", previous_reports:"گزارش قبلی ساختگی؛ معاینه تکمیلی ثبت نشده", previous_treatments:"ندارد"}).forEach(([key,value]) => $(key).value = value);
  let prepared = false;
  try {
    setBusy(true, "در حال دریافت مدرک ساختگی نمونه…");
    const response = await fetch("/api/demo/sample");
    if (!response.ok) throw new ApiError("مدرک نمونه در دسترس نیست؛ می‌توانید مدارک ساختگی خودتان را اضافه کنید.", response.status);
    const file = new File([await response.text()], "طرح-درمان-نمونه.txt", {type: "text/plain"});
    const files = [{file, name: file.name, role:'treatment_plan', uploadState: "pending", sampleMessage: "طرح درمان کاملاً ساختگی؛ ثبت پیشنهاد، نه اثبات ضرورت درمان."}];
    for (const [path,name,type,role,sampleMessage] of [['sample-image','synthetic-pattern-not-radiograph.png','image/png','dental_image','الگوی آزمون انتقال فایل؛ رادیوگرافی نیست و تفسیر بالینی نشده است.'], ['sample-plan','synthetic-plan.pdf','application/pdf','treatment_plan','PDF طرح درمان کاملاً ساختگی؛ متن آن برای آزمون نرم‌افزار استفاده می‌شود.']]) {
      const asset = await fetch('/api/demo/' + path);
      if (!asset.ok) throw new ApiError('مدرک نمونه در دسترس نیست.');
      const extra = new File([await asset.blob()], name, {type});
      files.push({file:extra, name, role, uploadState:'pending', sampleMessage});
    }
    const previous = new File(['SYNTHETIC prior clinical note\nTooth 46: cold sensitivity for three days. No examination or pulp test recorded.\nFor software testing only; not clinical evidence.'], 'synthetic-prior-report.txt', {type:'text/plain'});
    files.push({file:previous, name:previous.name, role:'previous_report', uploadState:'pending', sampleMessage:'یادداشت قبلی کاملاً ساختگی؛ نتیجهٔ معاینه ثبت نشده است.'});
    state.files = files.map(localRow);
    // The Sample click owns one entry; automatic steps update that entry.
    renderFiles();
    const session = await api('/api/demo/session', {method: 'POST'});
    demoCSRF = session.csrf_token;
    await createOrUpdate(true, true);
    prepared = true;
  } catch (e) { error(e.message); }
  finally { setBusy(false); }
  if (prepared) await processCase({replaceHistory: true});
}
function section(title, body) { return `<section class="report-section"><h2>${escapeHtml(title)}</h2>${body}</section>`; }
function audience(name, focus = false) {
  document.querySelectorAll('[data-audience]').forEach(el => el.classList.toggle('audience-hidden', el.dataset.audience !== name));
  ['patient', 'professional'].forEach(key => { $(key + '-view').setAttribute('aria-pressed', String(key === name)); $(key + '-view').className = 'btn ' + (key === name ? 'primary' : 'quiet'); });
  if (focus) $(name + '-view').focus();
}
function renderReview(report) {
  const review = report.review;
  const sourceByRef = new Map((review.source_index || []).map(source => [source.source_ref, source]));
  const artifacts = (report.presentation?.materials || []);
  const artifactIds = [...new Set((review.source_index || []).filter(s => s.artifact_id).map(s => s.artifact_id))];
  const artifactPosition = new Map(artifactIds.map((id, index) => [id, index]));
  const readableSource = source => {
    const sourceType = SOURCE_KINDS[source.kind] || 'منبع ثبت‌شده';
    const material = source.artifact_id ? artifacts[artifactPosition.get(source.artifact_id)] : null;
    const file = material?.filename ? ` · ${escapeHtml(material.filename)}` : '';
    const role = source.document_role ? ` · ${escapeHtml(DOCUMENT_ROLES[source.document_role] || source.document_role)}` : '';
    const page = source.page ? ` · صفحهٔ ${escapeHtml(source.page)}` : '';
    return `${escapeHtml(source.label || sourceType)}${file}${role}${page}`;
  };
  const refs = values => (values || []).map(ref => {
    const source = sourceByRef.get(ref);
    return source ? `<a class="source-link" href="#source-${escapeHtml(ref)}">${readableSource(source)}</a>` : '';
  }).filter(Boolean).join('، ');
  const assertions = values => (values || []).length ? values.map(a => `<li>${escapeHtml(humanText(a.text))}${a.insufficient_support ? '<small class="support-gap"> — پشتوانهٔ کافی ثبت نشده</small>' : ''}${a.source_refs?.length ? `<div class="assertion-sources">منبع: ${refs(a.source_refs)}</div>` : ''}</li>`).join('') : '<li class="empty-state">موردی در این بخش ثبت نشده است.</li>';
  const disclosure = (title, html, attributes = '') => `<details class="result-disclosure" ${attributes}><summary>${escapeHtml(title)}</summary><div>${html}</div></details>`;
  const hypotheses = (review.diagnostic_hypotheses || []).length ? review.diagnostic_hypotheses.map((h, i) => `<article class="hypothesis"><h3>${i+1}. ${escapeHtml(h.label)}</h3><p>پشتیبانی کیفی مدل: <bdi>${escapeHtml(h.confidence_label)}</bdi> — این مورد تشخیص یا احتمال قطعی نیست.</p>${h.insufficient_support ? '<p class="support-gap">پشتوانهٔ کافی ثبت نشده است.</p>' : ''}<p>شواهد پشتیبان: ${refs(h.supporting_evidence_refs) || 'ثبت نشده'}</p><p>شواهد ناسازگار: ${refs(h.contradicting_evidence_refs) || 'ثبت نشده؛ به معنی نبود ناسازگاری نیست'}</p><h4>اطلاعات ناقص</h4><ul>${assertions(h.missing_information)}</ul><h4>بررسی‌های قابل گفت‌وگو</h4><ul>${assertions(h.recommended_checks)}</ul></article>`).join('') : '<p class="empty-state">فرضیه‌ای در این بررسی ثبت نشده است.</p>';
  const sourceRows = (review.source_index || []).map(s => `<li id="source-${escapeHtml(s.source_ref)}">${readableSource(s)} <span class="source-type">${escapeHtml(SOURCE_KINDS[s.kind] || s.kind || 'منبع ثبت‌شده')}</span></li>`).join('');
  const sourceTechnicalRows = (review.source_index || []).map(s => `<li>${escapeHtml(s.label || SOURCE_KINDS[s.kind] || 'منبع')}<p>شناسهٔ منبع: <bdi>${escapeHtml(s.source_ref)}</bdi></p>${s.sha256 ? `<p>شناسهٔ محتوا: <bdi>${escapeHtml(s.sha256)}</bdi></p>` : ''}</li>`).join('');
  const gaps = [];
  for (const item of report.sections || []) if (['still_unclear', 'missing_evidence', 'confidence'].includes(item.section) && item.text) gaps.push(humanText(item.text));
  for (const hypothesis of review.diagnostic_hypotheses || []) {
    for (const item of hypothesis.missing_information || []) if (item.text) gaps.push(item.text);
    if (hypothesis.insufficient_support) gaps.push(`پشتوانهٔ کافی برای فرضیهٔ «${humanText(hypothesis.label)}» ثبت نشده است.`);
  }
  for (const item of review.limitations || []) if (item.text) gaps.push(humanText(item.text));
  for (const item of review.safety_red_flags || []) if (item.text) gaps.push(`نکتهٔ ایمنی: ${humanText(item.text)}`);
  for (const item of [...(review.patient_summary || []), ...(review.professional_report || [])]) {
    if (item.insufficient_support && item.text) gaps.push(`پشتوانهٔ کافی ثبت نشده: ${item.text}`);
  }
  const uniqueGaps = [...new Set(gaps)];
  const context = (report.sections || []).filter(item => ['your_question', 'dentist_recommendation'].includes(item.section));
  const discussion = (report.sections || []).filter(item => ['topics_to_discuss', 'questions_to_ask'].includes(item.section));
  const recommendedChecks = (review.diagnostic_hypotheses || []).flatMap(h => h.recommended_checks || []).filter(item => item.text);
  const dataMode = review.run?.mode;
  const modeNotice = dataMode === 'MOCK'
    ? 'این خروجی Mock برای نمونهٔ کاملاً ساختگی است؛ تفسیر بالینی تصویر انجام نشده و محتوا اعتبارسنجی بالینی نشده است.'
    : 'این خروجی حاصل بررسی مدل است و نیازمند تأیید انسانی است؛ تشخیص یا تعیین ضرورت درمان نیست.';
  const sourceList = sourceRows ? `<ol class="source-list">${sourceRows}</ol>` : '<p class="empty-state">منبعی برای این گزارش ثبت نشده است.</p>';
  const technicalSourceList = sourceTechnicalRows ? `<ol>${sourceTechnicalRows}</ol>` : '<p class="empty-state">شناسه‌ای ثبت نشده است.</p>';
  const technical = `<p>شناسهٔ snapshot: <bdi>${escapeHtml(report.snapshot_id || 'ثبت نشده')}</bdi></p><p>اجرا: <bdi>${escapeHtml(review.run?.provider || 'ثبت نشده')} / ${escapeHtml(review.run?.model || 'ثبت نشده')}</bdi></p><p>زمان: <bdi>${escapeHtml(review.run?.created_at || 'ثبت نشده')}</bdi>${Number.isFinite(review.run?.runtime_ms) ? ` · مدت: ${review.run.runtime_ms} ms` : ''}</p><p>شناسهٔ اجرا: <bdi>${escapeHtml(review.run?.run_id || 'ثبت نشده')}</bdi></p>`;
  const sourceContext = (report.presentation?.materials || []).map(m => `<li><bdi>${escapeHtml(m.filename)}</bdi>${m.image_analysis_disabled && dataMode === 'MOCK' ? ' — در اجرای Mock تفسیر بالینی تصویر انجام نشده است' : ''}</li>`).join('');
  const question = context.find(item => item.section === 'your_question');
  const recommendation = context.find(item => item.section === 'dentist_recommendation');
  $('report-content').innerHTML = `<p class="notice report-mode-notice">${modeNotice} گفته یا پیشنهاد درمان، اثبات ضرورت درمان نیست.</p><section class="case-context"><h2>زمینهٔ پرونده</h2>${question ? `<p><strong>سؤال شما</strong><br>${escapeHtml(question.text)}</p>` : '<p class="empty-state">سؤال پرونده در این گزارش موجود نیست.</p>'}${recommendation ? `<p><strong>پیشنهاد به روایت شما</strong><br>${escapeHtml(recommendation.text)}</p>` : ''}</section><section class="audience-report" data-audience="patient"><h2>خلاصه برای شما</h2><ul>${assertions(review.patient_summary)}</ul></section><section class="report-gaps"><h2>محدودیت‌ها و اطلاعات ناکافی</h2><ul>${uniqueGaps.length ? uniqueGaps.map(text => `<li>${escapeHtml(text)}</li>`).join('') : '<li class="empty-state">محدودیت یا مورد ناکافی جداگانه‌ای در دادهٔ گزارش ثبت نشده است.</li>'}</ul><p>کامل بودن پرونده به معنی کافی بودن شواهد یا ارزیابی بالینی نیست.</p></section>${discussion.length || recommendedChecks.length ? `<section class="discussion-points"><h2>برای گفت‌وگو با دندان‌پزشک</h2>${discussion.map(item => `<div><h3>${escapeHtml(SECTIONS[item.section])}</h3><p>${escapeHtml(humanText(item.text))}</p></div>`).join('')}${recommendedChecks.length ? `<h3>بررسی‌های مطرح‌شده</h3><ul>${assertions(recommendedChecks)}</ul>` : ''}</section>` : ''}<section class="evidence-context"><h2>مدارک در این بررسی</h2><ul>${sourceContext || '<li class="empty-state">مدرکی در گزارش ثبت نشده است.</li>'}</ul></section>${disclosure('پشتوانه و منبع هر ادعا', sourceList)}${disclosure('مشخصات فنی و شناسه‌های منابع', `${technical}${technicalSourceList}`, 'data-technical="true"')}<section class="audience-report" data-audience="professional"><h2>گزارش تخصصی</h2><ul>${assertions(review.professional_report)}</ul>${(review.diagnostic_hypotheses || []).length ? disclosure('فرضیه‌های بررسی‌شده', hypotheses) : ''}</section>`;
  $('report-footer').textContent = dataMode === 'MOCK'
    ? 'در اجرای Mock تصاویر تفسیر بالینی نشده‌اند. این گزارش تشخیص پزشکی نیست و ضرورت درمان را تعیین نمی‌کند؛ تصمیم درمانی به معاینه و گفت‌وگو با دندان‌پزشک نیاز دارد.'
    : 'تفسیر مدل نیازمند تأیید است و تشخیص پزشکی یا تعیین ضرورت درمان نیست؛ تصمیم درمانی به معاینه و گفت‌وگو با دندان‌پزشک نیاز دارد.';
  audience('patient');
  // Native disclosures remain keyboard operable; source links open their target.
  document.querySelectorAll('.source-link').forEach(link => link.addEventListener('click', () => {
    const target = document.getElementById(link.getAttribute('href').slice(1));
    if (target?.closest('details')) target.closest('details').open = true;
  }));
}
function renderReport(report, transition = true, replace = false) {
  state.report = report;
  if (transition) navigate('report', reportIdentity(report), replace);
  $('report-unavailable')?.classList.add('hidden');
  const urgent = report.report_kind === "URGENT";
  const review = report.report_kind === "REVIEW_PENDING";
  $("report-badge").textContent = urgent ? "نیازمند ارزیابی فوری" : review ? "گزارش ارزیابی شواهد آماده نیست" : report.safety_state === "CAUTION" ? "با توجه به محدودیت‌ها بخوانید" : "گزارش شواهد آماده است";
  $("report-badge").className = "badge" + (urgent ? " urgent" : "");
  let html = "";
  const p = report.presentation || {};
  $("audience-controls").classList.toggle("hidden", !report.review || urgent || review);
  if (report.review && !urgent && !review) {
    renderReview(report); renderFiles(); showView("report");
    $("view-report").querySelector("h1").focus(); return;
  }
  if (!urgent && !review) {
    const materials = (p.materials || []).map(m => `<li><bdi>${escapeHtml(m.filename)}</bdi>${m.image_analysis_disabled ? " — فقط ذخیره شده؛ تحلیل بالینی تصویر غیرفعال است" : " — مدرک بارگذاری‌شده"}</li>`).join("");
    html += section("پرونده شما / مدارک در اختیار", `<p>${state.sample ? "این پرونده و مدارک آن کاملاً ساختگی‌اند." : "این محیط فقط برای بررسی دادهٔ ساختگی است."}</p><ul>${materials || "<li>مدرکی ثبت نشده است.</li>"}</ul>`);
  }
  for (const item of report.sections || []) {
    // Preserve safety-only report boundaries even if an unexpected extra section arrives.
    if (urgent && item.section !== "safety_note") continue;
    if (review && item.section !== "review_pending") continue;
    const text = review && item.section === "review_pending"
      ? "این پرونده به بررسی دستی نیاز دارد و این نسخه امکان ارجاع به بازبین را ندارد؛ بنابراین گزارش ارزیابی شواهد ارائه نمی‌شود. دربارهٔ تصمیم درمانی با دندان‌پزشک گفت‌وگو کنید."
      : ["your_question", "dentist_recommendation"].includes(item.section) ? item.text : humanText(item.text);
    html += section(SECTIONS[item.section] || "جزئیات بررسی", `<p>${escapeHtml(text)}</p>`);
    if (item.section === "dentist_recommendation") html += '<p class="small">این گفته به روایت شماست؛ تأیید مستقل دندان‌پزشک یا اثبات ضرورت پزشکی نیست.</p>';
    if (item.section === "evidence_status") {
      html += section("پشتوانه و منبع هر ادعا", (p.claims || []).map(c => `<article class="claim"><h3>${escapeHtml(c.label)}</h3><p class="source">منبع: ${escapeHtml(c.source)}</p><p>${escapeHtml(c.status)}</p><ul>${c.evidence.length ? c.evidence.map(e => `<li><bdi>${escapeHtml(e.filename)}</bdi> — ${escapeHtml(e.relationship)}</li>`).join("") : "<li>پشتوانهٔ سندی مرتبط برای این ادعا ثبت نشده است.</li>"}</ul>${c.missing.length ? `<p>شواهد ناکافی؛ نیازمند: ${c.missing.map(escapeHtml).join("، ")}</p>` : ""}<p class="small">ثبت یا پیشنهاد درمان به معنی اثبات ضرورت پزشکی آن نیست.</p></article>`).join("") || "<p>ادعایی برای ارزیابی ثبت نشده است.</p>");
    }
  }
  if (!(report.review?.run?.mode)) $("report-footer").textContent = "تفسیر تصویر در مشخصات این گزارش ثبت نشده است. این گزارش تشخیص پزشکی نیست و ضرورت درمان را تعیین نمی‌کند؛ تصمیم درمانی به معاینه و گفت‌وگو با دندان‌پزشک نیاز دارد.";
  $("report-content").innerHTML = html; renderFiles(); showView("report");
  $("view-report").querySelector("h1").focus();
}
async function printReport() {
  if (state.busy || !state.caseId) return;
  ReportExport.discard();
  setBusy(true);
  const entry = navigation.current, revision = navigation.revision;
  try {
    // Revalidate authority/version immediately before offering export.
    const selectedAudience = document.querySelector('[data-audience]:not(.audience-hidden)')?.dataset.audience || 'patient';
    const report = await api(`/api/cases/${state.caseId}/report`);
    if (revision !== navigation.revision) return;
    if (!sameReport(entry, report)) { unavailableReport(); return; }
    ReportExport.prepare(report, selectedAudience);
    window.print();
  } catch (e) { ReportExport.discard(); if (revision === navigation.revision) { clearReport(); evidenceView(); error(e.message); } }
  finally { setBusy(false); }
}
async function resumeCase() {
  if (state.busy) return;
  try {
    const stored = JSON.parse(sessionStorage.getItem("dandoonjan_active_case") || "null");
    if (!stored?.id) return;
    navigation.session = navigationId(); navigation.draft = true;
    state.caseId = stored.id; state.sample = !!stored.sample;
    navigate("evidence"); const revision = navigation.revision; setBusy(true, "در حال دریافت وضعیت همین پرونده…");
    const current = await api(`/api/cases/${state.caseId}`);
    $("question").value = current.question; $("dentist").value = current.dentist_recommendation;
    const dossier = await api(`/api/cases/${state.caseId}/dossier`);
    dossierFields.forEach(id => $(id).value = dossier.fields[id] || "");
    showCompleteness(dossier);
    state.files = current.artifacts.map(a => localRow({file:null, name:a.filename, artifactId:a.artifact_id, uploadState:"uploaded", message:"مدرک ثبت‌شده در همین پرونده"}));
    renderFiles(); clearError();
    try {
      const report = await api(`/api/cases/${state.caseId}/report`);
      if (revision === navigation.revision) renderReport(report);
    }
    catch (e) { if (e.status !== 404) throw e; outcome(current); }
  } catch (e) { error(e.message); }
  finally { setBusy(false); }
}
$("start-case").onclick = startNewCase;
$("start-sample").onclick = startSample;
$("case-form").onsubmit = submitForm;
$("process-case").onclick = processCase;
$("retry-process").onclick = processCase;
$("print-report").onclick = printReport;
$("add-evidence").onclick = () => { evidenceView(); $("files").focus(); };
$("edit-case").onclick = () => {
  navigate("intake");
  $("submit-case").textContent = "ذخیرهٔ تغییرات همین پرونده"; $("question").focus();
};
$("new-case").onclick = startNewCase;
$("back-home").onclick = $("home-from-report").onclick = homeNavigation;
$("resume-case").onclick = resumeCase;
$("patient-view").onclick = () => audience("patient");
$("professional-view").onclick = () => audience("professional");
$("files").onchange = e => addFiles(e.target.files);
const dropzone = $("dropzone");
for (const name of ["dragenter", "dragover"]) dropzone.addEventListener(name, e => { e.preventDefault(); if (!state.busy) dropzone.classList.add("dragging"); });
for (const name of ["dragleave", "drop"]) dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.remove("dragging"); });
dropzone.addEventListener("drop", e => addFiles(e.dataTransfer.files));
try { if (JSON.parse(sessionStorage.getItem("dandoonjan_active_case") || "null")?.id) $("resume-case").classList.remove("hidden"); } catch (_) { /* Optional session continuity. */ }

navigate('home', {}, true);
