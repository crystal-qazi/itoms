-- Incident permission catalogue; role grants remain an explicit administrator decision.
INSERT INTO permissions (permission_key,description) VALUES
('incident.create','Create incidents within the actor''s authorized scope'),
('incident.read','Read incidents within the actor''s authorized scope'),
('incident.update','Transition incident status within the actor''s authorized scope'),
('incident.comment','Add public comments within the actor''s authorized scope'),
('incident.comment.internal','Add and view internal incident notes within the actor''s authorized scope'),
('incident.assign','Assign incidents to teams and members within the actor''s authorized scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);
