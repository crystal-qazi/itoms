-- Engineering task permission catalog. Role grants remain an explicit administrator decision.
INSERT INTO permissions (permission_key, description) VALUES
 ('engineering.tasks.read', 'Read engineering tasks within the actor''s authorized team scope'),
 ('engineering.tasks.create', 'Create engineering tasks within the actor''s authorized team scope'),
 ('engineering.tasks.update', 'Update engineering task status within the actor''s authorized team scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);