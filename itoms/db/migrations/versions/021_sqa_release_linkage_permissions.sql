-- Link manual SQA plans to the release they validate and register scoped permissions.
ALTER TABLE sqa_test_plans
    ADD COLUMN release_key VARCHAR(100) NULL AFTER plan_key,
    ADD INDEX idx_sqa_plan_release (release_key),
    ADD CONSTRAINT fk_sqa_plan_release
        FOREIGN KEY (release_key) REFERENCES software_releases(release_key);

INSERT INTO permissions (permission_key, description) VALUES
('sqa.plan.create', 'Create SQA test plans'),
('sqa.plan.read', 'Read SQA plans within authorized scope'),
('sqa.plan.update', 'Update SQA plans within authorized scope'),
('sqa.case.create', 'Create test cases within authorized SQA plans'),
('sqa.execution.create', 'Record test execution results within authorized SQA plans'),
('sqa.defect.create', 'Create defects from failed test executions'),
('sqa.defect.read', 'Read defects within authorized SQA plans'),
('sqa.signoff.create', 'Record release SQA sign-off decisions'),
('sqa.signoff.read', 'Read release SQA sign-off decisions')
ON DUPLICATE KEY UPDATE description = VALUES(description);
