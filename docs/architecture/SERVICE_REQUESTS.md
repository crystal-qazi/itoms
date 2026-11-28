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

**Known security limitation:** The shared `has_permission` function opens a separate connection. Request assignment, status changes and comments therefore do not yet serialize permission revocation with the protected mutation in one transaction. This is a documented TOCTOU consistency gap, not a passed security gate. See `AUTHORIZATION_TRANSACTION_CONSISTENCY.md` and `../engineering/SERVICE_REQUESTS_SKILL_VALIDATION.md`.

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
