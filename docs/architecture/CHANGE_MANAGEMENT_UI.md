# Change Management UI

The authenticated `/changes/` register supports scoped change listing, draft creation, detail, and controlled lifecycle transitions. Each request requires a description plus implementation, rollback and verification plans. Change type and risk are selected from fixed allowlists. Owner selection is validated against active employees.

Reads and writes are checked in the service layer using the requester as the owner scope and the immutable change ID as resource identity. Status transitions are constrained by the declared state machine. State changes and request creation are written to change activity and the central audit log. All web writes validate the session CSRF token.

Approval workflow integration, release linking, CAB scheduling, conflict detection, maintenance windows and SQA sign-off are not yet implemented in this UI slice. `change.approve` is a permission catalogue placeholder, not evidence of an enforced approval gate.