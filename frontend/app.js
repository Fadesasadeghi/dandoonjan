"use strict";
const $ = id => document.getElementById(id);
const state = {caseId: null, files: [], busy: false, sample: false, report: null, createUncertain: false};
const DOSSIER = {symptoms:"علائم", duration:"مدت علائم", medical_history:"سابقه پزشکی", medications:"داروها", allergies:"حساسیت‌ها", treatment_plan:"طرح درمان", previous_reports:"گزارش قبلی", previous_treatments:"درمان‌های قبلی", dental_images:"تصویر دندان", main_question:"سؤال اصلی"};
const dossierFields = Object.keys(DOSSIER).filter(id => $(id));
function showCompleteness(data) { $("completeness").textContent = data.missing_information.length ? "برای پروندهٔ کامل‌تر: " + data.missing_information.map(k => DOSSIER[k] || k).join("، ") : "بخش‌های اطلاعاتی ثبت شده‌اند؛ این به معنی کافی بودن شواهد بالینی نیست."; }
const STATUS = {pending: "در انتظار ارسال", uploading: "در حال آپلود", uploaded: "آپلود شد", rejected: "رد شد", duplicate: "تکراری", attention: "نیازمند توجه"};
const TREATMENTS = {ROOT_CANAL: "عصب‌کشی", EXTRACTION: "کشیدن دندان", CROWN: "روکش", FILLING: "ترمیم", SCALING: "جرم‌گیری", IMPLANT: "ایمپلنت", BRIDGE: "بریج", DENTURE: "دندان مصنوعی", ORTHODONTICS: "ارتودنسی", UNKNOWN: "نامشخص"};
const SECTIONS = {your_question: "سؤال شما", dentist_recommendation: "درمان پیشنهادی به روایت شما", found_in_documents: "آنچه می‌دانیم", evidence_status: "وضعیت شواهد", still_unclear: "آنچه هنوز نمی‌دانیم", missing_evidence: "شواهد تکمیلی", topics_to_discuss: "نکات نیازمند بررسی", questions_to_ask: "پیش از تصمیم بپرسید", confidence: "محدودیت اطمینان", safety_note: "محدودیت‌های ایمنی", review_pending: "نیازمند بررسی دستی"};
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function humanText(text) {
  if (["موردی باقی نمانده است.", "شواهد کاملی ثبت شده است."].includes(text)) return "در محدودهٔ این بررسی، مورد تکمیلی ثبت نشده است؛ این به معنی کامل بودن ارزیابی بالینی نیست.";
  return String(text).replace(/\b(ROOT_CANAL|EXTRACTION|CROWN|FILLING|SCALING|IMPLANT|BRIDGE|DENTURE|ORTHODONTICS|UNKNOWN)\b/g, key => TREATMENTS[key]);
}
class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; }
}
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch (_) { throw new ApiError("ارتباط قطع شد؛ نتیجهٔ این درخواست مشخص نیست. پروندهٔ موجود را نگه داشته‌ایم."); }
  let payload;
  try { payload = await response.json(); }
  catch (_) { throw new ApiError("پاسخ سرویس قابل خواندن نیست؛ دوباره وضعیت همین پرونده را بررسی کنید.", response.status); }
  if (!response.ok) throw new ApiError(payload.detail?.message_fa || payload.message_fa || (response.status === 404 ? "گزارش فعلی در دسترس نیست؛ همین پرونده را دوباره بررسی کنید." : "درخواست کامل نشد. لطفاً دوباره تلاش کنید."), response.status);
  return payload;
}
function saveCase() {
  try { sessionStorage.setItem("dandoonjan_active_case", JSON.stringify({id: state.caseId, sample: state.sample})); } catch (_) { /* Storage is optional; in-page retry still works. */ }
  $("resume-case").classList.toggle("hidden", !state.caseId);
}
function showView(name) {
  ["home", "workspace", "report"].forEach(v => $("view-" + v).classList.toggle("active", v === name));
  document.body.classList.toggle("print-ready", name === "report" && !!state.report);
  window.scrollTo({top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
}
function setBusy(busy, message = "") {
  state.busy = busy;
  document.querySelectorAll("button, textarea, input").forEach(el => { el.disabled = busy; });
  if (state.createUncertain) $("submit-case").disabled = true;
  $("activity").textContent = message;
  $("view-workspace").setAttribute("aria-busy", String(busy));
}
function error(message) {
  $("workspace-error").textContent = message;
  $("workspace-error").classList.remove("hidden");
}
function clearError() { $("workspace-error").classList.add("hidden"); }
function clearReport() { state.report = null; $("report-content").replaceChildren(); document.body.classList.remove("print-ready"); }
function renderFiles() {
  const html = state.files.map((row, i) => `<li data-upload-state="${row.status}"><bdi class="filename">${escapeHtml(row.name)}</bdi><span class="file-status">${STATUS[row.status]}</span>${row.message ? `<span class="file-message">${escapeHtml(row.message)}</span>` : ""}${row.retry ? `<button type="button" class="btn text retry-file" data-index="${i}">تلاش دوباره برای این فایل</button>` : ""}</li>`).join("");
  $("file-list").innerHTML = html;
  $("report-files").innerHTML = html;
  $("upload-summary").classList.toggle("hidden", !state.files.length);
  document.querySelectorAll(".retry-file").forEach(button => {
    button.disabled = state.busy;
    button.onclick = () => {
      if (state.busy) return;
      const row = state.files[Number(button.dataset.index)];
      row.status = "pending"; row.retry = false; row.message = "";
      evidenceView(); renderFiles();
    };
  });
}
function addFiles(files) {
  if (state.busy) return;
  for (const file of files) state.files.push({file, name: file.name, role:$("document-role").value, status: "pending", message: ""});
  $("files").value = "";
  renderFiles();
}
function evidenceView() {
  showView("workspace");
  $("intake-panel").classList.remove("hidden");
  $("evidence-panel").classList.remove("hidden");
  $("case-question").textContent = $("question").value;
  $("sample-notice").classList.toggle("hidden", !state.sample);
}
function startNewCase() {
  if (state.busy) return;
  Object.assign(state, {caseId: null, files: [], sample: false, report: null, createUncertain: false});
  clearReport(); clearError();
  $("case-form").reset(); $("evidence-panel").classList.add("hidden");
  $("intake-panel").classList.remove("hidden"); $("sample-notice").classList.add("hidden");
  $("outcome").classList.add("hidden"); $("submit-case").textContent = "ساخت پرونده و افزودن مدارک";
  renderFiles(); setBusy(false); showView("workspace"); $("question").focus();
}
async function createOrUpdate() {
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
  evidenceView();
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
  for (const row of state.files.filter(r => r.status === "pending")) {
    row.status = "uploading"; renderFiles();
    setBusy(true, "در حال آپلود فایل‌ها…");
    const data = new FormData(); data.append("file", row.file);
    data.append('document_role', row.role || 'unspecified');
    try {
      const result = await api(`/api/cases/${state.caseId}/artifacts`, {method: "POST", body: data});
      row.artifactId = result.artifact_id;
      row.status = result.duplicate_of ? "duplicate" : "uploaded";
      row.message = result.duplicate_of ? "این مدرک قبلاً در همین پرونده ثبت شده است." : "";
      if (/\.(png|jpe?g|heic)$/i.test(row.name)) row.message += " تصویر ذخیره شد؛ تحلیل بالینی تصویر غیرفعال است.";
    } catch (e) {
      row.status = e.status === 422 ? "rejected" : "attention";
      row.message = e.message;
      row.retry = row.status === "attention";
    }
    renderFiles();
  }
}
function applyAttention(result) {
  const ids = new Set([...(result.needs_more_evidence || []), ...(result.rejected_artifacts || [])]);
  const limited = new Set(result.limitations || []);
  for (const row of state.files) {
    if (limited.has(row.artifactId) && row.status === "uploaded") {
      row.status = "attention";
      row.message = "آپلود شد؛ بررسی این مدرک محدودیت دارد. تصاویر فقط ذخیره می‌شوند و تحلیل بالینی نمی‌شوند.";
    }
    if (ids.has(row.artifactId) && row.status === "uploaded") {
      row.status = "attention";
      row.message = "فایل آپلود شده، اما برای بررسی کافی یا قابل استفاده نیست. مدرک متنی روشن‌تری اضافه کنید. تصاویر تحلیل بالینی نمی‌شوند.";
    }
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
  $("outcome-title").focus();
}
async function processCase() {
  if (state.busy || !state.caseId) return;
  clearError(); clearReport(); $("outcome").classList.add("hidden"); evidenceView();
  try {
    await createOrUpdate();
    setBusy(true, "در حال آپلود فایل‌ها…");
    await uploadPending();
    setBusy(true, "در حال پردازش در سرور؛ لطفاً منتظر بمانید…");
    $("analysis-scene").classList.remove("hidden");
    $("view-workspace").classList.add("analyzing");
    $("analysis-scene").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
    const result = await api(`/api/cases/${state.caseId}/process`, {method: "POST"});
    applyAttention(result);
    if (result.report) {
      setBusy(true, "در حال آماده‌سازی نتیجه…");
      renderReport(await api(`/api/cases/${state.caseId}/report`));
    } else outcome(result);
  } catch (e) {
    error(e.message); outcome({status: "FAILED"});
  } finally { $("view-workspace").classList.remove("analyzing"); $("analysis-scene").classList.add("hidden"); setBusy(false); renderFiles(); }
}
async function startSample() {
  if (state.busy) return;
  startNewCase(); state.sample = true;
  $("sample-notice").classList.remove("hidden");
  $("question").value = "آیا پیشنهاد عصب‌کشی برای دندان ۴۶ پشتیبانی کافی دارد؟";
  $("dentist").value = "دندان‌پزشک عصب‌کشی و روکش را پیشنهاد کرده است.";
  Object.entries({symptoms:"حساسیت به سرما در دندان ۴۶ — نمونهٔ ساختگی", duration:"سه روز", medical_history:"سابقهٔ مهمی گزارش نشده؛ ساختگی", medications:"ندارد", allergies:"ندارد", treatment_plan:"Treatment Plan\nTooth 46: RCT recommended", previous_reports:"گزارش قبلی ساختگی؛ معاینه تکمیلی ثبت نشده", previous_treatments:"ندارد"}).forEach(([key,value]) => $(key).value = value);
  try {
    setBusy(true, "در حال دریافت مدرک ساختگی نمونه…");
    const response = await fetch("/api/demo/sample");
    if (!response.ok) throw new ApiError("مدرک نمونه در دسترس نیست؛ می‌توانید مدارک ساختگی خودتان را اضافه کنید.", response.status);
    const file = new File([await response.text()], "طرح-درمان-نمونه.txt", {type: "text/plain"});
    state.files.push({file, name: file.name, status: "pending", message: "مدرک نمونهٔ ساختگی"});
    for (const [path,name,type,role] of [['sample-image','synthetic-pattern-not-radiograph.png','image/png','dental_image'], ['sample-plan','synthetic-plan.pdf','application/pdf','treatment_plan']]) {
      const asset = await fetch('/api/demo/' + path);
      if (!asset.ok) throw new ApiError('مدرک نمونه در دسترس نیست.');
      const extra = new File([await asset.blob()], name, {type});
      state.files.push({file:extra, name, role, status:'pending', message:'ساختگی؛ الگوی تصویر، رادیوگرافی واقعی نیست.'});
    }
    const previous = new File(['Synthetic prior clinical note\nTooth 46: cold sensitivity reported. No examination recorded.'], 'synthetic-prior-report.txt', {type:'text/plain'});
    state.files.push({file:previous, name:previous.name, role:'previous_report', status:'pending', message:'گزارش قبلی کاملاً ساختگی'});
    renderFiles(); await createOrUpdate();
  } catch (e) { error(e.message); }
  finally { setBusy(false); }
  if (state.caseId) await processCase();
}
function section(title, body) { return `<section class="report-section"><h2>${escapeHtml(title)}</h2>${body}</section>`; }
function audience(name) {
  document.querySelectorAll('[data-audience]').forEach(el => el.classList.toggle('audience-hidden', el.dataset.audience !== name));
  ['patient', 'professional'].forEach(key => { $(key + '-view').setAttribute('aria-pressed', String(key === name)); $(key + '-view').className = 'btn ' + (key === name ? 'primary' : 'quiet'); });
}
function renderReview(report) {
  const review = report.review;
  const refs = values => values.map(ref => `<a class="source-link" href="#source-${escapeHtml(ref)}"><bdi>${escapeHtml(ref)}</bdi></a>`).join('، ');
  const assertions = values => (values || []).map(a => `<li>${escapeHtml(a.text)}${a.insufficient_support ? '<small> — بدون پشتوانه کافی</small>' : ''}<div>${refs(a.source_refs || [])}</div></li>`).join('');
  const disclosure = (title, html) => `<details class="result-disclosure"><summary>${escapeHtml(title)}</summary><div>${html}</div></details>`;
  const hypotheses = review.diagnostic_hypotheses.map((h, i) => `<article class="hypothesis"><h3>${i+1}. ${escapeHtml(h.label)}</h3><p>پشتیبانی کیفی مدل: <bdi>${escapeHtml(h.confidence_label)}</bdi> — احتمال بیماری یا تشخیص قطعی نیست.</p>${h.insufficient_support ? '<p>بدون پشتوانه کافی</p>' : ''}<p>شواهد پشتیبان: ${refs(h.supporting_evidence_refs) || 'ثبت نشده'}</p><p>شواهد ناسازگار: ${refs(h.contradicting_evidence_refs) || 'ثبت نشده؛ به معنی نبود ناسازگاری نیست'}</p><h4>اطلاعات ناقص</h4><ul>${assertions(h.missing_information)}</ul><h4>بررسی‌های پیشنهادی</h4><ul>${assertions(h.recommended_checks)}</ul></article>`).join('');
  const sources = `<ol>${review.source_index.map(s => `<li id="source-${escapeHtml(s.source_ref)}"><bdi>${escapeHtml(s.source_ref)}</bdi> — ${escapeHtml(s.kind)}${s.page ? ' · صفحه ' + s.page : ''}<br><small>شناسهٔ محتوا: <bdi>${escapeHtml(s.sha256)}</bdi></small></li>`).join('')}</ol>`;
  $('report-content').innerHTML = `<p class="notice">${review.run.mode === 'MOCK' ? 'اجرای Mock؛ این پروندهٔ نمونه کاملاً ساختگی است و تحلیل واقعی تصویر انجام نشده است.' : 'اجرای مدل واقعی؛ تفسیر مدل نیازمند بررسی است.'} ثبت پیشنهاد درمان، اثبات ضرورت درمان نیست.</p><section data-audience="patient"><h2>خلاصه برای شما</h2><ul>${assertions(review.patient_summary)}</ul></section><section data-audience="professional"><h2>گزارش تخصصی</h2><ul>${assertions(review.professional_report)}</ul></section>${disclosure('احتمال‌های مطرح', hypotheses)}${disclosure('پشتوانه و منبع هر ادعا', sources)}${disclosure('محدودیت‌ها و آنچه هنوز روشن نیست', '<ul>' + assertions(review.limitations) + '</ul>')}<section class="run-metadata"><h2>مشخصات همین بررسی</h2><p>شناسهٔ snapshot: <bdi>${escapeHtml(report.snapshot_id)}</bdi></p><p><bdi>${escapeHtml(review.run.provider)} / ${escapeHtml(review.run.model)}</bdi></p><p>زمان: <bdi>${escapeHtml(review.run.created_at)}</bdi> · مدت: ${review.run.runtime_ms} ms</p><p>شناسهٔ اجرا: <bdi>${escapeHtml(review.run.run_id)}</bdi></p></section>`;
  const question = (report.sections || []).find(item => item.section === 'your_question');
  if (question) $('report-content').insertAdjacentHTML('afterbegin', section('سؤال شما', `<p>${escapeHtml(question.text)}</p>`));
  audience('patient');
  // Native disclosures remain keyboard operable; source links open their target.
  document.querySelectorAll('.source-link').forEach(link => link.addEventListener('click', () => {
    const target = document.getElementById(link.getAttribute('href').slice(1));
    if (target?.closest('details')) target.closest('details').open = true;
  }));
}
let printDisclosures = [];
window.addEventListener('beforeprint', () => { printDisclosures = [...document.querySelectorAll('#report-content details')].map(el => [el, el.open]); printDisclosures.forEach(([el]) => el.open = true); });
window.addEventListener('afterprint', () => printDisclosures.forEach(([el, open]) => el.open = open));
function renderReport(report) {
  state.report = report;
  const urgent = report.report_kind === "URGENT";
  const review = report.report_kind === "REVIEW_PENDING";
  $("report-badge").textContent = urgent ? "نیازمند ارزیابی فوری" : review ? "در انتظار بررسی دستی" : report.safety_state === "CAUTION" ? "با توجه به محدودیت‌ها بخوانید" : "گزارش شواهد آماده است";
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
    const text = ["your_question", "dentist_recommendation"].includes(item.section) ? item.text : humanText(item.text);
    html += section(SECTIONS[item.section] || "جزئیات بررسی", `<p>${escapeHtml(text)}</p>`);
    if (item.section === "dentist_recommendation") html += '<p class="small">این گفته به روایت شماست؛ تأیید مستقل دندان‌پزشک یا اثبات ضرورت پزشکی نیست.</p>';
    if (item.section === "evidence_status") {
      html += section("پشتوانه و منبع هر ادعا", (p.claims || []).map(c => `<article class="claim"><h3>${escapeHtml(c.label)}</h3><p class="source">منبع: ${escapeHtml(c.source)}</p><p>${escapeHtml(c.status)}</p><ul>${c.evidence.length ? c.evidence.map(e => `<li><bdi>${escapeHtml(e.filename)}</bdi> — ${escapeHtml(e.relationship)}</li>`).join("") : "<li>پشتوانهٔ سندی مرتبط برای این ادعا ثبت نشده است.</li>"}</ul>${c.missing.length ? `<p>شواهد ناکافی؛ نیازمند: ${c.missing.map(escapeHtml).join("، ")}</p>` : ""}<p class="small">ثبت یا پیشنهاد درمان به معنی اثبات ضرورت پزشکی آن نیست.</p></article>`).join("") || "<p>ادعایی برای ارزیابی ثبت نشده است.</p>");
    }
  }
  $("report-content").innerHTML = html; renderFiles(); showView("report");
  $("view-report").querySelector("h1").focus();
}
async function printReport() {
  if (state.busy || !state.caseId) return;
  setBusy(true);
  try {
    // Revalidate authority/version immediately before offering export.
    renderReport(await api(`/api/cases/${state.caseId}/report`));
    window.print();
  } catch (e) { clearReport(); evidenceView(); error(e.message); }
  finally { setBusy(false); }
}
async function resumeCase() {
  if (state.busy) return;
  try {
    const stored = JSON.parse(sessionStorage.getItem("dandoonjan_active_case") || "null");
    if (!stored?.id) return;
    state.caseId = stored.id; state.sample = !!stored.sample;
    showView("workspace"); setBusy(true, "در حال دریافت وضعیت همین پرونده…");
    const current = await api(`/api/cases/${state.caseId}`);
    $("question").value = current.question; $("dentist").value = current.dentist_recommendation;
    const dossier = await api(`/api/cases/${state.caseId}/dossier`);
    dossierFields.forEach(id => $(id).value = dossier.fields[id] || "");
    showCompleteness(dossier);
    state.files = current.artifacts.map(a => ({name: a.filename, artifactId: a.artifact_id, status: "uploaded", message: "مدرک ثبت‌شده در همین پرونده"}));
    renderFiles(); evidenceView(); clearError();
    try { renderReport(await api(`/api/cases/${state.caseId}/report`)); }
    catch (e) { if (e.status !== 404) throw e; outcome(current); }
  } catch (e) { showView("workspace"); error(e.message); }
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
  $("intake-panel").classList.remove("hidden"); $("evidence-panel").classList.add("hidden");
  $("submit-case").textContent = "ذخیرهٔ تغییرات همین پرونده"; $("question").focus();
};
$("new-case").onclick = startNewCase;
$("back-home").onclick = $("home-from-report").onclick = () => { if (!state.busy) showView("home"); };
$("resume-case").onclick = resumeCase;
$("patient-view").onclick = () => audience("patient");
$("professional-view").onclick = () => audience("professional");
$("files").onchange = e => addFiles(e.target.files);
const dropzone = $("dropzone");
for (const name of ["dragenter", "dragover"]) dropzone.addEventListener(name, e => { e.preventDefault(); if (!state.busy) dropzone.classList.add("dragging"); });
for (const name of ["dragleave", "drop"]) dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.remove("dragging"); });
dropzone.addEventListener("drop", e => addFiles(e.dataTransfer.files));
try { if (JSON.parse(sessionStorage.getItem("dandoonjan_active_case") || "null")?.id) $("resume-case").classList.remove("hidden"); } catch (_) { /* Optional session continuity. */ }
