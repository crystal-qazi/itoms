# Change and release management foundation

Change records support Normal, Standard and Emergency categories, risk, planned window, implementation/rollback/verification plans and execution outcome. Draft submission creates a linked sequential approval workflow in the same transaction. The requester selects 1–10 active approvers, excluding themselves. Scheduling is blocked until the linked approval is fully approved; cancellation also cancels any pending approval atomically.

Release records track a version against an optional service and link related changes. A READY release can initiate a sequential approval workflow through the `REQUEST_APPROVAL` action. READY → APPROVED requires the linked approval to be fully approved and the SQA release gate to pass. APPROVED → DEPLOYING rechecks both approval and SQA conditions. Cancelling a release cancels any pending linked approval atomically.

Approver assignment is explicit; job titles do not infer approval authority. The `approvals.create` role grant must be configured deliberately. Schedule conflict and blackout checks, CAB policy configuration, deployment automation and post-implementation review remain future work.
