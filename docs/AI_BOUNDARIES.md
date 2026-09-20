# AI Boundaries

AI may be used for: artifact classification, structured extraction, language
normalization, claim candidate extraction, patient-facing explanation.

AI must NOT decide: clinical evidence policy (Knowledge Pack), canonical ontology
(validators), case state transitions (state machine), assessment status rules
(deterministic engine), safety policy (safety gate), source-of-truth mutation.

Document content passed to prompts is fenced as untrusted DATA
(`app/ai/prompts.py` ISOLATION_RULE + `<<< >>>` envelopes); the deterministic mock
provider cannot follow instructions embedded in documents (adversarial-tested).

Every call: prompt version + schema version + provider/model + input/output hash
recorded in ModelRun. Invalid outputs raise ExtractionValidationError and never
enter core state (INV-02).
