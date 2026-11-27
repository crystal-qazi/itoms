# Service Requests

## Scope

The first ITOMS release provides a deliberately basic Service Requests workflow:

- Employees submit a request with a title, description, category and priority.
- Authorized staff can assign a request to an active team and optional active team member.
- Requests move through OPEN, IN_PROGRESS, ON_HOLD, COMPLETED or CANCELLED.
- Completion requires resolution notes.
- Request history and audit events record submission, assignment, category administration and status transitions.
- Categories are dynamically administered by users with `service_request.categories.manage`.

## Explicit exclusions

This module does not implement a service catalog, configurable request forms, approval workflows, service-request SLA tracking, or automated fulfillment. Those are outside the finalized basic first-release scope.

## Authorization

The module uses the shared permission service and trusted resource context:

- `service_request.create`
- `service_request.read`
- `service_request.update`
- `service_request.assign`
- `service_request.categories.manage`

Role grants remain explicit administrator decisions. Request reads and mutations are scoped by requester, team or department according to the actor's grants. Category changes and request mutations write audit events in the same database transaction as their changes.

## Lifecycle

- OPEN → IN_PROGRESS, ON_HOLD, CANCELLED
- IN_PROGRESS → OPEN, ON_HOLD, COMPLETED, CANCELLED
- ON_HOLD → OPEN, IN_PROGRESS, COMPLETED, CANCELLED
- COMPLETED and CANCELLED are terminal.

A request can be completed only with non-empty resolution notes. Existing requests retain their category reference if that category is deactivated; inactive categories are omitted from new-request forms.
