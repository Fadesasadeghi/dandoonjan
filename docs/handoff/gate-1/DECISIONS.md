# DECISIONS

Status: **APPROVED by the Product Owner** as part of Gate 1. These are settled
product constraints, not open questions and not claims of implemented behavior.

| ID | Topic | Approved decision |
| --- | --- | --- |
| PO-01 | Release audience | Current release is a Controlled MVP / Demo. No real patient data is currently in scope. |
| PO-02 | Clinical scope | The product is decision-support, NOT autonomous diagnosis. This release is NOT clinical-ready. |
| PO-03 | Database | PostgreSQL is the deployment target. SQLite is for local development/testing only. |
| PO-04 | Python runtime | Python 3.11 is the official runtime. |
| PO-05 | Historical reports | Preserve historical reports. Never present them as the current report. |
| PO-06 | AI fallback | Mock AI is development/test only. A production provider failure must NOT silently fall back to Mock AI. |
| PO-07 | Claim provenance | Source-distinct claims must preserve independent provenance. Do not destructively deduplicate away clinician/document source distinction. |
| PO-08 | Legacy databases | No production legacy database currently requires migration. Migrations must still be safe on populated synthetic databases. |
| PO-09 | Concurrency acceptance | At least 5 simultaneous processing requests with correct isolation. |
| PO-10 | MVP product requirements | Required: case editing/versioning and adding evidence to an existing case. Deferred: Deep Links and clinician-review workflow. |

See [AUDIT](AUDIT.md) for gaps between intended behavior and verified behavior.
Existing audit findings are approved remediation scope; this lock makes no code
changes and does not claim these constraints have all passed acceptance testing.
