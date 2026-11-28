# Notifications and delivery outbox

The notification service creates in-app inbox records and outbox entries in one transaction. Inbox queries are scoped to the recipient employee and mark-read updates are owner-only.

The in-app and email outbox workers claim only their own channel using MySQL 8 `FOR UPDATE SKIP LOCKED`. Email is opt-in per notification: callers must explicitly request the EMAIL channel, and the recipient must have a valid address. Email delivery uses plain-text messages over STARTTLS or implicit TLS; credentials come only from environment configuration. If SMTP is not configured, email rows remain queued and are not claimed. Delivery failures use the shared bounded retry/dead-letter policy.

Abandoned PROCESSING claims can be recovered after a configurable stale interval. Attempts are bounded and exhausted rows move to DEAD. Dead-letter replay requires the explicit `notifications.outbox.replay` permission and writes an audit event. CLI commands are available for processing in-app rows, recovering stale claims and replaying one dead-lettered item.

SMTP configuration and a dedicated CLI worker are implemented. The worker sends plain-text email only, validates recipient/sender mailbox values, requires STARTTLS or implicit TLS, and reuses the bounded retry/dead-letter mechanism. EMAIL is opt-in per notification; before enabling it for real recipients, approve the sender identity, message content/privacy policy and operational schedule. Push delivery, notification preferences, retention controls and stale worker alerting remain future work.

## Concurrency and operational verification

- MySQL integration coverage verifies two concurrent outbox workers can claim ten due IN_APP rows in separate batches of five using `FOR UPDATE SKIP LOCKED`. The test asserts the claimed ID sets are disjoint and all ten rows transition to PROCESSING.
- GitHub Actions run [46124841345](https://github.com/crystal-qazi/itoms/actions/runs/46124841345) passed both `python-quality` and `mysql-migrations`; PR [#13](https://github.com/crystal-qazi/itoms/pull/13) was squash-merged as `b8d4123f5a484df669982fe171713b652f85da14`.
- This verifies concurrent claim isolation, not sustained throughput, worker crash recovery under production load, or alert delivery. Stale-claim alerting, backlog thresholds, worker supervision and on-call ownership remain deployment/operations gates.
