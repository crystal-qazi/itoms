-- Explicit permission to administer employees, team memberships and manager-team mappings.
INSERT INTO permissions (permission_key,description) VALUES
 ('identity.directory.manage','Manage employees, team memberships and manager-team assignments within the actor department')
ON DUPLICATE KEY UPDATE description=VALUES(description);
