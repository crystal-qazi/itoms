# Software Quality Assurance

ITOMS SQA is a manual evidence workflow. It provides test plans, test cases, execution records, defects and release sign-off decisions. It does not execute automated tests or replace CI.

## Workflow

1. Create an active test plan and optionally associate it with a software release.
2. Add test cases with preconditions, steps and expected results.
3. Record PASS, FAIL, BLOCKED or RETEST executions. Each execution is retained as evidence; the latest execution determines the case's current result.
4. Record defects against failed executions with LOW, MEDIUM, HIGH or CRITICAL severity. Defect lifecycle transitions are OPEN → TRIAGED → FIXED → RETEST → CLOSED; defects may be rejected at the OPEN or TRIAGED stage, and a failed retest may reopen a defect.
5. Complete a plan only when it contains at least one case, every case's latest result is PASS, and no unresolved HIGH/CRITICAL defect remains.
6. Record a release SQA sign-off. APPROVED sign-off requires at least one linked completed plan meeting the readiness checks.

## Enforced release gate

The release service checks the gate inside the release transition transaction, before both READY → APPROVED and APPROVED → DEPLOYING:
- at least one completed SQA plan is linked to the release key;
- every case in linked completed plans has a latest PASS execution;
- at least one APPROVED sign-off exists and every recorded sign-off is APPROVED;
- no unresolved HIGH/CRITICAL defect is linked to a test plan for that release.

The migration 021_sqa_release_linkage_permissions.sql adds the release association and SQA permission catalogue entries. Permissions are registered, not automatically granted to roles. Administrators must grant them deliberately through role configuration.

## Limitations

The current UI supports defect triage/fix/retest/close/reject actions. Approval workflow orchestration, automated test execution, CI ingestion, test evidence file attachments, and SQA reporting are not yet implemented. The schema stores one current sign-off per release/employee; a later decision by the same employee replaces their earlier decision and is audited.
