INSERT INTO permissions (permission_key,description) VALUES
('release.create','Create software release records'),
('release.read','Read software releases within authorized scope'),
('release.update','Update software release lifecycle within authorized scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);