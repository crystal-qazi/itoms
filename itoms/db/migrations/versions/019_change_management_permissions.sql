-- Change-management permission catalogue. Role grants remain explicit.
INSERT INTO permissions (permission_key,description) VALUES
('change.create','Create change requests'),
('change.read','Read change requests within authorized scope'),
('change.update','Update change requests within authorized scope'),
('change.approve','Approve change requests after linked approval workflow completes')
ON DUPLICATE KEY UPDATE description=VALUES(description);