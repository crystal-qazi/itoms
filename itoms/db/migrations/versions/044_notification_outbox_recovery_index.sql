-- Support bounded, concurrent stale-claim recovery without broad outbox scans.
CREATE INDEX idx_outbox_recovery
    ON notification_outbox (delivery_status, locked_at, outbox_id);
