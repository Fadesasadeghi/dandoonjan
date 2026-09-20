# State Machines

**Case state** (`app/core/cases/state_machine.py`): CREATED, INTAKE_COMPLETE,
PROCESSING, NEEDS_MORE_EVIDENCE, READY_FOR_ASSESSMENT, ASSESSED, REPORT_READY,
MANUAL_REVIEW_REQUIRED, FAILED, CANCELLED. Transitions are centralized and invalid
transitions are rejected (unit-tested). The orchestrator walks the allowed path.

**ProcessingRun state** (separate): QUEUED, RUNNING, SUCCEEDED, FAILED, RETRYING,
CANCELLED — operation state is never conflated with product state.
