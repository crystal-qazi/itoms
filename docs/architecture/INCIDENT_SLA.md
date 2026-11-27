# Incident SLA and escalation

SLA targets are configurable by priority and expressed as elapsed minutes in the initial 24x7 baseline. The service records first-response and resolution deadlines at ticket creation.

A first response is recorded only when a non-requester adds a public comment. Requester comments and internal notes do not satisfy first-response SLA. The incident detail view calculates first-response and resolution breach indicators at read time.

Escalation policies are configurable by priority, SLA type (FIRST_RESPONSE or RESOLUTION), level and elapsed minutes after the original deadline. Default levels are seeded for LOW, MEDIUM, HIGH and CRITICAL priorities. Administrators with `incident.sla.manage` can update thresholds at `/admin/sla/escalations`.

The `flask --app itoms incidents-process-sla-escalations` command evaluates due tickets. Unique ticket/type/level escalation records make repeated runs idempotent. Notifications are created for the active assigned employee and active team managers, when present, and are written to the in-app notification outbox. Run this command from a trusted scheduled worker; no scheduler is installed by the application.

Business calendars, holidays, pause conditions, business-hour clocks and external email/push escalation are not implemented. The current SLA clock is elapsed 24x7 time.
