INSERT INTO permissions (permission_key, description) VALUES
('sqa.defect.update', 'Update defect lifecycle within authorized SQA plans')
ON DUPLICATE KEY UPDATE description = VALUES(description);
