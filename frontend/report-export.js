/* Export presentation only. Never reads live dossier data or rewrites reports. */
"use strict";
window.ReportExport = (() => {
  const root = () => document.getElementById('report-export');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const safeLabel = value => {
    const basename = String(value ?? '').replace(/[\u0000-\u001f\u007f-\u009f\u061c\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]/g, '').split(/[\\/]/).filter(Boolean).pop()?.replace(/\s+/g, ' ').trim();
    return basename && !/^\.+$/.test(basename) ? basename : 'منبع ثبت‌شده';
  };
  const isolated = value => `<bdi dir="auto">${escape(safeLabel(value))}</bdi>`;
  const kinds = {PATIENT_REPORTED:'گفتهٔ شما', CLINICIAN_REPORTED:'گفتهٔ دندان‌پزشک به روایت شما', DOCUMENT_EXTRACTED:'محتوای سند', MODEL_INFERRED:'برداشت مدل؛ نیازمند تأیید'};
  const labels = {main_question:'سؤال اصلی', clinician_recommendation:'پیشنهاد دندان‌پزشک به روایت شما', context:'توضیحات شما', symptoms:'علائم', duration:'مدت علائم', medical_history:'سابقه پزشکی', medications:'داروها', allergies:'حساسیت‌ها', treatment_plan:'طرح درمان', previous_reports:'گزارش قبلی', previous_treatments:'درمان‌های قبلی'};
  const roles = {unspecified:'سایر مدارک', treatment_plan:'طرح درمان', prescription:'نسخه', dental_image:'تصویر دندان', previous_report:'گزارش قبلی'};
  const confidence = {LOW:'کم', MEDIUM:'متوسط', HIGH:'زیاد'};
  let originalTitle = null;
  let armed = false;
  function discard() {
    armed = false;
    document.body.classList.remove('export-prepared');
    root()?.replaceChildren();
    if (originalTitle !== null) document.title = originalTitle;
    originalTitle = null;
  }
  const section = (title, body, cls = '') => body ? `<section class="export-section ${cls}"><h2>${escape(title)}</h2>${body}</section>` : '';
  const paragraphs = text => String(text ?? '').split(/\r?\n/).filter(line => line.trim()).map(line => `<p dir="auto">${escape(line)}</p>`).join('');
  const lines = text => {
    // Preserve the screen's existing qualification of legacy empty-result text.
    if (['موردی باقی نمانده است.', 'شواهد کاملی ثبت شده است.'].includes(text)) text = 'در محدودهٔ این بررسی، مورد تکمیلی ثبت نشده است؛ این به معنی کامل بودن ارزیابی بالینی نیست.';
    const items = String(text ?? '').split(/\r?\n/).filter(line => line.trim());
    return items.length ? `<ul>${items.map(line => `<li dir="auto">${escape(line.replace(/^\s*•\s*/, ''))}</li>`).join('')}</ul>` : '';
  };
  function prepare(report, audience) {
    discard();
    if (!['STANDARD', 'URGENT', 'REVIEW_PENDING'].includes(report.report_kind)) throw new Error('نوع گزارش برای خروجی شناخته‌شده نیست.');
    const professional = audience === 'professional';
    const title = professional ? 'گزارش تخصصی' : 'خلاصه برای شما';
    const sections = report.sections || [];
    const find = name => sections.filter(s => s.section === name).map(s => s.text).filter(Boolean);
    const sectionText = (name, heading, list = false) => section(heading, find(name).map(list ? lines : paragraphs).join(''));
    const review = report.report_kind === 'STANDARD' ? report.review : null;
    // Existing product copy, selected from the authoritative response's mode.
    const demo = 'دموی کنترل‌شده، فقط برای دادهٔ ساختگی؛ پشتیبان تصمیم است، نه تشخیص. دانشنامهٔ توسعه از نظر بالینی اعتبارسنجی نشده است.';
    const limitation = review?.run?.mode === 'MOCK'
      ? 'در اجرای Mock تصاویر تفسیر بالینی نشده‌اند. این گزارش تشخیص پزشکی نیست و ضرورت درمان را تعیین نمی‌کند؛ تصمیم درمانی به معاینه و گفت‌وگو با دندان‌پزشک نیاز دارد.'
      : review?.run?.mode ? 'تفسیر مدل نیازمند تأیید است و تشخیص پزشکی یا تعیین ضرورت درمان نیست؛ تصمیم درمانی به معاینه و گفت‌وگو با دندان‌پزشک نیاز دارد.'
        : 'تفسیر تصویر در مشخصات این گزارش ثبت نشده است. این گزارش تشخیص پزشکی نیست و ضرورت درمان را تعیین نمی‌کند؛ تصمیم درمانی به معاینه و گفت‌وگو با دندان‌پزشک نیاز دارد.';
    const sources = review?.source_index || [];
    const materials = report.presentation?.materials || [];
    const artifactIds = [...new Set(sources.filter(s => s.artifact_id).map(s => s.artifact_id))];
    const byRef = new Map(sources.map((source, index) => [source.source_ref, {source, number:index+1}]));
    const readable = source => {
      const material = source.artifact_id ? materials[artifactIds.indexOf(source.artifact_id)] : null;
      const label = labels[source.label] || kinds[source.kind] || 'منبع ثبت‌شده';
      return `${escape(label)}${material?.filename ? ` · ${isolated(material.filename)}` : ''}${roles[source.document_role] ? ` · ${escape(roles[source.document_role])}` : ''}${source.page != null ? ` · صفحهٔ <bdi dir="ltr">${escape(source.page)}</bdi>` : ''}`;
    };
    const refs = values => (values || []).map(ref => {
      const item = byRef.get(ref);
      if (!item) throw new Error('منبع گزارش قابل نمایش نیست.');
      return `<a href="#export-source-${item.number}"><bdi dir="ltr">[${item.number}]</bdi> ${readable(item.source)}</a>`;
    }).join('؛ ');
    const assertions = (values, cls = '') => values?.length ? `<ul class="export-assertions">${values.map(item => `<li class="export-assertion ${cls}"><div dir="auto">${escape(item.text)}</div>${item.insufficient_support ? '<p class="export-support">پشتوانهٔ کافی ثبت نشده است.</p>' : ''}${item.source_refs?.length ? `<p class="export-reference">منبع: ${refs(item.source_refs)}</p>` : ''}</li>`).join('')}</ul>` : '';
    const hypothesisDetail = (title, values) => values?.length ? `<div class="export-hypothesis-detail"><h4>${escape(title)}</h4>${assertions(values)}</div>` : '';
    let body = '';
    if (report.report_kind === 'STANDARD') {
      body += sectionText('your_question', 'سؤال شما');
      body += sectionText('dentist_recommendation', 'پیشنهاد دندان‌پزشک به روایت شما');
      body += '<p class="export-attribution">این گفته به روایت شماست؛ تأیید مستقل دندان‌پزشک یا اثبات ضرورت پزشکی نیست.</p>';
      if (review) body += section(title, assertions(professional ? review.professional_report : review.patient_summary), 'export-summary');
      else {
        body += sectionText('found_in_documents', 'آنچه در مدارک ثبت شده است', true);
        body += sectionText('evidence_status', 'وضعیت شواهد', true);
      }
      for (const [name, heading] of [['still_unclear','آنچه هنوز روشن نیست'], ['missing_evidence','شواهد تکمیلی'], ['confidence','محدودیت اطمینان']]) body += sectionText(name, heading, true);
      if (professional) {
        const claims = report.presentation?.claims || [];
        body += section('ارزیابی ادعاهای موجود', claims.map(c => `<article class="export-claim"><h3>${escape(c.label)}</h3><p>منبع: ${escape(c.source)}</p><p dir="auto">${escape(c.status)}</p>${c.evidence?.length ? `<ul>${c.evidence.map(e => `<li>${isolated(e.filename)} — ${escape(e.relationship)}</li>`).join('')}</ul>` : '<p>پشتوانهٔ سندی مرتبط برای این ادعا ثبت نشده است.</p>'}${c.missing?.length ? `<p>شواهد ناکافی؛ نیازمند: ${c.missing.map(escape).join('، ')}</p>` : ''}<p>ثبت یا پیشنهاد درمان به معنی اثبات ضرورت پزشکی آن نیست.</p></article>`).join(''));
        body += section('فرضیه‌های بررسی‌شده؛ نیازمند تأیید', (review?.diagnostic_hypotheses || []).map(h => `<article class="export-hypothesis"><h3>${escape(h.label)}</h3><p>پشتیبانی کیفی مدل: ${escape(confidence[h.confidence_label] || 'ثبت نشده')} — این مورد تشخیص یا احتمال قطعی نیست.</p>${h.insufficient_support ? '<p>پشتوانهٔ کافی ثبت نشده است.</p>' : ''}<p class="export-reference">شواهد پشتیبان: ${refs(h.supporting_evidence_refs) || 'ثبت نشده'}</p><p class="export-reference">شواهد ناسازگار: ${refs(h.contradicting_evidence_refs) || 'ثبت نشده؛ به معنی نبود ناسازگاری نیست'}</p>${hypothesisDetail('اطلاعات ناقص', h.missing_information)}${hypothesisDetail('بررسی‌های قابل گفت‌وگو', h.recommended_checks)}</article>`).join(''));
      }
      body += sectionText('topics_to_discuss', 'برای گفت‌وگو با دندان‌پزشک', true);
      body += sectionText('questions_to_ask', 'پیش از تصمیم بپرسید', true);
      // Checks can be shared without exporting the professional hypothesis narrative.
      if (!professional) body += section('بررسی‌های قابل گفت‌وگو', assertions((review?.diagnostic_hypotheses || []).flatMap(h => h.recommended_checks || [])));
      body += section('محدودیت‌های ثبت‌شده', assertions(review?.limitations, 'export-limitation'));
      body += section('نکات ایمنی ثبت‌شده', assertions(review?.safety_red_flags), 'export-safety');
      const inventory = sources.length ? `<ol>${sources.map((s, i) => `<li class="export-source" id="export-source-${i+1}">${readable(s)} · ${escape(kinds[s.kind] || 'منبع ثبت‌شده')}</li>`).join('')}</ol>` : materials.length ? `<ul>${materials.map(m => `<li class="export-source">${isolated(m.filename)}${m.image_analysis_disabled ? ' — فقط ذخیره شده؛ تحلیل بالینی تصویر غیرفعال است' : ''}</li>`).join('')}</ul>` : '<p>مدرکی در گزارش ثبت نشده است.</p>';
      body += section('مدارک و منابع این بررسی', inventory);
    }
    if (report.report_kind === 'REVIEW_PENDING') body += sectionText('review_pending', 'نیازمند بررسی دستی');
    // Exact safety content from the response, never a substitute clinical rule.
    body += section('محدودیت‌های ایمنی', find('safety_note').map(paragraphs).join(''), 'export-safety');
    const status = report.report_kind === 'URGENT' ? 'نیازمند ارزیابی فوری' : report.report_kind === 'REVIEW_PENDING' ? 'گزارش ارزیابی شواهد آماده نیست' : report.safety_state === 'CAUTION' ? 'با توجه به محدودیت‌ها بخوانید' : 'گزارش شواهد آماده است';
    const exportedAt = new Intl.DateTimeFormat('fa-IR', {dateStyle:'medium', timeStyle:'short'}).format(new Date());
    root().innerHTML = `<header class="export-header"><p class="export-brand">دندونجان · <bdi dir="ltr">DANDOONJAN</bdi></p><h1>${title}</h1><p>${status}</p><p>زمان خروجی: <bdi dir="auto">${escape(exportedAt)}</bdi></p><p class="export-validity">این نسخه بر اساس گزارش معتبر هنگام تهیهٔ خروجی است؛ با تغییر اطلاعات پرونده ممکن است دیگر گزارش فعلی نباشد.</p></header>${section('دامنهٔ استفاده', paragraphs(demo), 'export-safety')}${body}<footer class="export-footer">${paragraphs(limitation)}</footer>`;
    originalTitle = document.title;
    document.title = `DANDOONJAN — ${title}`;
    armed = true;
    document.body.classList.add('export-prepared');
  }
  window.addEventListener('beforeprint', () => {
    if (!armed) discard();
  });
  window.addEventListener('afterprint', discard);
  return {prepare, discard};
})();
