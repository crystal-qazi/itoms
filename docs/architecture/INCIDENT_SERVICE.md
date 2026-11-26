# Incident service operations

The incident service implements ticket creation, allowed status transitions and comments. All operations check explicit permission grants, and updates write activity/audit records in the same transaction.

The status graph prevents arbitrary transitions. Grafana event idempotency is enforced by the unique external-source/event key in the database. External integrations must treat duplicate-key conflicts as already-processed events and must never auto-resolve tickets when an alert resolves. Internal comments require a distinct permission and must be filtered from requester-visible output.

SLA calculation, notifications, assignment history, attachments, list/search APIs and full object-level read/export checks remain subsequent work.
