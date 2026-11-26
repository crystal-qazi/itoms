-- Manual SQA plans, executions, defects and release sign-off.
CREATE TABLE IF NOT EXISTS sqa_test_plans (
 test_plan_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 plan_key VARCHAR(80) NOT NULL UNIQUE,
 title VARCHAR(200) NOT NULL,
 scope_description MEDIUMTEXT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 status ENUM('DRAFT','ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_sqa_plan_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS sqa_test_cases (
 test_case_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 test_plan_id BIGINT UNSIGNED NOT NULL,
 case_key VARCHAR(80) NOT NULL,
 title VARCHAR(200) NOT NULL,
 preconditions TEXT NULL,
 steps MEDIUMTEXT NOT NULL,
 expected_result MEDIUMTEXT NOT NULL,
 UNIQUE KEY uq_sqa_case_key (test_plan_id,case_key),
 CONSTRAINT fk_sqa_case_plan FOREIGN KEY (test_plan_id) REFERENCES sqa_test_plans(test_plan_id)
);
CREATE TABLE IF NOT EXISTS sqa_test_executions (
 execution_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 test_case_id BIGINT UNSIGNED NOT NULL,
 executed_by BIGINT UNSIGNED NOT NULL,
 result ENUM('NOT_RUN','PASS','FAIL','BLOCKED','RETEST') NOT NULL DEFAULT 'NOT_RUN',
 actual_result MEDIUMTEXT NULL,
 executed_at DATETIME NULL,
 CONSTRAINT fk_sqa_execution_case FOREIGN KEY (test_case_id) REFERENCES sqa_test_cases(test_case_id),
 CONSTRAINT fk_sqa_execution_employee FOREIGN KEY (executed_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS sqa_defects (
 defect_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 defect_key VARCHAR(80) NOT NULL UNIQUE,
 execution_id BIGINT UNSIGNED NULL,
 title VARCHAR(200) NOT NULL,
 description MEDIUMTEXT NOT NULL,
 severity ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 status ENUM('OPEN','TRIAGED','FIXED','RETEST','CLOSED','REJECTED') NOT NULL DEFAULT 'OPEN',
 assigned_to BIGINT UNSIGNED NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_sqa_defect_execution FOREIGN KEY (execution_id) REFERENCES sqa_test_executions(execution_id),
 CONSTRAINT fk_sqa_defect_assignee FOREIGN KEY (assigned_to) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS sqa_release_signoffs (
 signoff_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 release_key VARCHAR(100) NOT NULL,
 signed_by BIGINT UNSIGNED NOT NULL,
 decision ENUM('APPROVED','REJECTED','CONDITIONAL') NOT NULL,
 evidence_reference VARCHAR(255) NULL,
 comments TEXT NULL,
 signed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_sqa_release_signoff (release_key,signed_by),
 CONSTRAINT fk_sqa_signoff_employee FOREIGN KEY (signed_by) REFERENCES employees(employee_id)
);
