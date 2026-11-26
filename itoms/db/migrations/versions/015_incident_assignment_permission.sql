-- Permission catalog entries required by the first-release incident workflow.
INSERT INTO permissions (permission_key, description)
VALUES
 ('incident.assign', 'Assign incidents to teams within the actor''s authorized scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);
