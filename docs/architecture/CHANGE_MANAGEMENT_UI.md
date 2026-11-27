# Change Management UI

The authenticated `/changes/` register supports scoped change listing, draft creation, detail, and controlled lifecycle transitions. Each request requires a description plus implementation, rollback and verification plans. Change type and risk are selected from fixed allowlists. Owner selection is validated against active employees.

Reads and writes are checked in the service layer using the requester as the owner scope and the immutable change ID as resource identity. Status transitions are constrained by the declared state machine. State changes and request creation are written to change activity and the central audit log. All web writes validate the session CSRF token.

Submitting a draft requires the explicit `approvals.create` permission and 1–10 active approvers other than the requester. The ordered approval request, steps, history, audit event and SUBMITTED state are written in one transaction. SUBMITTED → SCHEDULED is blocked until the linked approval request is fully APPROVED. Cancelling a submitted change cancels its pending approval and skips remaining steps atomically. The `change.approve` permission remains a catalogue entry; the actual approval decision is made only by the assigned current-step approver through the shared Approval Inbox.

Release linking, CAB scheduling, conflict detection, maintenance windows and post-implementation review are not yet implemented.
