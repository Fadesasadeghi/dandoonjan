# DandoonJan presentation runbook

## Before the meeting

1. Open the Netlify URL and confirm `/health` returns `{"status":"ok"}`.
2. Confirm the FastAPI service is running with `DJ_AI_PROVIDER=mock`.
3. Use a private/incognito window or click «بررسی پرونده دیگر» for a fresh run.
4. If the backend was newly deployed, wait for `/health` before opening the demo.

## 2–3 minute demo

1. Open `/` and briefly show «قبل از درمان، مطمئن تصمیم بگیر.»
2. Click «مشاهده پرونده نمونه».
3. Let the real flow run: sample artifact → processing → evidence assessment.
4. Show «آنچه مدارک نشان می‌دهند» and point out that a plan mention is not proof of necessity.
5. Show «آنچه هنوز مشخص نیست» and «سؤال‌هایی که قبل از درمان باید بپرسید».
6. Close with the safety note: this is decision support, not a diagnosis.

## Emergency fallback

- If OpenRouter fails: keep `DJ_AI_PROVIDER=mock`; the presentation does not need OpenRouter.
- If a sample run fails: click «تلاش دوباره»; if needed refresh and click the sample CTA again.
- If the service restarted: wait for `/health`, then start a fresh sample case.
- If the browser is stale: open the same Netlify URL in a private window.
