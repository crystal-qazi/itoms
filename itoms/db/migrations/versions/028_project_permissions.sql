-- Project portfolio and milestone permissions; grants remain explicit Admin actions.
INSERT INTO permissions (permission_key,description) VALUES
 ('project.read','Read projects and milestones within authorized team scope'),
 ('project.create','Create projects for authorized teams'),
 ('project.update','Manage milestones and project tracking within authorized team scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);
