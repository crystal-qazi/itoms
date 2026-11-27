# Approval workflow

Approvals use ordered sequential steps. Only the assigned approver for the current step can decide. A rejection ends the workflow and marks remaining steps skipped; approval advances to the next step and completes only after the final step. Requesters may cancel their own pending requests; other actors require the explicit `approvals.cancel` permission. Decisions and cancellations are appended to approval history in the same transaction as their audit event.

Change Management creates a linked `CHANGE` approval request when a draft is submitted. The requester selects 1–10 active employees as approvers in sequence; self-approval is prohibited. The change and approval request are committed atomically. Scheduling is blocked until that linked approval is fully approved. Cancelling a change also cancels its pending approval and skips outstanding steps in the same transaction.

Release Management creates a linked `RELEASE` approval request from the READY state using the `REQUEST_APPROVAL` action. The requester selects 1–10 active approvers in sequence; self-approval is prohibited. READY → APPROVED is blocked until the linked approval is fully approved and the independent SQA gate passes. APPROVED → DEPLOYING rechecks both conditions. Cancelling a release also cancels any pending linked approval atomically.

The owning module re-checks the final approved state and resource identity inside its own transaction before applying the gated business transition. Approval policy configuration, delegation, parallel quorum and escalation are not yet implemented. The `approvals.create` and `approvals.cancel` permission keys are registered by migration 023. Role grants remain explicit; no role is granted either permission implicitly.

## Inbox

The authenticated Approval Inbox (`/approvals/`) lists only pending requests for which the signed-in employee is the current sequential approver. Decisions are submitted with CSRF protection and are validated again by the service under transaction locks. The inbox records decisions; the Change and Release services independently enforce the resulting approval state before allowing gated transitions.
