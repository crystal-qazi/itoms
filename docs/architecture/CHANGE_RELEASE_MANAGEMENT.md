# Change and Release Management

Change requests are created as drafts with a description, risk classification, optional schedule and owner, plus mandatory implementation, rollback and verification plans. The service constrains lifecycle transitions and records activity and audit events.

Draft submission requires `approvals.create` and an explicitly selected sequential chain of 1–10 active approvers, excluding the requester. Approval request, steps, history, audit and change submission are atomic. Scheduling is blocked until the linked request is fully approved; cancellation cancels any pending linked approval atomically.

Software release records support version, release key, target date, release notes, optional service association and optional related change association. A READY release uses the `REQUEST_APPROVAL` action to create a sequential approval request with explicit approvers. READY → APPROVED requires that request to be fully approved and the SQA gate to pass; APPROVED → DEPLOYING rechecks both gates. Cancellation also cancels any pending linked approval.

Permission catalogue entries are registered separately from role grants. Both modules use owner-scoped resource checks; write routes validate CSRF tokens. A release's optional change association does not itself mean that change has been approved. Schedule conflict detection, maintenance windows, deployment automation and post-implementation review are not implemented.
