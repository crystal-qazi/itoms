# Notifications and delivery outbox

The notification service creates in-app inbox records and outbox entries in one transaction. Inbox queries are scoped to the recipient employee and mark-read updates are owner-only. Outbox workers claim due work using MySQL 8 `FOR UPDATE SKIP LOCKED`; retries use bounded exponential delay and move exhausted items to DEAD.

This is infrastructure, not a running email service. Email delivery requires an approved SMTP configuration, template escaping, privacy review and worker deployment. A worker must process only channels it explicitly supports and must not mark delivery complete before the downstream provider confirms acceptance. Stale PROCESSING recovery and audited dead-letter replay are still required before production use.
