-- Service inventory permission catalog; no role grants are implied.
INSERT INTO permissions (permission_key, description) VALUES
 ('service.inventory.read', 'Read service inventory within the actor''s authorized scope'),
 ('service.inventory.create', 'Register services within the actor''s authorized team scope'),
 ('service.inventory.update', 'Update service lifecycle within the actor''s authorized scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);