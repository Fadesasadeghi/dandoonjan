# Next-phase contract — approved 2026-09-29

Base: `273e8c3e472a81162a28ce3cab4de39103801c76`; work branch:
`agent/sadeghi-next-phase`. PR #4 and its branch remain protected.
The reference brief is authoritative; its four PNGs are art direction only.

## Execution boundary

Offline implementation and synthetic tests only. No keys, live provider requests,
paid services, asset acquisition, deployment, or major frontend dependencies.
Preserve the modular monolith and every protected P0/P1/RC invariant.

## Safety and confidence

Deterministic safety restrictions remain authoritative. Model-derived red flags
may escalate concern but cannot downgrade, suppress, override, or clear urgent,
review, or blocked states. Restricted reports cannot expose routine hypotheses.
Hypothesis confidence is exactly LOW/MEDIUM/HIGH: qualitative model uncertainty
and support only, never disease probability, diagnostic certainty or clinical truth.
No numeric hypothesis confidence. No definitive diagnosis or direct prescription.

## Dossier

Separately record symptoms, duration, medical history, medications, allergies,
treatment plan/prescription text and documents, radiographs/dental images, previous
reports/treatments, and main question. Missing is distinct from an explicit 'none'.
Incomplete intake is allowed; completeness describes supplied information, never
clinical adequacy. Changes increment case version and invalidate current reports.
Preserve versioned source history; no destructive backfill of existing context.

## Output and provenance

Versioned output contains patient_summary, professional_report,
diagnostic_hypotheses, safety_red_flags, limitations and source_index.
Each hypothesis has label, confidence_label, supporting_evidence_refs,
contradicting_evidence_refs, missing_information and recommended_checks.
Assertions carry source refs or an explicit insufficient-support marker.
References resolve only within the same case, revision and derivation; never invent
locators or collapse independent clinician/document sources. Model interpretation
remains MODEL_INFERRED. Reference validity does not establish clinical correctness.
Both audience reports and PDF derive from one integrity-checked immutable snapshot.
Old snapshots and treatment-claim semantics remain unchanged.

## Provider boundary

Explicit Mock remains deterministic. Explicit real mode fails closed regardless of
environment. Backend-only text/image transport; opaque outbound names and stripped
metadata; preserved originals and traceable derivatives. Bound pages, pixels,
payload size, attempts and total duration. Audit provider/model/runtime/run identity
without logging prompts, content, keys, URLs or raw exceptions.

## Synthetic acceptance fixture specification

Use an invented adult case with three days of cold sensitivity around tooth 46,
an explicitly synthetic medical history, medications/allergies recorded as none,
an independently sourced proposed treatment plan, a prior report, and a question
about the evidence and remaining checks. No patient identifiers.
Offline image fixture is a programmatically constructed nonclinical dental-image
test pattern, explicitly not a real radiograph and not diagnostic evidence.
It proves transport only. A legally permitted anonymized radiograph remains required
for later real acceptance; no real patient data or asset acquisition is authorized.
Mock hypotheses are test fixtures, never clinical expected answers.

## Acceptance

Run protected baseline first, regression-first changes, populated synthetic
migrations, source isolation, shared snapshot identity, application restart,
provider failure, sanitized logs, 390/768/1440 browser checks, keyboard/contrast/
reduced-motion/fallback and PDF checks. Record exact results and NOT VERIFIED items.
First live call requires separate owner authorization, approved provider/model,
transmission terms/budget and owner-provisioned secret; preview requires a later
deployment/access/storage approval. Neither is authorized by this contract.
