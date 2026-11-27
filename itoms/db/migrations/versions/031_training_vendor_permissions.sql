-- Explicit permissions for vendor directory and IT training.
INSERT INTO permissions (permission_key,description) VALUES
 ('vendor.directory.read','Read support-contact vendor directory'),
 ('vendor.directory.manage','Create and deactivate vendor directory entries'),
 ('training.course.read','Read active training courses'),
 ('training.course.manage','Create and manage training courses'),
 ('training.enroll','Enroll the current employee in active training courses'),
 ('training.read','Read training enrollment records'),
 ('training.manage','Enroll employees and update enrollment completion status')
ON DUPLICATE KEY UPDATE description=VALUES(description);
