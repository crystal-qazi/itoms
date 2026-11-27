# Incident SLA foundation

SLA targets are configurable by priority and expressed as elapsed minutes in this initial 24x7 baseline. The service records first-response and resolution deadlines at ticket creation.

A first response is recorded only when a non-requester adds a public comment. Requester comments and internal notes do not satisfy first-response SLA. The incident detail view calculates first-response breach when the due time has passed without a recorded first response, and resolution breach when the resolution due time has passed while the incident remains unresolved. These indicators are calculated when the record is read; no background SLA monitor or notification worker is implemented.

Business calendars, holidays, pause conditions, escalation schedules and breach notifications are subsequent capabilities and must not be represented as implemented until built and tested.
