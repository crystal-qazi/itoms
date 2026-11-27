# Incident service operations

The incident service implements ticket creation, allowed status transitions and comments. All operations check explicit permission grants, and updates write activity/audit records in the same transaction.

The status graph prevents arbitrary transitions. Grafana event idempotency is enforced by the unique external-source/event key in the database. External integrations must treat duplicate-key conflicts as already-processed events and must never auto-resolve tickets when an alert resolves. Internal comments require a distinct permission and must be filtered from requester-visible output.

Priority-based elapsed-time SLA deadlines, first public staff-response recording and read-time breach indicators are implemented. Business calendars, pause rules, automated breach monitoring/notifications, assignment history, attachments, advanced list/search APIs and full object-level read/export checks remain subsequent work.
