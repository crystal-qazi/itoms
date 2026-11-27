-- Explicit permission for audited notification dead-letter replay.
INSERT INTO permissions (permission_key,description) VALUES
 ('notifications.outbox.replay','Replay dead-lettered notification outbox entries after authorization')
ON DUPLICATE KEY UPDATE description=VALUES(description);
