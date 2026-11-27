# Notifications and delivery outbox

The notification service creates in-app inbox records and outbox entries in one transaction. Inbox queries are scoped to the recipient employee and mark-read updates are owner-only.

The in-app outbox worker claims due IN_APP rows using MySQL 8 `FOR UPDATE SKIP LOCKED` and marks them sent after the inbox record is already durable. EMAIL rows are deliberately not claimed until an approved SMTP integration is configured; the worker never falsely reports an unsupported email as delivered.

Abandoned PROCESSING claims can be recovered after a configurable stale interval. Attempts are bounded and exhausted rows move to DEAD. Dead-letter replay requires the explicit `notifications.outbox.replay` permission and writes an audit event. CLI commands are available for processing in-app rows, recovering stale claims and replaying one dead-lettered item.

Email delivery still requires approved SMTP configuration, template escaping, privacy review and a dedicated worker. Push delivery, notification preferences, retention controls and stale worker alerting remain future work.