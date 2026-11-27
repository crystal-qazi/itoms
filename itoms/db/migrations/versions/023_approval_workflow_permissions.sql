-- Approval workflow permission catalogue. Role grants remain explicit.
INSERT INTO permissions (permission_key,description) VALUES
('approvals.create','Create sequential approval requests'),
('approvals.cancel','Cancel pending approval requests not owned by the requester')
ON DUPLICATE KEY UPDATE description=VALUES(description);
