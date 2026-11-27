-- Permissions required by the employee directory and scoped role-assignment lifecycle.
INSERT INTO permissions (permission_key,description) VALUES
 ('identity.accounts.create','Create employee records and first-login accounts within the actor department'),
 ('identity.roles.assign','Assign and revoke scoped application roles within authorized employee scopes')
ON DUPLICATE KEY UPDATE description=VALUES(description);
