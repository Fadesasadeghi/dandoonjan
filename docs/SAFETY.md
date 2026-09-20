# Safety Gate

Separate engine (`app/pipeline/assessment.py::run_safety_gate`); states NORMAL,
CAUTION, URGENT_EVALUATION, MANUAL_REVIEW, BLOCKED. Detects configured urgent
patterns (severe bleeding, facial swelling, airway/swallowing, trauma, rapidly
worsening symptoms, high fever) in patient-provided text; fail-closed triggers for
unresolved HIGH-importance gaps (MANUAL_REVIEW). The report composer may never
downgrade safety state; URGENT_EVALUATION renders only the urgent-care message.
Report text passes a forbidden-phrase check ("you definitely need...", "your dentist
is wrong...", medication directives) and raises SafetyBlockedError otherwise.

## P0 fail-closed report policy (P0-06)

NORMAL -> normal report | CAUTION -> report with constrained safety language |
URGENT_EVALUATION -> urgent-safe content only | MANUAL_REVIEW -> normal report
BLOCKED; an explicit review-pending report only; case state MANUAL_REVIEW_REQUIRED
(never REPORT_READY) | BLOCKED -> no report at all. The composer verifies snapshot
integrity and ownership before composing and cannot downgrade the safety state.
BLOCKED patterns cover unsafe medication/self-treatment requests; MANUAL_REVIEW
triggers include critical unresolved evidence gaps and low-confidence extraction
(< 0.5) on material claims.
