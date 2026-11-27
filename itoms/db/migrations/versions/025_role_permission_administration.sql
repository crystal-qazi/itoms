-- Dedicated authorization for explicit role-to-permission administration.
INSERT INTO permissions (permission_key,description) VALUES
('identity.roles.permissions.manage','Grant and revoke permissions on application roles')
ON DUPLICATE KEY UPDATE description=VALUES(description);
