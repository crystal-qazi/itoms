# Notifications and delivery outbox

The notification service creates in-app inbox records and outbox entries in one transaction. Inbox queries are scoped to the recipient employee and mark-read updates are owner-only.

The in-app and email outbox workers claim only their own channel using MySQL 8 `FOR UPDATE SKIP LOCKED`. Email is opt-in per notification: callers must explicitly request the EMAIL channel, and the recipient must have a valid address. Email delivery uses plain-text messages over STARTTLS or implicit TLS; credentials come only from environment configuration. If SMTP is not configured, email rows remain queued and are not claimed. Delivery failures use the shared bounded retry/dead-letter policy.

Abandoned PROCESSING claims can be recovered after a configurable stale interval. Attempts are bounded and exhausted rows move to DEAD. Dead-letter replay requires the explicit `notifications.outbox.replay` permission and writes an audit event. CLI commands are available for processing in-app rows, recovering stale claims and replaying one dead-lettered item.

SMTP configuration and a dedicated CLI worker are implemented. The worker sends plain-text email only, validates recipient/sender mailbox values, requires STARTTLS or implicit TLS, and reuses the bounded retry/dead-letter mechanism. EMAIL is opt-in per notification; before enabling it for real recipients, approve the sender identity, message content/privacy policy and operational schedule. Push delivery, notification preferences, retention controls and stale worker alerting remain future work.

## Concurrency and operational verification

- MySQL integration coverage verifies two concurrent outbox workers can claim ten due IN_APP rows in separate batches of five using `FOR UPDATE SKIP LOCKED`. The test asserts the claimed ID sets are disjoint and all ten rows transition to PROCESSING.
- GitHub Actions run [46124841345](https://github.com/crystal-qazi/itoms/actions/runs/46124841345) passed both `python-quality` and `mysql-migrations`; PR [#13](https://github.com/crystal-qazi/itoms/pull/13) was squash-merged as `b8d4123f5a484df669982fe171713b652f85da14`.
- This verifies concurrent claim isolation, not sustained throughput, worker crash recovery under production load, or alert delivery. Stale-claim alerting, backlog thresholds, worker supervision and on-call ownership remain deployment/operations gates.


## Operator runbook

### Worker commands

Run these from the approved ITOMS deployment environment under the dedicated service identity:

```bash
flask --app itoms notifications-process-outbox --batch-size 25
flask --app itoms notifications-recover-outbox --stale-after 300
```

Only after SMTP sender identity, content/privacy policy, credentials and schedule are formally approved:

```bash
flask --app itoms notifications-process-email-outbox --batch-size 25
```

Dead-letter replay is a controlled administrative action and requires the explicit replay permission:

```bash
flask --app itoms notifications-replay-outbox OUTBOX_ID --actor-employee-id EMPLOYEE_ID
```

Do not schedule the email worker before SMTP approval. Do not automatically replay DEAD rows without investigating the recorded failure and confirming the recipient/content are still appropriate.

### Queue observation queries

Queue depth and oldest item by channel/status:

```sql
SELECT channel, delivery_status, COUNT(*) AS item_count,
       MIN(created_at) AS oldest_created_at,
       MAX(attempt_count) AS max_attempt_count
FROM notification_outbox
GROUP BY channel, delivery_status
ORDER BY channel, delivery_status;
```

Abandoned PROCESSING claims older than the configured recovery interval (example: five minutes):

```sql
SELECT COUNT(*) AS stale_processing_count,
       MIN(locked_at) AS oldest_stale_lock
FROM notification_outbox
WHERE delivery_status='PROCESSING'
  AND locked_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 300 SECOND);
```

Dead-letter backlog:

```sql
SELECT channel, COUNT(*) AS dead_letter_count,
       MIN(created_at) AS oldest_dead_letter
FROM notification_outbox
WHERE delivery_status='DEAD'
GROUP BY channel;
```

These queries are observation aids, not alerting. Operations must approve service-specific backlog/age thresholds, monitoring cadence, worker restart policy, alert routing and on-call ownership. Do not invent a universal threshold or treat a successful one-off CLI run as proof of continuous delivery.


### Recovery query index

Migration `044_notification_outbox_recovery_index.sql` adds `idx_outbox_recovery (delivery_status, locked_at, outbox_id)`. The stale-claim recovery worker filters and orders by these columns before applying `FOR UPDATE SKIP LOCKED`; the dedicated composite index narrows the locking scan to stale PROCESSING rows rather than relying on the ready-delivery index (`delivery_status, available_at`). The four-worker MySQL regression in PR #16 exercises this recovery path against 40 stale rows and checks that each row is recovered exactly once.


## Concurrent stale-claim recovery verification — 2026-11-28

- Migration `044_notification_outbox_recovery_index.sql` adds `idx_outbox_recovery (delivery_status, locked_at, outbox_id)`.
- The recovery query explicitly uses this index. The four-worker regression initially exposed that the optimizer could choose a broad scan on the small test fixture even after the index was added; the explicit index hint made the intended stale-row locking range deterministic.
- MySQL 8.4 CI run [46125978646](https://github.com/crystal-qazi/itoms/actions/runs/46125978646) passed both `python-quality` and `mysql-migrations`. The four-worker test recovered 40 stale rows in four batches of ten, with exactly one retry increment and one recovery audit event per row.
- PR [#16](https://github.com/crystal-qazi/itoms/pull/16) was squash-merged into `feature/itoms-foundation` as `804458a2fbc90d51510e813933018725682a9fc6`.
- This is focused concurrency evidence, not sustained worker throughput or production monitoring certification.
