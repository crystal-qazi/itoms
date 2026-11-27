# Notifications and delivery outbox

The notification service creates in-app inbox records and outbox entries in one transaction. Inbox queries are scoped to the recipient employee and mark-read updates are owner-only.

The in-app and email outbox workers claim only their own channel using MySQL 8 `FOR UPDATE SKIP LOCKED`. Email is opt-in per notification: callers must explicitly request the EMAIL channel, and the recipient must have a valid address. Email delivery uses plain-text messages over STARTTLS or implicit TLS; credentials come only from environment configuration. If SMTP is not configured, email rows remain queued and are not claimed. Delivery failures use the shared bounded retry/dead-letter policy.

Abandoned PROCESSING claims can be recovered after a configurable stale interval. Attempts are bounded and exhausted rows move to DEAD. Dead-letter replay requires the explicit `notifications.outbox.replay` permission and writes an audit event. CLI commands are available for processing in-app rows, recovering stale claims and replaying one dead-lettered item.

SMTP configuration and a dedicated CLI worker are implemented. The worker sends plain-text email only, validates recipient/sender mailbox values, requires STARTTLS or implicit TLS, and reuses the bounded retry/dead-letter mechanism. EMAIL is opt-in per notification; before enabling it for real recipients, approve the sender identity, message content/privacy policy and operational schedule. Push delivery, notification preferences, retention controls and stale worker alerting remain future work.