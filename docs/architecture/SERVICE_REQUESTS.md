# Service Requests

## Scope

The first ITOMS release provides a deliberately basic Service Requests workflow:

- Employees submit a request with a title, description, category and priority.
- Request numbers are generated automatically and protected by a unique database constraint.
- Authorized staff can assign a request to an active team and optional active team member.
- Requests move through OPEN, IN_PROGRESS, ON_HOLD, COMPLETED or CANCELLED.
- Entering ON_HOLD requires a pending reason; the current reason is shown on the request and preserved in status activity.
- Completion requires resolution notes.
- Plain-text comments preserve author and timestamp.
- Request history and audit events record submission, assignment, comments, category administration and status transitions.
- In-app notifications are queued through the shared notification/outbox tables for assignment, status and comment events.
- Categories are dynamically administered by users with `service_request.categories.manage`.

## Explicit exclusions and remaining capability work

This module does not implement a service catalog, configurable request forms, approval workflows, service-request SLA tracking, or automated fulfillment.

The current list provides status and priority filters with a bounded service result count. Full-text/combined advanced search, pagination controls and Service Request-specific reports/dashboard remain outstanding. Priority is currently a fixed MySQL ENUM (LOW, MEDIUM, HIGH, CRITICAL), not an Admin-managed configuration list; align this with the Blueprint's configurable-priority requirement before calling Section 7.4 complete.

## Authorization

The module uses the shared permission service and trusted resource context:

- `service_request.create`
- `service_request.read`
- `service_request.update`
- `service_request.assign`
- `service_request.categories.manage`

Role grants remain explicit administrator decisions. Request reads and mutations are scoped by requester, team or department according to the actor's grants. Comments use `service_request.update` in the current implementation; no separate comment permission is defined. Category changes and request mutations write audit events in the same database transaction as their changes.

**Current bounded security guarantee:** Comment creation uses `has_permission_in_transaction` on the same MySQL connection as the comment, activity, audit and notification/outbox writes. It locks actor authorization and team scope before locking the request row, then revalidates requester/team IDs. A MySQL 8.4 two-connection test verifies that a permission revocation waits for an in-flight authorized comment transaction and that a later comment is denied. Request creation, assignment, status transitions and category administration still use the separate-connection `has_permission` path; their TOCTOU windows remain open. This is not a module-wide or repository-wide security pass. See `AUTHORIZATION_TRANSACTION_CONSISTENCY.md` and `../engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md`.

## Lifecycle

- OPEN → IN_PROGRESS, ON_HOLD, CANCELLED
- IN_PROGRESS → OPEN, ON_HOLD, COMPLETED, CANCELLED
- ON_HOLD → OPEN, IN_PROGRESS, COMPLETED, CANCELLED
- COMPLETED and CANCELLED are terminal.

A request can be completed only with non-empty resolution notes. Moving to ON_HOLD requires a non-empty pending reason (maximum 2,000 characters). Comments are plain text, length-limited and rendered through Jinja autoescaping. Existing requests retain their category reference if that category is deactivated; inactive categories are omitted from new-request forms.

## Notifications

Assignment, status and comment events enqueue IN_APP notification and outbox rows in the same request transaction. Delivery is asynchronous and depends on the configured notification worker. This module does not send email directly or claim that the worker is installed/scheduled by the application.

## Database changes

- Migration 027 creates the original request, category and activity tables.
- Migration 042 adds the current pending reason, reason history on activity and the comment table.
- Notification persistence reuses the shared notification/outbox schema from migration 007.

## Validation

See `../engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md` for the requirement crosswalk, Full-Stack/Security/UI-UX findings, and remaining release gates.
