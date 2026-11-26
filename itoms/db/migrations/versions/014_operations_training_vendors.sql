-- Lightweight vendor directory, operational records and training.
CREATE TABLE IF NOT EXISTS vendor_directory (
 vendor_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 vendor_name VARCHAR(200) NOT NULL,
 service_description TEXT NULL,
 support_email VARCHAR(254) NULL,
 support_phone VARCHAR(50) NULL,
 support_portal_url VARCHAR(500) NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS operational_work_items (
 work_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 work_number VARCHAR(40) NOT NULL UNIQUE,
 domain ENUM('NETWORK','INFRASTRUCTURE','ORACLE') NOT NULL,
 title VARCHAR(240) NOT NULL,
 description MEDIUMTEXT NOT NULL,
 owner_team_id BIGINT UNSIGNED NOT NULL,
 assigned_to BIGINT UNSIGNED NULL,
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 status ENUM('OPEN','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED') NOT NULL DEFAULT 'OPEN',
 external_reference VARCHAR(150) NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_ops_queue (domain,owner_team_id,status,priority),
 CONSTRAINT fk_ops_team FOREIGN KEY (owner_team_id) REFERENCES teams(team_id),
 CONSTRAINT fk_ops_assignee FOREIGN KEY (assigned_to) REFERENCES employees(employee_id),
 CONSTRAINT fk_ops_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS oracle_database_inventory (
 oracle_database_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 service_id BIGINT UNSIGNED NULL,
 environment_name VARCHAR(80) NOT NULL,
 database_name VARCHAR(128) NOT NULL,
 host_reference VARCHAR(255) NOT NULL,
 version_label VARCHAR(80) NULL,
 criticality ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 lifecycle_status ENUM('ACTIVE','MAINTENANCE','RETIRED') NOT NULL DEFAULT 'ACTIVE',
 notes TEXT NULL,
 CONSTRAINT fk_oracle_service FOREIGN KEY (service_id) REFERENCES service_records(service_id)
);
CREATE TABLE IF NOT EXISTS training_courses (
 course_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 course_title VARCHAR(200) NOT NULL,
 description TEXT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_training_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS training_enrollments (
 enrollment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 course_id BIGINT UNSIGNED NOT NULL,
 employee_id BIGINT UNSIGNED NOT NULL,
 status ENUM('ENROLLED','IN_PROGRESS','COMPLETED','CANCELLED') NOT NULL DEFAULT 'ENROLLED',
 enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at DATETIME NULL,
 UNIQUE KEY uq_training_employee_course (course_id,employee_id),
 CONSTRAINT fk_training_course FOREIGN KEY (course_id) REFERENCES training_courses(course_id),
 CONSTRAINT fk_training_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);
