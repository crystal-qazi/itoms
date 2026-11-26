-- Notification sender permission; grants are managed explicitly by administrators.
INSERT INTO permissions (permission_key, description)
VALUES ('notifications.send', 'Create in-app notifications for active employees')
ON DUPLICATE KEY UPDATE description=VALUES(description);