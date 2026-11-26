# Approval workflow

Approvals use ordered sequential steps. Only the assigned approver for the current step can decide. A rejection ends the workflow and marks remaining steps skipped; approval advances to the next step and completes only after the final step. Requesters may cancel their own pending requests; other actors require the explicit `approvals.cancel` permission. Decisions and cancellations are appended to approval history in the same transaction.

The workflow engine does not itself execute the approved business action. The owning module must re-check the final approved state, resource identity and authorization inside its own transaction before applying a change. Approval policy configuration, delegation, parallel quorum and escalation are not yet implemented.
