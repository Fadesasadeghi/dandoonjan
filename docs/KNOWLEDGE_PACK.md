# Knowledge Pack

Versioned, review-gated clinical evidence requirements (`app/core/knowledge/pack.py`).

Keys are composite `"<TREATMENT_ID>|<MODALITY>"` (P0.1 D-Q3): e.g.
`TREATMENT_ROOT_CANAL|REQUIRED` and `TREATMENT_ROOT_CANAL|RECOMMENDED` are different
propositions. Current dev pack: `kp-dev-v1.2.0-modality` — the smallest entries
needed to prove routing/assessment; clinical expansion remains out of scope.
Previously V0 shipped `kp-dev-v1.0.0`, status DEVELOPMENT,
review_status **NOT_CLINICALLY_VALIDATED** — demo/evaluation only; its rules are
not medical guidelines.

Statuses: DEVELOPMENT, REVIEW_REQUIRED, CLINICIAN_REVIEWED, RETIRED.
With `DJ_REQUIRE_CLINICIAN_REVIEWED_KNOWLEDGE_PACK=true`, assessment refuses
unreviewed packs (KnowledgePackUnavailableError) — production gate, tested.
Gap Engine and Assessment Engine read requirements only from the active pack;
every gap/assessment row stores `knowledge_pack_version`.

## P0 versioning (P0-08)

Uniqueness is (knowledge_pack_id, version) so multiple versions of one logical
pack coexist (e.g. dandoonjan_dev_pack / kp-dev-v1.0.0 and kp-dev-v1.1.0).
AssessmentSnapshot stores knowledge_pack_id + exact version + status. Duplicate
(id, version) rows are rejected by the database.
